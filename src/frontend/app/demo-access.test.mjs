import test from 'node:test';
import assert from 'node:assert/strict';
import {getDemoConfig,createSession,verifySession,sessionCookie,accessGate,handleLogin,handleLogout,createLoginLimiter,proxyBackend,MAX_PROXY_BYTES} from '../demo-access.mjs';
const env={DEMO_ACCESS_ENABLED:'true',DEMO_PASSWORD:'demo-password-long-enough',DEMO_SESSION_SECRET:'s'.repeat(32),BACKEND_SHARED_KEY:'k'.repeat(32),BACKEND_INTERNAL_URL:'https://backend.example'};
const cfg=()=>getDemoConfig(env),origin='https://demo.example';
const req=(path='/',options={})=>new Request(origin+path,options);
const cookie=()=>`esg_demo_session=${createSession(cfg())}`;
const authed=(path,options={})=>req('/api/backend'+path,{...options,headers:{cookie:cookie(),...options.headers}});
test('Render config fails closed and enforces secret lengths and HTTPS',()=>{
 assert.equal(getDemoConfig({}).enabled,false);
 for(const patch of [{DEMO_ACCESS_ENABLED:undefined},{DEMO_ACCESS_ENABLED:'false'},{DEMO_PASSWORD:'short'},{DEMO_SESSION_SECRET:'short'},{BACKEND_SHARED_KEY:'short'},{BACKEND_INTERNAL_URL:'http://backend.example'},{BACKEND_INTERNAL_URL:'https://user:pass@backend.example'}])assert.throws(()=>getDemoConfig({...env,RENDER:'true',...patch}));
 assert.equal(getDemoConfig({...env,RENDER:'true',RENDER_EXTERNAL_URL:origin}).enabled,true);
});
test('sessions reject tampering malformed tokens expiry and future issuance',()=>{
 const c=cfg(),token=createSession(c,1000);assert.equal(verifySession(token,c,1001),true);
 for(const bad of [token+'x',token.replace(/^./,'X'),'garbage','',undefined])assert.equal(verifySession(bad,c,1001),false);
 assert.equal(verifySession(token,c,1000+8*3600),false);assert.equal(verifySession(token,c,999),false);
 assert.match(sessionCookie(token),/HttpOnly; Secure; SameSite=Lax/);assert.match(sessionCookie(token),/Max-Age=28800/);
});
test('workspace shares evidence and API require session',()=>{
 assert.equal(accessGate(req('/?share=secret'),cfg()).headers.get('location'),origin+'/login?next=%2F%3Fshare%3Dsecret');
 assert.equal(accessGate(req('/api/backend/shares/token/evidence/id'),cfg()).status,401);
 assert.equal(accessGate(req('/',{headers:{cookie:cookie()}}),cfg()),null);
 assert.equal(accessGate(req('/'),getDemoConfig({})),null);assert.equal(accessGate(req('/login'),cfg()),null);
});
test('login throttling logout and origin checks',async()=>{
 const limiter=createLoginLimiter();const login=password=>req('/api/demo/login?next=https://evil.example',{method:'POST',headers:{origin,'content-type':'application/x-www-form-urlencoded'},body:new URLSearchParams({password})});
 const bad=await handleLogin(login('wrong'),cfg(),limiter);assert.equal(bad.status,303);assert.equal(bad.headers.get('location'),'/login?error=1');assert.equal(bad.headers.has('set-cookie'),false);
 const good=await handleLogin(login(env.DEMO_PASSWORD),cfg(),limiter);assert.equal(good.headers.get('location'),'/');assert.match(good.headers.get('set-cookie'),/esg_demo_session=/);
 for(let i=0;i<10;i++)await handleLogin(login('wrong'),cfg(),limiter);
 assert.equal((await handleLogin(login(env.DEMO_PASSWORD),cfg(),limiter)).status,429);
 assert.equal((await handleLogin(req('/api/demo/login',{method:'POST',headers:{origin:'https://evil.example'}}),cfg(),limiter)).status,403);
 assert.match(handleLogout(req('/api/demo/logout',{method:'POST',headers:{origin}}),cfg()).headers.get('set-cookie'),/Max-Age=0/);
 assert.equal(handleLogout(req('/api/demo/logout',{method:'POST'}),cfg()).status,403);
});
test('originless same-origin form navigation works but cross-site CSRF remains denied',async()=>{
 const form=new URLSearchParams({password:env.DEMO_PASSWORD});
 const headers={'content-type':'application/x-www-form-urlencoded',
   'sec-fetch-site':'same-origin','sec-fetch-mode':'navigate','sec-fetch-dest':'document'};
 const attempt=h=>req('/api/demo/login',{method:'POST',headers:h,body:form});
 const good=await handleLogin(attempt(headers),cfg(),createLoginLimiter());
 assert.equal(good.status,303);
 assert.match(good.headers.get('set-cookie'),/esg_demo_session=/);
 for(const h of [
  {...headers,'sec-fetch-site':'cross-site'},
  {...headers,'sec-fetch-site':'same-site'},
  {...headers,'sec-fetch-mode':'cors'},
  {...headers,'sec-fetch-dest':'empty'},
  {...headers,origin:'null'},
  {...headers,origin:'https://evil.example'},
  {'content-type':'application/x-www-form-urlencoded'}
 ]){
  const response=await handleLogin(attempt(h),cfg(),createLoginLimiter());
  assert.equal(response.status,403,JSON.stringify(h));
  assert.equal(response.headers.has('set-cookie'),false);
 }
 const denied=await proxyBackend(authed('/documents',{method:'POST',headers:{
  'sec-fetch-site':'same-origin','sec-fetch-mode':'cors','sec-fetch-dest':'empty'
 },body:'{}'}),['documents'],cfg(),async()=>{throw Error('must not call API');});
 assert.equal(denied.status,403);
});
test('proxy auth headers role upstream errors no redirects or cookies',async()=>{
 let call;const upstream=async(...args)=>{call=args;return new Response('{"detail":"Denied"}',{status:403,headers:{'content-type':'application/json','set-cookie':'upstream=bad','location':'https://secret.example'}});};
 assert.equal((await proxyBackend(req('/api/backend/profile'),['profile'],cfg(),upstream)).status,401);
 const response=await proxyBackend(authed('/profile?period=2026-01',{headers:{'X-Demo-Role':'clerk','X-Demo-Backend-Key':'spoof',authorization:'Bearer spoof'}}),['profile'],cfg(),upstream);
 assert.equal(response.status,403);assert.equal(await response.text(),'{"detail":"Denied"}');assert.equal(call[0],'https://backend.example/profile?period=2026-01');
 assert.equal(call[1].headers.get('X-Demo-Backend-Key'),env.BACKEND_SHARED_KEY);assert.equal(call[1].headers.get('X-Demo-Role'),'clerk');assert.equal(call[1].headers.has('cookie'),false);assert.equal(call[1].headers.has('authorization'),false);assert.equal(call[1].redirect,'manual');assert.equal(call[1].cache,'no-store');assert.equal(response.headers.has('set-cookie'),false);assert.equal(response.headers.has('location'),false);
});
test('binary GET POST PUT at ten MiB and oversized rejection',async()=>{
 const bytes=new Uint8Array(MAX_PROXY_BYTES);bytes[0]=255;bytes[bytes.length-1]=128;
 for(const method of ['GET','POST','PUT']){
 let body;const result=await proxyBackend(authed('/documents/file',{method,headers:{origin,'content-type':'application/octet-stream'},...(method==='GET'?{}:{body:bytes})}),['documents','file'],cfg(),async(_url,options)=>{body=options.body;return new Response(bytes,{headers:{'content-type':'application/pdf','content-disposition':'attachment; filename="bill.pdf"'}});});
 assert.equal(result.status,200);assert.deepEqual(new Uint8Array(await result.arrayBuffer()),bytes);if(method!=='GET')assert.deepEqual(new Uint8Array(body),bytes);
 }
 assert.equal((await proxyBackend(authed('/documents',{method:'POST',headers:{origin},body:new Uint8Array(MAX_PROXY_BYTES+1)}),['documents'],cfg(),()=>{throw Error('must not fetch');})).status,413);
});
test('path origin method and upstream redirect validation',async()=>{
 const fail=()=>{throw Error('must not fetch');};
 for(const segments of [['..','secret'],['%2e%2e','secret'],['https:','evil'],['foo/bar'],['foo\\bar'],['%252e%252e'],[]])assert.equal((await proxyBackend(authed('/profile'),segments,cfg(),fail)).status,400);
 for(const headers of [{},{origin:'https://evil.example'}])assert.equal((await proxyBackend(authed('/profile',{method:'POST',headers,body:'{}'}),['profile'],cfg(),fail)).status,403);
 assert.equal((await proxyBackend(authed('/profile',{method:'PATCH',headers:{origin}}),['profile'],cfg(),fail)).status,405);
 assert.equal((await proxyBackend(authed('/profile'),['profile'],cfg(),async()=>new Response(null,{status:307,headers:{location:'https://evil.example'}}))).status,502);
});

test('bounded login request rejects oversized payloads without issuing a session',async()=>{
 const result=await handleLogin(req('/api/demo/login',{method:'POST',headers:{origin},body:'password='+('x'.repeat(5000))}),cfg(),createLoginLimiter());
 assert.equal(result.headers.has('set-cookie'),false);assert.equal(result.headers.get('location'),'/login?error=1');
});
test('proxy refuses oversized downloads and hides network failures',async()=>{
 for(const upstream of [async()=>new Response(new Uint8Array(MAX_PROXY_BYTES+1)),async()=>{throw Error('internal secret');}]){
 const result=await proxyBackend(authed('/documents/file'),['documents','file'],cfg(),upstream);
 assert.equal(result.status,502);assert.doesNotMatch(await result.text(),/internal secret/);
 }
});

test('login preserves safe share return URLs and rejects open redirects',async()=>{
 const next='/?share=private-pack-token&period=2026-01';
 const gate=accessGate(req(next),cfg());assert.equal(gate.headers.get('location'),origin+'/login?next='+encodeURIComponent(next));
 for(const value of [next,'/workspace?period=2026-01','//evil.example','https://evil.example','/\\evil.example','/%2f%2fevil.example','/%255cevil.example','/%broken','/\n/evil']){
  const response=await handleLogin(req('/api/demo/login',{method:'POST',headers:{origin},body:new URLSearchParams({password:env.DEMO_PASSWORD,next:value})}),cfg(),createLoginLimiter());
  assert.equal(response.headers.get('location'),value===next||value.startsWith('/workspace')?value:'/');
 }
 const failed=await handleLogin(req('/api/demo/login',{method:'POST',headers:{origin},body:new URLSearchParams({password:'wrong',next})}),cfg(),createLoginLimiter());
 assert.equal(failed.headers.get('location'),'/login?error=1&next='+encodeURIComponent(next));
});
test('hosted mutations use trusted configured HTTPS public origin behind TLS termination',async()=>{
 const hosted=getDemoConfig({...env,RENDER:'true',RENDER_EXTERNAL_URL:origin});
 const login=givenOrigin=>new Request('http://internal:10000/api/demo/login',{method:'POST',headers:{origin:givenOrigin},body:new URLSearchParams({password:env.DEMO_PASSWORD})});
 assert.equal((await handleLogin(login(origin),hosted,createLoginLimiter())).status,303);
 assert.equal((await handleLogin(login('https://evil.example'),hosted,createLoginLimiter())).status,403);
 // Render routes to an internal listener; unauthenticated redirects must
 // always point to the trusted external HTTPS website, not internal HTTP.
 const hostedGate=accessGate(new Request('http://localhost:10000/?period=2026-01'),hosted);
 assert.equal(hostedGate.status,303);
 assert.equal(hostedGate.headers.get('location'),origin+'/login?next=%2F%3Fperiod%3D2026-01');
 assert.throws(()=>getDemoConfig({...env,RENDER:'true'}),/public origin|RENDER_EXTERNAL_URL/);
 for(const value of ['http://demo.example','https://user:pass@demo.example','https://demo.example/path'])assert.throws(()=>getDemoConfig({...env,DEMO_PUBLIC_ORIGIN:value}));
});


test('full ten MiB file survives its multipart envelope with form fields',async()=>{
 const bytes=new Uint8Array(MAX_PROXY_BYTES);bytes[0]=255;bytes[bytes.length-1]=128;
 const form=new FormData();form.set('file',new Blob([bytes],{type:'image/png'}),'test-evidence.png');form.set('type','electricity');form.set('period','2026-12');
 let checked=false;
 const response=await proxyBackend(authed('/documents',{method:'POST',headers:{origin,'x-demo-role':'clerk'},body:form}),['documents'],cfg(),async(url,options)=>{
  assert.ok(options.body.length>MAX_PROXY_BYTES);
  const received=await new Request(url,{method:'POST',headers:options.headers,body:options.body}).formData();
  assert.equal(received.get('type'),'electricity');assert.equal(received.get('period'),'2026-12');
  assert.deepEqual(new Uint8Array(await received.get('file').arrayBuffer()),bytes);checked=true;
  return Response.json({id:'test-document'},{status:201});
 });
 assert.equal(response.status,201);assert.equal(checked,true);
});

test('owner deletion proxy preserves session and same-origin protections',async()=>{
 const docId='synthetic-doc';let call;
 const upstream=async(...args)=>{call=args;return new Response(JSON.stringify({deleted:true,id:docId}),{headers:{'content-type':'application/json'}});};
 const deleted=authed(`/documents/${docId}`,{method:'DELETE',headers:{origin,'X-Demo-Role':'owner','content-type':'application/json'},body:JSON.stringify({expected_version:2})});
 const result=await proxyBackend(deleted,['documents',docId],cfg(),upstream);
 assert.equal(result.status,200);assert.equal((await result.json()).deleted,true);
 assert.equal(call[1].method,'DELETE');assert.equal(call[1].headers.get('X-Demo-Role'),'owner');
 assert.equal(call[1].headers.get('X-Demo-Backend-Key'),env.BACKEND_SHARED_KEY);
 assert.equal(new TextDecoder().decode(call[1].body),'{"expected_version":2}');
 assert.equal((await proxyBackend(authed(`/documents/${docId}`,{method:'DELETE',headers:{origin:'https://evil.example','content-type':'application/json'},body:'{}'}),['documents',docId],cfg(),upstream)).status,403);
 assert.equal((await proxyBackend(req(`/api/backend/documents/${docId}`,{method:'DELETE',headers:{origin},body:'{}'}),['documents',docId],cfg(),upstream)).status,401);
});

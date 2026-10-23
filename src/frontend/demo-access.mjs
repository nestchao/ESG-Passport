// Server-only security helpers. Never import into client components.
import {createHash,createHmac,randomBytes,timingSafeEqual} from 'node:crypto';
export const SESSION_COOKIE='esg_demo_session';
export const LOGIN_CSRF_COOKIE='esg_demo_login_csrf';
const LOGIN_CSRF_SECONDS=30*60;
export const SESSION_SECONDS=8*60*60;
export const MAX_PROXY_BYTES=10*1024*1024;
export function getDemoConfig(environment=process.env){
 const enabled=environment.DEMO_ACCESS_ENABLED==='true';
 if(environment.RENDER==='true'&&!enabled)throw Error('Render requires DEMO_ACCESS_ENABLED=true.');
 if(!enabled)return {enabled:false};
 for(const [name,min] of [['DEMO_PASSWORD',16],['DEMO_SESSION_SECRET',32],['BACKEND_SHARED_KEY',32]]){
  if(typeof environment[name]!=='string'||environment[name].length<min)throw Error(`${name} must contain at least ${min} characters.`);
 }
 let backend;try{backend=new URL(environment.BACKEND_INTERNAL_URL);}catch{throw Error('BACKEND_INTERNAL_URL must be an HTTPS origin.');}
 if(backend.protocol!=='https:'||backend.username||backend.password||backend.pathname!=='/'||backend.search||backend.hash)throw Error('BACKEND_INTERNAL_URL must be an HTTPS origin without credentials or a path.');
 let publicOrigin;
 const publicUrl=environment.DEMO_PUBLIC_ORIGIN||environment.RENDER_EXTERNAL_URL;
 if(publicUrl){
  let parsed;try{parsed=new URL(publicUrl);}catch{throw Error('Demo public origin must be an HTTPS origin.');}
  if(parsed.protocol!=='https:'||parsed.username||parsed.password||parsed.pathname!=='/'||parsed.search||parsed.hash)throw Error('Demo public origin must be an HTTPS origin.');
  publicOrigin=parsed.origin;
 }
 if(environment.RENDER==='true'&&!publicOrigin)throw Error('Render requires RENDER_EXTERNAL_URL or DEMO_PUBLIC_ORIGIN for its public origin.');
 return {enabled:true,publicWorkspaceEnabled:environment.PUBLIC_WORKSPACE_ENABLED==='true',publicOrigin,password:environment.DEMO_PASSWORD,secret:environment.DEMO_SESSION_SECRET,backendKey:environment.BACKEND_SHARED_KEY,backendUrl:backend.origin};
}
const signature=(value,config)=>createHmac('sha256',config.secret).update(value).digest('base64url');
export function createSession(config,now=Math.floor(Date.now()/1000)){
 const value=`v1.${now}.${now+SESSION_SECONDS}.${randomBytes(24).toString('base64url')}`;
 return `${value}.${signature(value,config)}`;
}
export function verifySession(token,config,now=Math.floor(Date.now()/1000)){
 if(!config.enabled||typeof token!=='string'||token.length>256)return false;
 const parts=token.split('.');if(parts.length!==5||parts[0]!=='v1'||!/^\d{1,12}$/.test(parts[1])||!/^\d{1,12}$/.test(parts[2])||!/^[A-Za-z0-9_-]{32}$/.test(parts[3])||!/^[A-Za-z0-9_-]{43}$/.test(parts[4]))return false;
 const expected=signature(parts.slice(0,4).join('.'),config);
 return timingSafeEqual(Buffer.from(parts[4]),Buffer.from(expected))&&Number(parts[1])<=now&&Number(parts[2])>now&&Number(parts[2])-Number(parts[1])===SESSION_SECONDS;
}
export function sessionCookie(token,maxAge=SESSION_SECONDS){return `${SESSION_COOKIE}=${token}; Path=/; Max-Age=${maxAge}; HttpOnly; Secure; SameSite=Lax`;}
// Double-submit, signed, short-lived token for originless native form POSTs.
// Browser must present both hidden value from our page and host-scoped cookie.
export function createLoginCsrf(config,now=Math.floor(Date.now()/1000)){
 const raw=`v1.${now}.${randomBytes(24).toString('base64url')}`;
 return `${raw}.${signature('login-csrf:'+raw,config)}`;
}
export function verifyLoginCsrf(token,config,now=Math.floor(Date.now()/1000)){
 if(!config.enabled||typeof token!=='string'||token.length>180)return false;
 const parts=token.split('.');
 if(parts.length!==4||parts[0]!=='v1'||!/^[0-9]{1,12}$/.test(parts[1])||
    !/^[A-Za-z0-9_-]{32}$/.test(parts[2])||!/^[A-Za-z0-9_-]{43}$/.test(parts[3]))return false;
 const issued=Number(parts[1]);if(issued>now||issued+LOGIN_CSRF_SECONDS<=now)return false;
 const expected=signature('login-csrf:'+parts.slice(0,3).join('.'),config);
 return timingSafeEqual(Buffer.from(parts[3]),Buffer.from(expected));
}
export function loginCsrfCookie(token,secure=true){return `${LOGIN_CSRF_COOKIE}=${token}; Path=/; Max-Age=${LOGIN_CSRF_SECONDS}; HttpOnly; ${secure?'Secure; ':''}SameSite=Lax`;}
function namedCookie(request,name){return request.headers.get('cookie')?.split(';').map(part=>part.trim()).find(part=>part.startsWith(`${name}=`))?.slice(name.length+1);}
export function loginCsrfFromRequest(request){return namedCookie(request,LOGIN_CSRF_COOKIE);}
function acceptedLoginCsrf(request,config,submitted){
 const cookie=loginCsrfFromRequest(request);
 return verifyLoginCsrf(cookie,config)&&typeof submitted==='string'&&
        submitted.length===cookie.length&&timingSafeEqual(Buffer.from(submitted),Buffer.from(cookie));
}
function allowedLoginOrigin(request,config,submitted){
 if(sameOrigin(request,config))return true;
 const origin=request.headers.get('origin');
 // Only the native login form may use the double-submit fallback. Edge can
 // send the literal Origin: null on a same-origin form navigation. Treat that
 // opaque origin as untrusted unless ALL three browser Fetch Metadata signals
 // confirm same-origin document navigation AND the signed CSRF token matches.
 // Explicit foreign origins always fail even with valid CSRF credentials.
 if(origin!==null&&origin!=='null')return false;
 const site=request.headers.get('sec-fetch-site');
 const mode=request.headers.get('sec-fetch-mode'),dest=request.headers.get('sec-fetch-dest');
 if(origin==='null'){
  if(site!=='same-origin'||mode!=='navigate'||dest!=='document')return false;
 }else{
  if(site==='cross-site'||site==='same-site')return false;
  if((mode&&mode!=='navigate')||(dest&&dest!=='document'))return false;
 }
 return acceptedLoginCsrf(request,config,submitted);
}

function tokenFrom(request){return request.headers.get('cookie')?.split(';').map(part=>part.trim()).find(part=>part.startsWith(`${SESSION_COOKIE}=`))?.slice(SESSION_COOKIE.length+1);}
const headers={'Cache-Control':'no-store, max-age=0','Pragma':'no-cache','Referrer-Policy':'no-referrer'};
const error=(message,status)=>Response.json({detail:message},{status,headers});
const redirect=location=>new Response(null,{status:303,headers:{...headers,Location:location}});
export function safeReturnTo(value){
 if(typeof value!=='string'||value.length>2048||!value.startsWith('/')||value.startsWith('//')||value.includes('#'))return '/';
 let decoded=value;
 try{
  for(let i=0;i<4;i++){
   if(/[\x00-\x20\x7f\\]/.test(decoded)||!decoded.startsWith('/')||decoded.startsWith('//'))return '/';
   const next=decodeURIComponent(decoded);if(next===decoded)break;decoded=next;
  }
  if(/[\x00-\x20\x7f\\]/.test(decoded)||decoded.startsWith('//'))return '/';
  const target=new URL(value,'https://return.invalid');
  return target.origin==='https://return.invalid'?target.pathname+target.search:'/';
 }catch{return '/';}
}
const loginLocation=(next,error=false)=>'/login'+(error?'?error=1':'')+(next!=='/'?`${error?'&':'?'}next=${encodeURIComponent(next)}`:'');
export function accessGate(request,config){
 if(!config.enabled)return null;
 const url=new URL(request.url),path=url.pathname;
 // Public, completely synthetic sandbox. Explicit exact-path allowlist only;
 // NEVER expose /api/backend/* or real workspace pages through this gate.
 if(config.publicWorkspaceEnabled&&['GET','HEAD'].includes(request.method)&&path==='/demo')return redirect(new URL('/',config.publicOrigin||url.origin).href);
 if(['GET','HEAD'].includes(request.method)&&(path==='/demo'||path==='/ocr'||path==='/ocr-assets/pdf.worker.min.mjs'||/^\/demo-assets\/(?:electricity-itemised-001|water-sidebar-001|waste-landscape-001)\.png$/.test(path)))return null;
 if(config.publicWorkspaceEnabled&&(path==='/'&&['GET','HEAD'].includes(request.method)||path.startsWith('/api/backend/')&&['GET','POST','PUT','DELETE'].includes(request.method)))return null;
 if(path==='/login'||path==='/api/demo/login'||path==='/api/demo/logout'||path.startsWith('/_next/')||path==='/favicon.ico')return null;
 if(verifySession(tokenFrom(request),config))return null;
 const trustedOrigin=config.publicOrigin||url.origin;
 if(request.method==='GET'&&path==='/'&&url.search==='')return redirect(new URL('/demo',trustedOrigin).href);
 // Next.js Proxy requires absolute Location URLs for middleware redirects.
 const loginUrl=new URL(loginLocation(safeReturnTo(path+url.search)),trustedOrigin);
 return path.startsWith('/api/')?error('Demo sign-in required.',401):redirect(loginUrl.href);
}
function sameOrigin(request,config){
 const origin=request.headers.get('origin'),expected=config.publicOrigin||new URL(request.url).origin;
 // If a request supplies an Origin, it must match. Reject foreign/null origins.
 if(origin!==null)return origin===expected;
 // Some same-origin browser FORM navigations omit Origin. Fetch Metadata
 // headers are browser-controlled and reject cross-site CSRF submissions.
 // Background fetch, same-site siblings and missing metadata remain blocked.
 return request.headers.get('sec-fetch-site')==='same-origin' &&
  request.headers.get('sec-fetch-mode')==='navigate' &&
  request.headers.get('sec-fetch-dest')==='document';
}
// Bounded per-process throttling, including a global limit against spoofed/rotating IPs.
export function createLoginLimiter(){
 const entries=new Map();let windowStart=0,total=0;
 return (request,now=Date.now())=>{
  if(now-windowStart>=60_000){windowStart=now;total=0;entries.clear();}
  if(total++>=30)return false;
  const key=createHash('sha256').update(request.headers.get('x-forwarded-for')?.split(',')[0].trim()||'unknown').digest('hex');
  const attempts=entries.get(key)||0;entries.set(key,attempts+1);return attempts<5;
 };
}
export const loginLimiter=createLoginLimiter();
async function readBounded(stream,limit){
 if(!stream)return new Uint8Array();
 const reader=stream.getReader(),parts=[];let size=0;
 try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>limit){await reader.cancel();throw new RangeError('Body too large');}parts.push(value);}}
 finally{reader.releaseLock();}
 const bytes=new Uint8Array(size);let offset=0;for(const part of parts){bytes.set(part,offset);offset+=part.length;}return bytes;
}
export async function handleLogin(request,config,limiter=loginLimiter){
 if(!config.enabled)return redirect('/');
 let password='',next='/',csrf='';
 try{const bytes=await readBounded(request.body,4096);const values=new URLSearchParams(new TextDecoder().decode(bytes));password=values.get('password')||'';next=safeReturnTo(values.get('next'));csrf=values.get('csrf_token')||'';}catch{return redirect('/login?error=1');}
 if(!allowedLoginOrigin(request,config,csrf))return error('Request origin is not allowed.',403);
 if(!limiter(request))return error('Unable to sign in. Try again shortly.',429);
 const digest=value=>createHash('sha256').update(value).digest();
 if(!timingSafeEqual(digest(password),digest(config.password)))return redirect(loginLocation(next,true));
 const response=redirect(next);response.headers.set('Set-Cookie',sessionCookie(createSession(config)));return response;
}
export function handleLogout(request,config){
 if(!sameOrigin(request,config))return error('Request origin is not allowed.',403);
 const response=redirect(config.enabled?'/login':'/');response.headers.set('Set-Cookie',sessionCookie('',0));return response;
}
function validPath(segments){return Array.isArray(segments)&&segments.length>0&&segments.every(segment=>typeof segment==='string'&&segment.length>0&&segment!=='.'&&segment!=='..'&&!/[\x00-\x20\x7f%\\/:?#]/.test(segment));}
export async function proxyBackend(request,segments,config,fetchImpl=fetch){
 if(!config.enabled)return error('Demo proxy is disabled.',404);
 const isStaff=verifySession(tokenFrom(request),config);
 if(!isStaff&&!config.publicWorkspaceEnabled)return error('Demo sign-in required.',401);
 if(!['GET','POST','PUT','DELETE'].includes(request.method))return error('Method not allowed.',405);
 if(request.method!=='GET'){
  const nativeOrigin=sameOrigin(request,config);
  const site=request.headers.get('sec-fetch-site');
  // Some Edge navigations send Origin: null. For the synthetic-only sandbox,
  // accept native same-origin browser writes; real Supabase writes still require
  // the original exact Origin check and an authenticated staff session.
  if(!nativeOrigin&&(isStaff||site!=='same-origin'))return error('Request origin is not allowed.',403);
 }
 if(!validPath(segments))return error('Invalid backend path.',400);
 // Only approved fictional sample images may be uploaded anonymously.
 // The sandbox backend verifies exact SHA-256, file category and month.
 const sampleUpload=!isStaff&&request.method==='POST'&&segments.length===1&&segments[0]==='documents';
 const incoming=new URL(request.url),prefix=isStaff?'':'/sandbox';
 const target=`${config.backendUrl}${prefix}/${segments.map(encodeURIComponent).join('/')}${incoming.search}`;
 // Explicit allowlist: cookies, authorization and every incoming shared-key header are dropped.
 const outgoing=new Headers();for(const name of ['content-type','accept','x-demo-role']){const value=request.headers.get(name);if(value)outgoing.set(name,value);}
 outgoing.set('X-Demo-Backend-Key',config.backendKey);
 let body;
 try{if(request.method!=='GET'){
  // Multipart envelope allowance lets a full 10 MiB file reach the backend's file limit.
  const multipart=outgoing.get('content-type')?.startsWith('multipart/form-data');
  const limit=sampleUpload?512*1024+64*1024:MAX_PROXY_BYTES+(multipart?64*1024:0);
  body=await readBounded(request.body,limit);
 }}catch{return error('Upload exceeds the 10 MiB limit.',413);}
 try{
  const upstream=await fetchImpl(target,{method:request.method,headers:outgoing,body,redirect:'manual',credentials:'omit',cache:'no-store',signal:AbortSignal.timeout(60_000)});
  if(upstream.status>=300&&upstream.status<400&&upstream.status!==304){await upstream.body?.cancel();return error('Backend redirect refused.',502);}
  const responseHeaders=new Headers(headers);for(const name of ['content-type','content-disposition','retry-after']){const value=upstream.headers.get(name);if(value)responseHeaders.set(name,value);}
  const bytes=await readBounded(upstream.body,MAX_PROXY_BYTES);
  return new Response([204,205,304].includes(upstream.status)?null:bytes,{status:upstream.status,headers:responseHeaders});
 }catch{return error('Backend is unavailable. Please retry.',502);}
}

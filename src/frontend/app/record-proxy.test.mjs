import test from 'node:test';
import assert from 'node:assert/strict';
import {getDemoConfig,proxyBackend} from '../demo-access.mjs';
const origin='https://fictional-demo.example';
const config=getDemoConfig({DEMO_ACCESS_ENABLED:'true',PUBLIC_LIVE_WORKSPACE_ENABLED:'true',BACKEND_SHARED_KEY:'fictional-key-'.repeat(4),BACKEND_INTERNAL_URL:'https://fictional-backend.example',DEMO_PUBLIC_ORIGIN:origin});

test('passwordless proxy forwards record CRUD, archive and restore with version bodies',async()=>{
 const cases=[
  ['POST',['documents'],{type:'water'}],
  ['GET',['documents'],null],
  ['GET',['documents','fictional'],null],
  ['GET',['documents','fictional','file'],null],
  ['PUT',['documents','fictional'],{expected_version:2,name:'Fictional bill'}],
  ['PUT',['documents','fictional','activities'],{expected_version:3,confirmed:true,activities:[]}],
  ['POST',['documents','fictional','archive'],{expected_version:4}],
  ['POST',['documents','fictional','restore'],{expected_version:5}],
  ['DELETE',['documents','fictional'],{expected_version:6}],
 ];
 for(const [method,segments,body]of cases){
  let calls=0;
  const request=new Request(origin+'/api/backend/'+segments.join('/'),{method,headers:{origin,'X-Demo-Role':'owner','content-type':'application/json','x-forwarded-for':'192.0.2.51'},...(body?{body:JSON.stringify(body)}:{})});
  const result=await proxyBackend(request,segments,config,async(url,options)=>{
   calls++;
   assert.equal(url,'https://fictional-backend.example/'+segments.join('/'));
   assert.equal(options.method,method);
   assert.equal(options.headers.get('X-Demo-Role'),'owner');
   assert.equal(options.headers.get('X-Demo-Backend-Key'),config.backendKey);
   if(body)assert.deepEqual(JSON.parse(new TextDecoder().decode(options.body)),body);
   return Response.json({ok:true},{status:method==='POST'&&segments.length===1?201:200});
  });
  assert.equal(calls,1,method+' '+segments.join('/'));
  assert.equal(result.status,method==='POST'&&segments.length===1?201:200);
 }
});

test('proxy preserves backend delete guards rather than replacing them with a blanket ban',async()=>{
 for(const [status,detail]of [[403,'Only the Owner can perform this action.'],[409,'Approved evidence cannot be deleted.'],[409,'This document changed. Refresh before saving.'],[503,'Evidence storage unavailable.']]){
  const request=new Request(origin+'/api/backend/documents/fictional',{method:'DELETE',headers:{origin,'X-Demo-Role':'clerk','content-type':'application/json','x-forwarded-for':'192.0.2.52'},body:JSON.stringify({expected_version:1})});
  const response=await proxyBackend(request,['documents','fictional'],config,async()=>Response.json({detail},{status}));
  assert.equal(response.status,status);
  assert.deepEqual(await response.json(),{detail});
 }
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { createApiClient } from './api-client.mjs';
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}});

test('legacy public-demo delete restriction explains deployment mismatch without bypassing 403',async()=>{
 const api=createApiClient({fetchImpl:async()=>json({detail:'Permanent deletion is disabled on the public demo.'},403)});
 await assert.rejects(api.request('/documents/fictional',{method:'DELETE',body:JSON.stringify({expected_version:1})}),error=>{
  assert.equal(error.status,403);
  assert.match(error.message,/server-version issue/);
  assert.match(error.message,/deployment must be updated/);
  return true;
 });
});

test('ordinary deletion permissions and evidence conflicts keep their backend explanation',async()=>{
 for(const [status,message] of [[403,'Only the Owner can perform this action.'],[409,'This record belongs to an approved customer Passport. Archive it instead.']]){
  const api=createApiClient({fetchImpl:async()=>json({detail:message},status)});
  await assert.rejects(api.request('/documents/fictional',{method:'DELETE'}),error=>error.status===status&&error.message===message);
 }
});
test('JSON requests carry the simulated role and no credentials',async()=>{
 let call;const api=createApiClient({baseUrl:'http://localhost:8000/',fetchImpl:async(...args)=>{call=args;return json({ok:true});}});
 assert.deepEqual(await api.request('/profile/recalculate',{method:'POST',body:'{}'},'clerk'),{ok:true});
 assert.equal(call[0],'http://localhost:8000/profile/recalculate');assert.equal(call[1].headers.get('X-Demo-Role'),'clerk');assert.equal(call[1].headers.get('Content-Type'),'application/json');assert.equal(call[1].credentials,'omit');
});
test('multipart leaves content type boundary to fetch',async()=>{
 let headers;const api=createApiClient({fetchImpl:async(_url,options)=>{headers=options.headers;return json({id:'doc'});}});
 const body=new FormData();body.append('file',new Blob(['bill']),'bill.pdf');await api.request('/documents',{method:'POST',body,headers:{'Content-Type':'application/json'}});assert.equal(headers.has('Content-Type'),false);
});
test('validation includes nested field paths',async()=>{
 for(const [body,message] of [[{detail:[{loc:['body','activities',0,'quantity'],msg:'Must be non-negative'}]},'activities.0.quantity: Must be non-negative'],[{detail:{field:'period',message:'Invalid month'}},'period: Invalid month']]){
 const api=createApiClient({fetchImpl:async()=>json(body,422)});await assert.rejects(api.request('/documents'),error=>error.message===message&&error.status===422);}
});

test('validation exposes field errors for inline record feedback',async()=>{
 const api=createApiClient({fetchImpl:async()=>json({detail:[{loc:['body','activities.0.unit'],msg:'Choose a supported unit.'}]},422)});
 await assert.rejects(api.request('/documents'),error=>error.fieldErrors?.['activities.0.unit']==='Choose a supported unit.');
});
test('403 and 409 preserve backend action messages',async()=>{
 for(const status of [403,409]){const api=createApiClient({fetchImpl:async()=>json({detail:'Review the current draft.'},status)});await assert.rejects(api.request('/shares'),error=>error.status===status&&error.message==='Review the current draft.');}
});
test('connection errors give setup instructions without fallback',async()=>{
 const api=createApiClient({fetchImpl:async()=>{throw Error('sensitive upstream detail');}});await assert.rejects(api.request('/profile'),error=>/start the backend/i.test(error.message)&&/NEXT_PUBLIC_API_URL/.test(error.message)&&!error.message.includes('sensitive'));
});
test('protected preview fetches a file blob with the role',async()=>{
 let call;const api=createApiClient({fetchImpl:async(...args)=>{call=args;return new Response('bill',{headers:{'Content-Type':'image/png'}});}});const url=await api.preview('doc / 1','clerk');assert.match(url,/^blob:/);URL.revokeObjectURL(url);assert.match(call[0],/documents\/doc%20%2F%201\/file$/);assert.equal(call[1].headers.get('X-Demo-Role'),'clerk');
});
test('public share decorates selected evidence only and sends no identity',async()=>{
 let call;const api=createApiClient({baseUrl:'http://localhost:8000',fetchImpl:async(...args)=>{call=args;return json({token:'a/b',snapshot:{selected_evidence_ids:['one'],evidence:[{id:'one',preview_url:'blob:old'},{id:'two',preview_url:'blob:private'}]}});}});
 const pack=await api.request('/shares/a%2Fb',{},'customer');assert.equal(call[1].headers.has('X-Demo-Role'),false);assert.equal(pack.snapshot.evidence[0].preview_url,'http://localhost:8000/shares/a%2Fb/evidence/one');assert.equal(pack.snapshot.evidence[1].preview_url,undefined);
});

test('duplicate conflict identifies the saved record without exposing internal metadata',async()=>{
 const existing={message:'Already uploaded.',document_id:'saved',period:'2026-07',archived:true};
 const api=createApiClient({fetchImpl:async()=>json({detail:existing},409)});
 await assert.rejects(api.request('/documents'),error=>error.existingDocument?.id==='saved'&&error.existingDocument.period==='2026-07'&&error.existingDocument.archived===true);
});

test('same-origin proxy requests include session credentials',async()=>{
 let options;const api=createApiClient({baseUrl:'/api/backend',fetchImpl:async(_url,opts)=>{options=opts;return json({ok:true});}});
 await api.request('/profile');assert.equal(options.credentials,'same-origin');
});
test('PR9 approval gap challenge remains structured for the existing owner-review form',async()=>{
 const pr9_review={hash:'b'.repeat(64),items:[{id:'q::r1::value_not_available',code:'E3.1',issue:'value_not_available'}]};
 const api=createApiClient({fetchImpl:async()=>json({detail:{message:'Review and acknowledge each gap',pr9_review}},409)});
 await assert.rejects(api.request('/questionnaires/q/approve-share',{method:'POST',body:'{}'},'owner'),
  error=>error.status===409&&error.approvalReview?.hash===pr9_review.hash&&error.approvalReview.items[0].id===pr9_review.items[0].id);
});

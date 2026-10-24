import test from 'node:test';
import assert from 'node:assert/strict';
import {refreshAfterRecordChange} from './record-mutations.mjs';
import {createApiClient} from './api-client.mjs';

test('failed post-save refresh preserves acknowledged deletion and does not retry it',async()=>{
  const requests=[],messages=[];
  const api=createApiClient({fetchImpl:async(url,options)=>{
    requests.push(options.method||'GET');
    if(options.method==='DELETE')return Response.json({deleted:true});
    return Response.json({detail:'Temporary database outage.'},{status:503});
  }});
  const saved=await api.request('/documents/fictional',{method:'DELETE',body:JSON.stringify({expected_version:2})});
  assert.equal(saved.deleted,true);
  const refreshed=await refreshAfterRecordChange(()=>api.request('/documents'),message=>messages.push(message));
  assert.equal(refreshed,false);
  assert.deepEqual(requests,['DELETE','GET']);
  assert.match(messages[0],/change was saved/);
  assert.match(messages[0],/Temporary database outage/);
});

test('successful refresh does not report a mutation failure',async()=>{
  assert.equal(await refreshAfterRecordChange(async()=>[],()=>assert.fail('Unexpected error')),true);
});

test('plain-object refresh errors still explain that the change was saved',async()=>{
  let message;
  assert.equal(await refreshAfterRecordChange(async()=>{throw null;},value=>{message=value;}),false);
  assert.match(message,/record change was saved/);
});

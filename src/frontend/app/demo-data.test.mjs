import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createDemo } from './demo-data.mjs';

test('frontend starts with its own synthetic profile and records', async () => {
  const demo=createDemo();
  const profile=await demo.request('/profile');
  assert.equal(profile.readiness.complete,8);
  assert.equal((await demo.request('/documents')).length,6);
});
test('confirmation updates the demo; unconfirmed quantities stay excluded', async () => {
  const demo=createDemo();
  const doc=await demo.request('/documents/doc-electricity');
  await demo.request('/documents/doc-electricity/activities',{method:'PUT',body:JSON.stringify({confirmed:true,activities:doc.activities})});
  assert.equal((await demo.request('/profile')).metrics.find(m=>m.code==='E1.2').value,740);
});
test('the simulated clerk cannot approve a pack',async()=>{
  const demo=createDemo();
  await assert.rejects(demo.request('/questionnaires/request-1/approve-share',{method:'POST',body:'{}'},'clerk'),/Owner/);
});
test('reviewed questions create a frozen local preview snapshot',async()=>{
  const demo=createDemo();
  await demo.request('/questionnaires/request-1/map',{method:'POST',body:'{}'});
  let q=await demo.request('/questionnaires/request-1');
  for(const item of q.questions)await demo.request(`/questions/${item.id}/review`,{method:'PUT',body:JSON.stringify({codes:item.proposed_codes,reviewed:true})});
  q=await demo.request('/questionnaires/request-1');
  const pack=await demo.request('/questionnaires/request-1/approve-share',{method:'POST',body:JSON.stringify({version:q.version,recipient:q.customer,selected_evidence_ids:['doc-water']})});
  const before=await demo.request(`/shares/${pack.token}`,{},'customer');
  const water=await demo.request('/documents/doc-water');
  water.activities[0].quantity='20';
  await demo.request('/documents/doc-water/activities',{method:'PUT',body:JSON.stringify({confirmed:true,activities:water.activities})});
  assert.deepEqual((await demo.request(`/shares/${pack.token}`,{},'customer')).snapshot.questions,before.snapshot.questions);
  assert.equal(before.snapshot.evidence.length,1);
});

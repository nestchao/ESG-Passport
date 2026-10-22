import {test} from 'node:test';
import assert from 'node:assert/strict';
import {canonicalPolicyAnswer, setPolicyStatus, knownPolicyCount, policyStatus} from './policy-fields.mjs';

const names=['Code of Conduct','Anti-Corruption Policy','Whistleblowing Policy','Health and Safety Policy'];
test('a new month starts with four canonical unknown answers',()=>{
  assert.deepEqual(canonicalPolicyAnswer(null),{policies:names.map(name=>({name,status:'unknown'}))});
  assert.equal(knownPolicyCount(null),0);
});
test('known count includes both explicit yes and no but excludes unknown and noncanonical policies',()=>{
  const answer={policies:[{name:names[0],status:'in place'},{name:names[1],status:'not in place'},{name:names[2],status:'unknown'},{name:'Custom',status:'in place'}]};
  assert.equal(knownPolicyCount(answer),2);
  assert.equal(policyStatus(answer,names[3]),'unknown');
  assert.equal(policyStatus({policies:[{name:names[0],status:'yes'}]},names[0]),'unknown');
});
test('editing a policy preserves other explicit answers without mutating the saved answer',()=>{
  const saved={policies:[{name:names[0],status:'in place'}]};
  const next=setPolicyStatus(saved,names[1],'not in place');
  assert.equal(next.policies.length,4);
  assert.equal(knownPolicyCount(next),2);
  assert.equal(saved.policies.length,1);
  assert.deepEqual(setPolicyStatus(next,'Custom','in place'),next);
});

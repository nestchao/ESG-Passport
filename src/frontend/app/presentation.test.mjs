import { test } from 'node:test';
import assert from 'node:assert/strict';
import { policyRows, declarationText, recentRequests, customerPortalMessage } from './presentation.mjs';

test('policies have readable statuses and absent statuses stay unknown', () => {
  assert.deepEqual(policyRows({policies:[{name:'Conduct',status:'in place'},{name:'Reporting',status:'not in place'},{name:'Safety',status:'unknown'},{name:'Other'}]}), [
    {name:'Conduct',label:'In place',tone:'complete'},
    {name:'Reporting',label:'Not in place',tone:'neutral'},
    {name:'Safety',label:'Unknown',tone:'attention'},
    {name:'Other',label:'Unknown',tone:'attention'},
  ]);
  assert.deepEqual(policyRows(null), []);
});

test('years are not grouped and missing declarations are not zero', () => {
  assert.equal(declarationText('G3.1', '2025'), '2025');
  assert.equal(declarationText('G3.1', null), 'No owner declaration recorded.');
  assert.equal(declarationText('G1.1', 0), '0');
  assert.equal(declarationText('S4.1', {injuries:1,fatalities:0,description:'First aid provided.'}), 'Injuries: 1 · Fatalities: 0 · First aid provided.');
});

test('recent requests use update, creation and ID order without changing input', () => {
  const input=[
    {id:'a',created_at:'2026-09-01T00:00:00Z',updated_at:'2026-10-10T00:00:00Z'},
    {id:'b',created_at:'2026-10-02T00:00:00Z'},
    {id:'c',created_at:'2026-10-03T00:00:00Z',updated_at:'2026-10-10T00:00:00Z'},
    {id:'d',created_at:'2026-10-03T00:00:00Z',updated_at:'2026-10-10T00:00:00Z'},
  ];
  assert.deepEqual(recentRequests(input).map(q=>q.id), ['d','c','a']);
  assert.deepEqual(input.map(q=>q.id), ['a','b','c','d']);
  assert.deepEqual(recentRequests([]), []);
});

test('loaded customer packs never show share-link empty instructions', () => {
  assert.equal(customerPortalMessage(null), 'Open the share link provided by the supplier.');
  assert.equal(customerPortalMessage({snapshot:{}}), 'Your owner-approved answers and selected evidence.');
});

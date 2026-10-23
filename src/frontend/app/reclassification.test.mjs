import {test} from 'node:test';
import assert from 'node:assert/strict';
import * as fields from './record-fields.mjs';
import {recordDraftKey} from './monthly.mjs';
test('correcting document type resets incompatible quantity and unit without changing dates or source input',()=>{
 const original=[{category:'electricity',quantity:'50',unit:'kWh',period_start:'2026-12-01',period_end:'2026-12-31',estimated:true,assumptions:'Old proxy'}];
 const next=fields.reclassifyActivities(original,'water');
 assert.equal(original[0].quantity,'50');
 assert.equal(next[0].category,'water');assert.equal(next[0].unit,'m3');assert.equal(next[0].quantity,'');
 assert.equal(next[0].period_start,'2026-12-01');assert.equal(next[0].period_end,'2026-12-31');
 assert.equal(next[0].estimated,false);assert.equal(next[0].assumptions,'');
 assert.ok(fields.validateActivities(next,'water','2026-12')['activities.0.quantity']);
 const waste=fields.reclassifyActivities(original,'waste');assert.equal(waste[0].category,'waste_generated');assert.equal(waste[0].unit,'kg');
});
test('record type changes participate in unsaved edit protection',()=>{
 const draft={name:'Bill',period:'2026-12',activities:[]};
 assert.notEqual(recordDraftKey({...draft,type:'electricity'}),recordDraftKey({...draft,type:'water'}));
});

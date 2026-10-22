import test from 'node:test';
import assert from 'node:assert/strict';
import * as monthly from './monthly.mjs';

test('validates four digit reporting months including range limits', () => {
  for (const value of ['0001-01','0099-12','2026-09','9999-12']) assert.equal(monthly.isValidPeriod(value),true,value);
  for (const value of ['0000-01','10000-01','2026-1','2026-00','2026-13',' 2026-09',null,202609]) assert.equal(monthly.isValidPeriod(value),false,String(value));
});
test('month bounds use Gregorian leap rules without year 0..99 conversion', () => {
  assert.deepEqual(monthly.monthBounds('2024-02'),{start:'2024-02-01',end:'2024-02-29'});
  assert.deepEqual(monthly.monthBounds('1900-02'),{start:'1900-02-01',end:'1900-02-28'});
  assert.equal(monthly.monthBounds('2000-02').end,'2000-02-29');
  assert.equal(monthly.monthBounds('0004-02').end,'0004-02-29');
  assert.equal(monthly.monthBounds('9999-12').end,'9999-12-31');
  assert.throws(()=>monthly.monthBounds('0000-01'),RangeError);
});
test('month labels and previous month handle early years and floor', () => {
  assert.equal(monthly.monthLabel('2026-09'),'September 2026');
  assert.equal(monthly.monthLabel('0099-01'),'January 0099');
  assert.equal(monthly.previousMonth('2026-01'),'2025-12');
  assert.equal(monthly.previousMonth('0001-02'),'0001-01');
  assert.equal(monthly.previousMonth('0001-01'),null);
});
test('URL helpers select a valid month and preserve share and unrelated parameters', () => {
  assert.equal(monthly.selectedPeriod('?period=2025-02&share=public'),'2025-02');
  assert.equal(monthly.selectedPeriod('?period=bad'),'2026-09');
  assert.equal(monthly.selectedPeriod(''),'2026-09');
  const source = new URLSearchParams('share=secret&tab=evidence&period=2026-09');
  const next = new URLSearchParams(monthly.periodSearch(source,'2026-10'));
  assert.equal(next.get('share'),'secret');assert.equal(next.get('tab'),'evidence');assert.equal(next.get('period'),'2026-10');
  assert.equal(source.get('period'),'2026-09');
});
test('endpoint period paths scope collection endpoints and require explicit extra params elsewhere', () => {
  assert.equal(monthly.periodPath('/documents','2026-10',{archived:true}),'/documents?period=2026-10&archived=true');
  for (const path of ['/profile','/declarations','/questionnaires','/shares']) assert.equal(monthly.periodPath(path,'2026-10'),`${path}?period=2026-10`);
  assert.equal(monthly.periodPath('/activity-log','2026-10'),'/activity-log');
  assert.equal(monthly.periodPath('/documents/abc','2026-10'),'/documents/abc');
  assert.equal(monthly.periodPath('/shares/public','2026-10'),'/shares/public');
  assert.equal(monthly.periodPath('/documents/abc','2026-10',{period:'2026-08'}),'/documents/abc?period=2026-08');
  assert.equal(monthly.periodPath('/documents?archived=true','2026-10'),'/documents?archived=true&period=2026-10');
});
test('record dirty keys cover metadata and normalised activities', () => {
  const draft={name:'Power bill',period:'2026-09',activities:[{quantity:'2.00',category:'electricity'}]};
  const key=monthly.recordDraftKey(draft);
  assert.notEqual(key,monthly.recordDraftKey({...draft,name:'Renamed'}));
  assert.notEqual(key,monthly.recordDraftKey({...draft,period:'2026-10'}));
  assert.notEqual(key,monthly.recordDraftKey({...draft,activities:[{quantity:'3',category:'electricity'}]}));
  assert.equal(key,monthly.recordDraftKey({...draft,activities:[{quantity:'2',category:'electricity'}]}));
  assert.deepEqual(monthly.validateRecordMetadata({name:'   ',period:'0000-01'}),{name:'Enter a record name.',period:'Choose a valid reporting month.'});
  assert.deepEqual(monthly.validateRecordMetadata(draft),{});
});
test('record updates preserve input arrays and reject stale versions', () => {
  const old={id:'a',version:2,name:'Saved'},other={id:'b',version:1};const rows=Object.freeze([Object.freeze(old),other]);
  assert.equal(monthly.applyRecordUpdate(rows,{id:'a',version:1,name:'Stale'}),rows);
  assert.equal(monthly.applyRecordUpdate(rows,{id:'a',version:2,name:'Duplicate'}),rows);
  const fresh={id:'a',version:3,name:'New'};const next=monthly.applyRecordUpdate(rows,fresh);
  assert.notEqual(next,rows);assert.deepEqual(next,[fresh,other]);assert.equal(old.name,'Saved');
  assert.deepEqual(monthly.applyRecordUpdate(rows,{id:'c',version:1}),[...rows,{id:'c',version:1}]);
});
test('new declarations start blank with four unknown policies and no inherited assertions', () => {
  assert.deepEqual(monthly.defaultDeclaration('S4.1'),{injuries:'',fatalities:'',description:''});
  assert.deepEqual(monthly.defaultDeclaration('G1.1'),{directors:''});
  assert.deepEqual(monthly.defaultDeclaration('G3.1'),{year:''});
  assert.deepEqual(monthly.defaultDeclaration('S1.1'),{count:'',description:''});
  const policies=monthly.defaultDeclaration('G2.1');assert.equal(policies.policies.length,4);assert.ok(policies.policies.every(row=>row.status==='unknown'));
  policies.policies[0].status='in place';assert.equal(monthly.defaultDeclaration('G2.1').policies[0].status,'unknown');
});

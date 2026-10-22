import { test } from 'node:test';
import assert from 'node:assert/strict';
import { saveQuestionReview, replaceRequest, loadApproval } from './request-updates.mjs';

test('answer confirmation saves before retrieving only its questionnaire', async () => {
  const calls=[];
  const updated={id:'r1',version:4};
  const api=async(path,options={})=>{calls.push([path,options.method||'GET']);return path==='/questionnaires/r1'?updated:{id:'q1'};};
  assert.equal(await saveQuestionReview(api,'r1','q1',{codes:['E1.2'],reviewed:true}), updated);
  assert.deepEqual(calls,[['/questions/q1/review','PUT'],['/questionnaires/r1','GET']]);
});

test('failed saves do not retrieve or replace the draft', async () => {
  const calls=[];
  await assert.rejects(saveQuestionReview(async path=>{calls.push(path);throw Error('Conflict');},'r1','q1',{}), /Conflict/);
  assert.deepEqual(calls,['/questions/q1/review']);
});

test('failed post-save refresh remains an error for the UI to retain edits', async () => {
  await assert.rejects(saveQuestionReview(async path=>{if(path.startsWith('/questionnaires/'))throw Error('Offline');return {};},'r1','q1',{}), /Offline/);
});

test('request replacement preserves other resources and ignores older responses', () => {
  const old=[{id:'r1',version:4},{id:'r2',version:2}];
  assert.deepEqual(replaceRequest(old,{id:'r1',version:5}),[{id:'r1',version:5},old[1]]);
  assert.deepEqual(replaceRequest(old,{id:'r1',version:3}),old);
  assert.equal(replaceRequest(old,{id:'r3',version:1}).length,3);
});

test('approval loads only current request, shares and decorated customer pack', async () => {
  const calls=[];
  const api=async path=>{calls.push(path);return path==='/shares'?[]:{id:'r1'};};
  await loadApproval(api,'r1','token');
  assert.deepEqual(calls.sort(),['/questionnaires/r1','/shares','/shares/token'].sort());
});

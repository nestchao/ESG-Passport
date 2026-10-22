import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createDraftNavigator,questionDraftChanged,approvalKey,declarationKey,warnBeforeUnload} from './draft-state.mjs';

test('unchanged navigation runs immediately; dirty navigation waits for an explicit choice',()=>{
  let dirty=false,visited=0,discarded=0;
  const guard=createDraftNavigator({isDirty:()=>dirty,onDiscard:()=>{discarded++;dirty=false;}});
  assert.equal(guard.request(()=>visited++),false);assert.equal(visited,1);
  dirty=true;assert.equal(guard.request(()=>visited++),true);assert.equal(visited,1);
  guard.keepEditing();assert.equal(visited,1);assert.equal(discarded,0);
  guard.request(()=>visited++);guard.discardAndContinue();assert.equal(visited,2);assert.equal(discarded,1);
  guard.discardAndContinue();assert.equal(visited,2);
});

test('evidence return may preserve parent edits while discarding only the source edit',()=>{
  let parentDirty=true,sourceDirty=false,sourceDiscarded=0,returned=0;
  const guard=createDraftNavigator({isDirty:()=>parentDirty,onDiscard:()=>{parentDirty=false;}});
  assert.equal(guard.request(()=>returned++,{dirty:sourceDirty,discard:()=>sourceDiscarded++}),false);
  assert.equal(returned,1);assert.equal(parentDirty,true);
  sourceDirty=true;guard.request(()=>returned++,{dirty:sourceDirty,discard:()=>sourceDiscarded++});guard.discardAndContinue();
  assert.equal(parentDirty,true);assert.equal(sourceDiscarded,1);assert.equal(returned,2);
});

test('a reverted question or reordered code selection is not an unsaved edit',()=>{
  const q={reviewed:true,codes:['E1.2','E2.1'],manual_answer:''};
  assert.equal(questionDraftChanged(q,{codes:['E2.1','E1.2'],manual:''}),false);
  assert.equal(questionDraftChanged(q,{codes:['E1.2'],manual:''}),true);
  assert.equal(questionDraftChanged(q,{codes:q.codes,manual:'Owner statement'}),true);
  assert.equal(questionDraftChanged({reviewed:false,proposed_codes:['E1.2']},{codes:['E1.2'],manual:''}),false);
});

test('approval and declaration comparisons ignore ordering and numeric serialization only',()=>{
  assert.equal(approvalKey('Buyer',['b','a']),approvalKey('Buyer',['a','b']));
  assert.notEqual(approvalKey('Buyer',['a']),approvalKey('Buyer',[]));
  assert.equal(declarationKey({directors:'2'},['b','a']),declarationKey({directors:2},['a','b']));
  assert.notEqual(declarationKey({count:0,description:'No incidents'},[]),declarationKey({count:0,description:''},[]));
});

test('the unload warning uses native browser confirmation without persisting or sharing',()=>{
  let prevented=false;
  const event={preventDefault(){prevented=true;},returnValue:undefined};
  warnBeforeUnload(event);
  assert.equal(prevented,true);assert.equal(event.returnValue,'');
});

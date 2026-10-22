import test from 'node:test';
import assert from 'node:assert/strict';
import { createWorkspaceLoader } from './workspace-loading.mjs';
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};
const flush=()=>new Promise(resolve=>setImmediate(resolve));
test('starts every section concurrently and completes core without optional sections',async()=>{
  const loader=createWorkspaceLoader();const started=[];const work=Object.fromEntries(['profile','documents','questionnaires','declarations','shares'].map(key=>[key,deferred()]));const states={};
  const result=loader.load({role:'owner',request:key=>{started.push(key);return work[key].promise;},onState:(key,state)=>states[key]=state});
  assert.deepEqual(started,Object.keys(work));
  for(const key of ['profile','documents','questionnaires'])work[key].resolve(key);
  assert.equal(await result,true);assert.equal(states.declarations.status,'loading');assert.equal(states.shares.status,'loading');
});
test('partial failure preserves successful sections and can retry',async()=>{
  const loader=createWorkspaceLoader();const states={};
  await loader.load({role:'clerk',request:key=>key==='declarations'?Promise.reject(Error('offline')):Promise.resolve(key),onState:(key,state)=>states[key]=state});await flush();
  assert.equal(states.profile.status,'ready');assert.equal(states.declarations.status,'error');assert.equal(states.declarations.error,'offline');
  await loader.load({role:'clerk',request:key=>Promise.resolve(key),onState:(key,state)=>states[key]=state});await flush();
  assert.equal(states.declarations.status,'ready');assert.equal(states.shares,undefined);
});
test('rejects outdated generations even after owner to clerk to owner',async()=>{
  const loader=createWorkspaceLoader();const old=deferred();const seen=[];
  const first=loader.load({role:'owner',request:()=>old.promise,onState:(key,state)=>{if(state.status==='ready')seen.push('old');}});
  loader.invalidate();
  await loader.load({role:'clerk',request:()=>Promise.resolve('clerk'),onState:()=>{}});
  await loader.load({role:'owner',request:()=>Promise.resolve('new'),onState:(key,state)=>{if(state.status==='ready')seen.push(state.value);}});
  old.resolve('old');assert.equal(await first,false);await flush();assert.deepEqual(seen,['new','new','new','new','new']);
});
test('core failure rejects refresh after preserving successful section results',async()=>{
  const states={};const loader=createWorkspaceLoader();
  await assert.rejects(loader.load({role:'owner',request:key=>key==='documents'?Promise.reject(Error('documents unavailable')):Promise.resolve(key),onState:(key,state)=>states[key]=state}),/documents unavailable/);
  await flush();assert.equal(states.profile.status,'ready');assert.equal(states.documents.status,'error');
});
test('accepting a confirmed section rejects its older background result without cancelling other sections',async()=>{
  const loader=createWorkspaceLoader();const oldShares=deferred();const oldDeclarations=deferred();const seen=[];
  await loader.load({role:'owner',request:key=>key==='shares'?oldShares.promise:key==='declarations'?oldDeclarations.promise:Promise.resolve(key),onState:(key,state)=>{if(state.status==='ready')seen.push([key,state.value]);}});
  loader.accept('shares');oldShares.resolve('stale packs');oldDeclarations.resolve('current declarations');await flush();
  assert.equal(seen.some(([key])=>key==='shares'),false);assert.equal(seen.some(([key,value])=>key==='declarations'&&value==='current declarations'),true);
});

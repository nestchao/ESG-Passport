import test from 'node:test';
import assert from 'node:assert/strict';
const h = await import('./review-recovery.mjs').catch(()=>({}));
const docs = [{id:'a'},{id:'b'},{id:'c'}];
test('reconfirmation detects prior review without asserting a cause',()=>{
 assert.equal(h.needsReconfirmation({questions:[{reviewed:false,reviewed_at:'date'}]}),true);
 assert.equal(h.needsReconfirmation({questions:[{reviewed:false}]}),false);
});
test('recommendations use reviewed answers; selection preserves deliberate choices',()=>{
 const r={questions:[{reviewed:true,evidence_ids:['a','a','declaration-x']},{reviewed:false,evidence_ids:['b']}]};
 assert.deepEqual(h.recommendedEvidence(r),['a','declaration-x']);
 assert.deepEqual(h.evidenceSelection(r,['c','bad','c'],docs),{recommendedIds:['a'],selectedRecommendedCount:0,excludedIds:['a'],noAttachments:false});
 assert.deepEqual(h.retainEvidenceSelection([],docs),[]);
 assert.deepEqual(h.retainEvidenceSelection(['c','c','bad'],docs),['c']);
 assert.equal(h.evidenceSelection(r,['bad'],docs).noAttachments,true);
});
test('pack question evidence intersects approved selection and safe actual evidence',()=>{
 const snapshot={selected_evidence_ids:['a','b','c','d','e'],evidence:[{id:'a',preview_url:'/shares/t/evidence/a'},{id:'b',preview_url:'javascript:alert(1)'},{id:'c',preview_url:'#'},{id:'d',preview_url:'https://example.com/d'},{id:'e',preview_url:'data:text/html,bad'},{id:'unselected',preview_url:'/private'}]};
 assert.deepEqual(h.packQuestionEvidence({evidence_ids:['a','b','c','e','unselected'],metrics:[{evidence_ids:['d']}]},snapshot).map(d=>d.id),['a','d']);
 assert.deepEqual(h.packQuestionEvidence({evidence_ids:['a']},{...snapshot,selected_evidence_ids:[]}),[]);
});
test('latest approved pack uses root request ID and actual dates',()=>{
 const shares=[{questionnaire_id:'q',created_at:'2026-01-01',token:'old'},{questionnaire_id:'other',created_at:'2027-01-01'},{questionnaire_id:'q',created_at:'2026-02-01',token:'new'}];
 assert.equal(h.latestApprovedPack(shares,'q').token,'new');
 assert.equal(h.latestApprovedPack(shares,'none'),undefined);
});
test('context reload requests only needed context and normalizes lists',async()=>{
 const calls=[]; const api=async p=>{calls.push(p);return p==='/documents'?null:p==='/shares'?[]:{id:'q'};};
 assert.deepEqual(await h.reloadRequestContext(api,'a/b','clerk'),{request:{id:'q'},documents:[],shares:[]});
 assert.deepEqual(calls.sort(),['/documents','/questionnaires/a%2Fb']);
 calls.length=0;await h.reloadRequestContext(api,'q','owner');assert.deepEqual(calls.sort(),['/documents','/questionnaires/q','/shares']);
});
test('reload propagates conflicts and network failures without partial results',async()=>{
 for(const error of [Object.assign(new Error('conflict'),{status:409}),new Error('offline')]){
 await assert.rejects(h.reloadRequestContext(async p=>{if(p==='/documents')throw error;return {id:'q'};},'q','owner'),e=>e===error);
 }
});
test('create then match uses exactly two calls and awaits saved callback',async()=>{
 const calls=[];let saved;
 const api=async(p,o)=>{calls.push([p,o]);return calls.length===1?{id:'a/b'}:{id:'a/b',questions:[]};};
 const result=await h.createAndMatchRequest(api,{customer:'Buyer'},async q=>{saved=q;});
 assert.equal(saved.id,'a/b');assert.equal(result.id,'a/b');assert.deepEqual(calls.map(c=>c[0]),['/questionnaires','/questionnaires/a%2Fb/map']);assert.equal(calls[0][1].body,JSON.stringify({customer:'Buyer'}));
});
test('creation failure never calls saved callback; matching failure preserves saved callback',async()=>{
 let saved=0;const failure=new Error('offline');
 await assert.rejects(h.createAndMatchRequest(async()=>{throw failure;},{},()=>saved++),e=>e===failure);assert.equal(saved,0);
 let n=0;await assert.rejects(h.createAndMatchRequest(async()=>{if(n++)throw failure;return {id:'q'};},{},()=>saved++),/Request saved\. Matching could not finish: offline\. Retry matching or select disclosures manually\./);assert.equal(saved,1);
});

test('archived and unavailable evidence cannot be selected; active other-month evidence remains valid',()=>{
 const docs=[{id:'cross',period:'2026-01'},{id:'archived',archived:true},{id:'gone',unavailable:true}];
 assert.deepEqual(h.retainEvidenceSelection(['cross','archived','gone'],docs),['cross']);
 const result=h.evidenceSelection({questions:[{reviewed:true,evidence_ids:['cross']}]},[],docs);
 assert.equal(result.recommendedIds[0],'cross');assert.deepEqual(result.excludedIds,['cross']);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname,resolve} from 'node:path';
import {PUBLIC_DEMO_SAMPLES,PUBLIC_DEMO_MONTHS,demoSamplesForMonth} from '../public-demo-data.mjs';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
test('public demo uses only explicit fictional local records, with no production URLs or shared tokens',()=>{
 assert.equal(PUBLIC_DEMO_SAMPLES.length,3);
 assert.deepEqual([...PUBLIC_DEMO_MONTHS],['2026-03','2026-05']);
 assert.equal(demoSamplesForMonth('2026-05').length,1);
 assert.equal(demoSamplesForMonth('2026-03').length,2);
 for(const s of PUBLIC_DEMO_SAMPLES){
  assert.match(s.id,/^syn-[a-z]+-001$/);
  assert.match(s.image,/^\/demo-assets\/[a-z-]+-001\.png$/);
  assert.ok(existsSync(resolve(root,'public',s.image.slice(1))));
  assert.ok(s.caveat.length>20);
  assert.ok(s.question.length>20);
  assert.ok(s.answer.length>50);
  assert.equal(s.image.includes('http'),false);
 }
 const waste=PUBLIC_DEMO_SAMPLES.find(s=>s.kind==='waste');
 assert.equal(waste.quantity,'4850');
 assert.equal(waste.suggestion.category,'waste_diverted');
 assert.match(waste.answer,/does not independently establish/);
 assert.match(waste.caveat,/No generated, diverted or disposed total/);
 const electricity=PUBLIC_DEMO_SAMPLES.find(s=>s.kind==='electricity');
 assert.equal(electricity.quantity,'2577');
 assert.match(electricity.answer,/sample factor/);
 const water=PUBLIC_DEMO_SAMPLES.find(s=>s.kind==='water');
 assert.equal(water.quantity,'807');
 assert.equal(water.isEstimated,true);
});
test('public demo client cannot access the protected API, storage, secrets, forms or external endpoints',()=>{
 const source=readFileSync(resolve(root,'app/demo/page.tsx'),'utf8');
 for(const dangerous of ['apiRequest','apiPreview','/api/backend','SupabaseClient','createClient(','fetch(','XMLHttpRequest','localStorage','sessionStorage','/shares/','/documents/']){
  assert.equal(source.includes(dangerous),false,dangerous);
 }
 assert.match(source,/documents are fictional examples/);
 assert.match(source,/no account or password/i);
 assert.match(source,/Staff sign-in/);
 assert.match(source,/simulation/i);
 assert.match(source,/not proof of completed recycling/);
});

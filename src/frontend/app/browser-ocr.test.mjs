import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {parseBrowserBill} from '../browser-ocr-candidates.mjs';
import {getDemoConfig,accessGate} from '../demo-access.mjs';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');

test('conservative document candidate detection for electricity and Malay water',()=>{
 const e=parseBrowserBill('TENAGA DEMO MERANTI\nBILLING PERIOD: 01/05/2026 - 31/05/2026\nTotal energy usage: 2,577 kWh','electricity','2026-05');
 assert.equal(e.quantity,'2577');assert.equal(e.unit,'kWh');assert.equal(e.period_start,'2026-05-01');assert.equal(e.period_end,'2026-05-31');assert.equal(e.verified,false);
 const w=parseBrowserBill('AIR DEMO KENCANA\nPENGGUNAAN AIR: 807 m3\nTARIKH: 02/04/2026','water','2026-03');
 assert.equal(w.quantity,'807');assert.equal(w.unit,'m3');assert.equal(w.document_date,'2026-04-02');
});
test('waste net transfer does not invent diversion and excludes gross/tare',()=>{
 const w=parseBrowserBill('PUSAT TIMBANG\nGROSS / BERAT KASAR: 13,680 kg\nTARE / BERAT KENDERAAN: 8,830 kg\nNET / BERAT BERSIH: 4,850 kg\nTujuan: RECYCLING\nTarikh: 29/03/2026','waste','2026-03');
 assert.equal(w.quantity,'4850');assert.equal(w.unit,'kg');assert.equal(w.category,'unclassified_waste_transfer');
 assert.equal(w.notes.some(x=>x.includes('NOT verified')),true);
 assert.equal(w.period_start,'2026-03-29');
});
test('ambiguous or invalid content cannot become verified claims',()=>{
 const a=parseBrowserBill('Energy usage: 100 kWh\nEnergy usage: 500 kWh','electricity','2026-03');
 assert.equal(a.quantity,'');assert.equal(a.verified,false);
 assert.match(a.notes.join(' '),/Conflicting quantities/);
 const b=parseBrowserBill('No date or volume found','water','2026-03');
 assert.equal(b.quantity,'');assert.equal(b.verified,false);
 assert.throws(()=>parseBrowserBill('x','water','2026-17'),/valid reporting month/);
 assert.throws(()=>parseBrowserBill('x'.repeat(60001),'water','2026-03'),/too long/);
});
test('OCR and only the PDF worker asset are anonymous GET allowed; production API unchanged',()=>{
 const cfg=getDemoConfig({DEMO_ACCESS_ENABLED:'true',DEMO_PASSWORD:'very-long-synthetic-password',DEMO_SESSION_SECRET:'s'.repeat(50),BACKEND_SHARED_KEY:'k'.repeat(50),BACKEND_INTERNAL_URL:'https://backend.example',FRONTEND_ORIGIN:'https://example.com',PUBLIC_WORKSPACE_ENABLED:'true'});
 const req=(p,method='GET')=>new Request('https://example.com'+p,{method});
 assert.equal(accessGate(req('/ocr'),cfg),null);
 assert.equal(accessGate(req('/ocr-assets/pdf.worker.min.mjs'),cfg),null);
 assert.notEqual(accessGate(req('/ocr','POST'),cfg),null);
 assert.notEqual(accessGate(req('/ocr-assets/anything.mjs'),cfg),null);
 assert.ok(existsSync(resolve(root,'public/ocr-assets/pdf.worker.min.mjs')));
 assert.ok(readFileSync(resolve(root,'app/ocr/page.tsx'),'utf8').includes('worker.recognize'));
});

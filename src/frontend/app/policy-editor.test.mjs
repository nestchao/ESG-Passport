import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import * as fields from './policy-fields.mjs';

const require=createRequire(process.env.POLICY_FRONTEND_ROOT ? `${process.env.POLICY_FRONTEND_ROOT}/package.json` : import.meta.url);
const {createElement}=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
const ts=require('typescript');
const source=readFileSync(new URL('./policy-editor.tsx',import.meta.url),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2020}}).outputText;
const module={exports:{}};
new Function('require','module','exports',compiled)(id=>id==='./policy-fields.mjs'?fields:require(id),module,module.exports);
const {PolicyEditor}=module.exports;
const props={answer:{},period:'2026-10',onChange(){},documents:[],selectedEvidence:[],onEvidenceChange(){}};
const render=extra=>renderToStaticMarkup(createElement(PolicyEditor,{...props,...extra}));

test('four policies have native labelled radio groups and unknown is the only initial selection',()=>{
  const html=render();
  assert.equal((html.match(/<fieldset/g)||[]).length,4);
  assert.equal((html.match(/type="radio"/g)||[]).length,12);
  assert.equal((html.match(/checked=""/g)||[]).length,4);
  assert.equal((html.match(/<input(?=[^>]*value="unknown")(?=[^>]*checked="")[^>]*>/g)||[]).length,4);
  for(const name of fields.POLICIES.map(p=>p.name))assert.ok(html.includes(name));
  assert.ok(html.includes('0 of 4 policy statuses known'));
  assert.ok(html.includes('Unknown answers remain incomplete'));
});
test('previous month stays a reference and cannot check current month known answers',()=>{
  const previousAnswer={policies:fields.POLICIES.map(p=>({name:p.name,status:'in place'}))};
  const html=render({previousAnswer,previousPeriod:'2026-09'});
  assert.equal((html.match(/<input(?=[^>]*value="unknown")(?=[^>]*checked="")[^>]*>/g)||[]).length,4);
  assert.ok(html.includes('Previous month (2026-09):'));
  assert.ok(html.includes('Reference only'));
});
test('disabled mode locks every answer and attachment and retains explicit save metadata',()=>{
  const html=render({disabled:true,owner:'Test Owner',savedAt:'2026-10-22T00:00:00Z',documents:[{id:'d1',name:'Safety.pdf',period:'2026-09'}],selectedEvidence:['d1']});
  assert.equal((html.match(/type="radio" disabled=""/g)||[]).length,12);
  assert.match(html,/<input[^>]*type="checkbox"[^>]*disabled=""[^>]*checked=""/);
  for(const text of ['Owner:','Test Owner','Saved:','Safety.pdf','2026-09','Selected'])assert.ok(html.includes(text));
  assert.equal((html.match(/<section[^>]*aria-label="Supporting attachments"/g)||[]).length,1);
});

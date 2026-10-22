import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';

// Exercise the actual TSX components using the project's existing compiler.
function component(file, name) {
  let source=readFileSync(new URL(file,import.meta.url),'utf8');
  if(name==='Question') source=source.slice(0,source.indexOf('export default function Home'))+
    source.slice(source.indexOf('function Question('),source.indexOf('function ExtractionMetadata('))+'\nexport {Question};';
  const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2020}}).outputText;
  const module={exports:{}};
  const require=createRequire(import.meta.url);
  const resolve=id=>id==='./desktop-overview'?{DesktopOverview}:id==='./declaration-summary'?{DeclarationSummary}:require(id);
  new Function('require','module','exports',compiled)(resolve,module,module.exports);
  return module.exports[name];
}
const DeclarationSummary=component('./declaration-summary.tsx','DeclarationSummary');
const DesktopOverview=component('./desktop-overview.tsx','DesktopOverview');

test('declaration UI renders policy rows with labels rather than JSON',()=>{
  const html=renderToStaticMarkup(createElement(DeclarationSummary,{code:'G2.1',value:{policies:[{name:'Conduct',status:'in place'},{name:'Safety',status:'unknown'},{name:'Reporting',status:'not in place'}]}}));
  assert.equal((html.match(/role="listitem"/g)||[]).length,3);
  for(const label of ['Conduct','In place','Unknown','Not in place'])assert.ok(html.includes(label));
  assert.ok(!html.includes('&quot;status&quot;'));
});

test('declaration UI preserves missing values and displays a plain reporting year',()=>{
  assert.match(renderToStaticMarkup(createElement(DeclarationSummary,{code:'G3.1',value:'2025'})),/>2025</);
  assert.match(renderToStaticMarkup(createElement(DeclarationSummary,{code:'G3.1',value:null})),/No owner declaration recorded/);
  assert.match(renderToStaticMarkup(createElement(DeclarationSummary,{code:'G2.1',value:null})),/No owner declaration recorded/);
});

const overviewProps={readiness:{complete:9,total:11},breakdown:{complete:9,estimated:2},documents:[],requests:[],gaps:[],periodLabel:'September 2026',titles:{},onUpload(){},onReview(){},onRecords(){},onRequest(){},onGap(){},onAllRequests(){}};
test('overview renders three newest request shortcuts and View all',()=>{
  const requests=[1,4,2,3].map(n=>({id:String(n),customer:`Buyer ${n}`,period:'2026-09',status:'draft',created_at:`2026-10-0${n}T00:00:00Z`}));
  const html=renderToStaticMarkup(createElement(DesktopOverview,{...overviewProps,requests}));
  assert.ok(html.includes('View all'));
  assert.ok(html.indexOf('Buyer 4')<html.indexOf('Buyer 3'));
  assert.ok(html.indexOf('Buyer 3')<html.indexOf('Buyer 2'));
  assert.ok(!html.includes('Buyer 1'));
});
test('overview empty requests have a helpful empty state',()=>{
  const html=renderToStaticMarkup(createElement(DesktopOverview,overviewProps));
  assert.ok(html.includes('No customer requests yet.'));
});

test('question edits are locked during saving so late responses cannot discard new edits',()=>{
  const Question=component('./page.tsx','Question');
  const props={q:{id:'q1',codes:[],text:'Unsupported question'},index:0,role:'owner',busy:true,onSave(){},onEvidence(){},onDirty(){},onDraftChange(){}};
  const html=renderToStaticMarkup(createElement(Question,props));
  assert.match(html,/<fieldset disabled=""/);
  assert.match(html,/<textarea[^>]*disabled=""/);
  const editable=renderToStaticMarkup(createElement(Question,{...props,busy:false}));
  assert.ok(!editable.includes('<fieldset disabled=""'));
  assert.ok(!/<textarea[^>]*disabled=""/.test(editable));
});

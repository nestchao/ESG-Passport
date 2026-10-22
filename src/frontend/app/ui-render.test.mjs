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
  const resolve=id=>id==='./draft-answer'?{DraftAnswer}:id==='./desktop-overview'?{DesktopOverview}:id==='./declaration-summary'?{DeclarationSummary}:require(id);
  new Function('require','module','exports',compiled)(resolve,module,module.exports);
  return module.exports[name];
}
const DeclarationSummary=component('./declaration-summary.tsx','DeclarationSummary');
const DesktopOverview=component('./desktop-overview.tsx','DesktopOverview');
const DraftAnswer=component('./draft-answer.tsx','DraftAnswer');

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


test('prepared policy answer renders structured statuses, month and owner without raw JSON',()=>{
 const q={reviewed:true,answer:'Raw JSON must not appear: {"policies":[]}',metrics:[{code:'G2.1',title:'Policies in place',badge:'declared',value:{policies:[{name:'Code of Conduct',status:'in place'},{name:'Whistleblowing Policy',status:'not in place'},{name:'Safety',status:'unknown'}]},confirmed_by:['Mr Lim']}]};
 const html=renderToStaticMarkup(createElement(DraftAnswer,{question:q,period:'2026-12'}));
 for(const text of ['Prepared answer','December 2026','Partial-year coverage','Code of Conduct','In place','Not in place','Unknown','Mr Lim','Owner declared'])assert.ok(html.includes(text),text);
 assert.ok(!html.includes('Raw JSON'));assert.ok(!html.includes('&quot;policies&quot;'));
 assert.equal((html.match(/role="listitem"/g)||[]).length,3);
});
test('draft answer preserves explicit missing values, estimates and waste breakdown',()=>{
 const q={reviewed:true,metrics:[{code:'E4.1',title:'Waste management',badge:'missing',value:null,unit:'t',components:[{name:'generated',value:'0.050000',unit:'t'},{name:'diverted',value:null,unit:'t'},{name:'disposed',value:'0',unit:'t'}]},{code:'E2.1',title:'Energy consumption',badge:'estimated',value:'597.845790',unit:'kWh'}]};
 const html=renderToStaticMarkup(createElement(DraftAnswer,{question:q,period:'2026-12',changed:true}));
 for(const text of ['Not available','Generated','Diverted','Disposed','0.05','597.84579','Estimated','changes','confirm'])assert.ok(html.includes(text),text);
 assert.ok(!html.includes('[object Object]'));
});
test('unsupported owner answer and unconfirmed draft retain their original text',()=>{
 const manual='Not available. Scope 3 is outside this test profile.';
 const html=renderToStaticMarkup(createElement(DraftAnswer,{question:{reviewed:true,answer:manual,manual_declaration:{declared_by:'Mr Lim'},metrics:[]},period:'2026-12'}));
 assert.ok(html.includes(manual));assert.ok(html.includes('Mr Lim'));
 const waiting=renderToStaticMarkup(createElement(DraftAnswer,{question:{reviewed:false,answer:'Not available — confirm this mapping first.',metrics:[]},period:'2026-12'}));
 assert.ok(waiting.includes('Draft answer'));assert.ok(waiting.includes('confirm this mapping first'));
});


test('numeric answer display rounds for readability while retaining precise value in its title',()=>{
 const html=renderToStaticMarkup(createElement(DraftAnswer,{question:{reviewed:true,metrics:[{code:'E2.1',title:'Energy',badge:'estimated',value:'597.84579230080572',unit:'kWh'}]},period:'2026-12'}));
 assert.ok(html.includes('title="597.84579230080572 kWh"'));
 assert.ok(html.includes('>597.846<span>kWh</span>'));
});

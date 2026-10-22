import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {createRequire} from 'node:module';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import ts from 'typescript';

function load(file){
  const source=readFileSync(new URL(file,import.meta.url),'utf8');
  const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2020}}).outputText;
  const require=createRequire(import.meta.url),module={exports:{}};
  const resolve=id=>id.startsWith('./')&&existsSync(new URL(id+'.tsx',import.meta.url))?load(id+'.tsx'):require(id);
  new Function('require','module','exports',js)(resolve,module,module.exports);return module.exports;
}
test('unsaved changes dialog offers two explicit choices without saving',()=>{
  const {UnsavedChangesDialog}=load('./unsaved-changes-dialog.tsx');
  const html=renderToStaticMarkup(createElement(UnsavedChangesDialog,{onKeep(){},onDiscard(){}}));
  assert.match(html,/role="alertdialog"/);assert.match(html,/Keep editing/);assert.match(html,/Discard changes/);
  assert.doesNotMatch(html,/>Save changes</);
});
test('evidence selection explains zero files and omitted supporting documents without blocking share',()=>{
  const {EvidenceSelector}=load('./evidence-selector.tsx');
  const props={request:{questions:[{reviewed:true,evidence_ids:['one','two']}]},documents:[{id:'one',name:'Power.png'},{id:'two',name:'Fuel.png'}],selectedIds:[],onChange(){},disabled:false};
  const empty=renderToStaticMarkup(createElement(EvidenceSelector,props));
  assert.match(empty,/0 of 2 supporting files selected/);assert.match(empty,/No attachments will be shared/);assert.match(empty,/Select supporting evidence/);
  const partial=renderToStaticMarkup(createElement(EvidenceSelector,{...props,selectedIds:['one']}));
  assert.match(partial,/1 of 2 supporting files selected/);assert.match(partial,/Fuel.png/);assert.match(partial,/not included/);
});
test('recovery notice shows previous pack and requires an explicit reload',()=>{
  const {RequestRecoveryNotice}=load('./request-recovery-notice.tsx');
  const props={request:{id:'r1',status:'draft',questions:[{reviewed:false,reviewed_at:'2026-09-01'}]},shares:[{questionnaire_id:'r1',created_at:'2026-10-01',token:'approved'}],role:'owner',conflict:false,busy:false,onReload(){},onOpenPack(){}};
  const html=renderToStaticMarkup(createElement(RequestRecoveryNotice,props));
  assert.match(html,/Your answers need reviewing again because source data or mappings changed/);assert.match(html,/Reload latest answers/);assert.match(html,/Previous approved pack remains available/);assert.match(html,/Open approved pack/);
  const clerk=renderToStaticMarkup(createElement(RequestRecoveryNotice,{...props,role:'clerk'}));
  assert.doesNotMatch(clerk,/Open approved pack/);
});
test('partial quantities never masquerade as a complete metric',()=>{
  const {MetricAvailability}=load('./metric-availability.tsx');
  const html=renderToStaticMarkup(createElement(MetricAvailability,{metric:{value:null,badge:'missing',components:[{name:'generated',value:'0.100000000000',unit:'t'}]}}));
  assert.match(html,/review incomplete/i);assert.match(html,/0.1 t/);assert.match(html,/Available/);
  assert.equal(renderToStaticMarkup(createElement(MetricAvailability,{metric:{value:0,badge:'auto',components:[]}})),'');
});

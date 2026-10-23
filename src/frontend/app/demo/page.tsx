"use client";

import {useState} from 'react';
import {ArrowRight,Check,ClipboardCheck,FileCheck2,FileText,FolderOpen,Leaf,LockKeyhole,RotateCcw,ShieldAlert,Sparkles,BarChart3,Eye,ExternalLink} from 'lucide-react';
import {PUBLIC_DEMO_SAMPLES,PUBLIC_DEMO_MONTHS,demoSamplesForMonth,type PublicDemoSample} from '../../public-demo-data.mjs';
import './public-demo.css';

type Screen='Overview'|'Records'|'Customer request'|'Passport preview';
const pages:Screen[]=['Overview','Records','Customer request','Passport preview'];
const icons=[BarChart3,FolderOpen,ClipboardCheck,FileCheck2];
const months:Record<string,string>={'2026-03':'March 2026','2026-05':'May 2026'};
const names:Record<string,string>={waste_generated:'Waste generated',waste_diverted:'Waste diverted',waste_disposed:'Waste disposed'};

export default function PublicDemo(){
 const [screen,setScreen]=useState<Screen>('Overview');
 const [month,setMonth]=useState('2026-03');
 const [activeId,setActiveId]=useState('syn-waste-001');
 const [questionId,setQuestionId]=useState('syn-waste-001');
 const [reviewed,setReviewed]=useState<string[]>([]);
 const [wasteCategory,setWasteCategory]=useState('');
 const [acknowledged,setAcknowledged]=useState(false);
 const [previewReady,setPreviewReady]=useState(false);
 const [openMobileNav,setOpenMobileNav]=useState(false);
 const list=demoSamplesForMonth(month);
 const selected=PUBLIC_DEMO_SAMPLES.find(s=>s.id===activeId)??PUBLIC_DEMO_SAMPLES[0];
 const question=PUBLIC_DEMO_SAMPLES.find(s=>s.id===questionId)??PUBLIC_DEMO_SAMPLES[0];
 const allReviewed=reviewed.includes(question.id);
 const coverage=Math.round(reviewed.filter(id=>list.some(s=>s.id===id)).length/Math.max(1,list.length)*100);
 const selectedCategory=wasteCategory ? names[wasteCategory] : 'Unclassified transfer';
 const jump=(next:Screen)=>{setScreen(next);setOpenMobileNav(false);};
 const chooseMonth=(next:string)=>{setMonth(next);setActiveId(demoSamplesForMonth(next)[0]?.id??activeId);};
 const toggleReviewed=(id:string)=>{setReviewed(old=>old.includes(id)?old.filter(v=>v!==id):[...old,id]);setPreviewReady(false);};
 const reset=()=>{setScreen('Overview');setMonth('2026-03');setActiveId('syn-waste-001');setQuestionId('syn-waste-001');setReviewed([]);setWasteCategory('');setAcknowledged(false);setPreviewReady(false);};
 const renderRecord=(item:PublicDemoSample)=>{
  const isWaste=item.kind==='waste';
  return <div className="pd-evidence" key={item.id}>
   <div className="pd-source-panel">
    <div className="pd-small-head"><FileText size={16}/><b>{item.file}</b></div>
    <img className="pd-evidence-image" src={item.image} alt={`Fully synthetic ${item.title.toLowerCase()} for demonstration only`}/>
    <span className="pd-source-caption">Synthetic source document · Original illustration from test fixtures</span>
   </div>
   <section className="pd-edit-panel">
    <div className="pd-card-heading"><div><span className="pd-eyebrow">OCR candidate review</span><h2>{item.title}</h2></div><span className="pd-pill">Not production data</span></div>
    <p className="pd-muted">These values are preloaded from a fictional sample. Reviewing or changing them affects only this browser page.</p>
    <dl className="pd-data-grid">
     <div><dt>Source</dt><dd>{item.source}</dd></div><div><dt>Reporting period</dt><dd>{item.period}</dd></div>
     <div><dt>Detected quantity</dt><dd><strong>{Number(item.quantity).toLocaleString('en-MY')} {item.unit}</strong></dd></div>
     <div><dt>Document category</dt><dd>{item.kind[0].toUpperCase()+item.kind.slice(1)}</dd></div>
     <div><dt>Suggested disclosure</dt><dd>{item.disclosure}</dd></div><div><dt>Source reading</dt><dd>{item.isEstimated?'Estimated':'Printed quantity'}</dd></div>
    </dl>
    {isWaste&&<div className="pd-suggestion">
      <div className="pd-note-head"><Sparkles size={17}/>Suggested classification: <strong>{item.suggestion?.label}</strong><span className="pd-pill amber">Unverified</span></div>
      <p>{item.suggestion?.basis}. This is a declared destination, <strong>not proof of completed recycling.</strong></p>
      <label htmlFor="pd-waste-category">Illustrative waste category</label>
      <select id="pd-waste-category" value={wasteCategory} onChange={e=>{setWasteCategory(e.target.value);setPreviewReady(false);}}>
       <option value="">Choose category (unverified)</option>{Object.entries(names).map(([id,name])=><option key={id} value={id}>{name}</option>)}
      </select>
      <button type="button" className="pd-quiet" onClick={()=>setWasteCategory(item.suggestion?.category??'')} >Use suggested category <ArrowRight size={14}/></button>
      {wasteCategory&&<p className="pd-warning">{selectedCategory} is a simulated choice only. Supporting evidence is still needed before this could become a verified ESG disclosure.</p>}
    </div>}
    <div className="pd-warning"><ShieldAlert size={16}/><span>{item.caveat}</span></div>
    <div className="pd-action-row"><button type="button" className="pd-button secondary" onClick={()=>toggleReviewed(item.id)}><Check size={16}/>{reviewed.includes(item.id)?'Undo simulated review':'Mark reviewed (demo only)'}</button><button type="button" className="pd-button primary" onClick={()=>{setQuestionId(item.id);setAcknowledged(false);setPreviewReady(false);jump('Customer request');}}>Use in sample questionnaire <ArrowRight size={16}/></button></div>
   </section>
  </div>;
 };
 return <div className="public-demo">
  <aside className={`pd-sidebar${openMobileNav?' is-open':''}`}>
   <a className="pd-brand" href="/demo"><Leaf size={26}/>ESG Passport</a>
   <div className="pd-company"><strong>Meranti Demo Manufacturing</strong><small>Composite fictional examples · Malaysia</small></div>
   <div className="pd-sidebar-label">PUBLIC EXPERIENCE</div>
   <nav aria-label="Demo navigation">{pages.map((page,i)=>{const Icon=icons[i];return <button key={page} type="button" aria-current={screen===page?'page':undefined} className={screen===page?'selected':''} onClick={()=>jump(page)}><Icon size={18}/>{page}</button>;})}</nav>
   <div className="pd-sidebar-footer"><ShieldAlert size={17}/><span>Synthetic information only. No live uploads, accounts, customer records, or Supabase connections.</span></div>
  </aside>
  <div className="pd-main-shell">
   <header className="pd-topbar">
    <div className="pd-top-left"><button type="button" aria-label="Toggle navigation" className="pd-mobile-nav" onClick={()=>setOpenMobileNav(v=>!v)}>☰</button><span className="pd-breadcrumb">ESG Passport <span>/</span> Public demo <span>/</span> <strong>{screen}</strong></span></div>
    <div className="pd-top-links"><span className="pd-status"><span className="pd-dot"/> Offline demo</span><a href="/login" className="pd-staff-link"><LockKeyhole size={15}/>Staff sign-in</a></div>
   </header>
   <div className="pd-safety-banner"><ShieldAlert size={16}/><span><strong>PUBLIC SYNTHETIC DEMO.</strong> All documents are fictional examples from different test scenarios. Actions simulate a workflow locally; nothing is saved, shared, uploaded, approved, or submitted to production systems.</span><button type="button" onClick={reset}><RotateCcw size={15}/> Reset demo</button></div>
   <main className="pd-content">
    <div className="pd-page-heading"><div><div className="pd-eyebrow">ESG READINESS · SANDBOX</div><h1>{screen==='Overview'?'Prepare an ESG Passport, safely':screen}</h1><p>{screen==='Overview'?'Explore how evidence becomes defensible disclosures — with no account or password.':screen==='Records'?'View synthetic source documents and simulated OCR candidates.':screen==='Customer request'?'Map a fictional buyer question to SEDG evidence and review limitations.':'See what a customer-facing pack could look like before real owner approval.'}</p></div><span className="pd-badge">Synthetic demonstration</span></div>
    {screen==='Overview'&&<>
     <div className="pd-month-tabs" aria-label="Reporting period"><span>Reporting period</span>{PUBLIC_DEMO_MONTHS.map(m=><button key={m} type="button" className={month===m?'active':''} onClick={()=>chooseMonth(m)}>{months[m]}</button>)}</div>
     <div className="pd-stats"><div><small>Sample records</small><strong>{list.length}</strong><span>Local fixtures only</span></div><div><small>Simulated review progress</small><strong>{coverage}%</strong><span>No server writes</span></div><div><small>Protected customer data</small><strong>0 accessed</strong><span>Live workspace isolated</span></div></div>
     <section className="pd-panel"><div className="pd-card-heading"><div><span className="pd-eyebrow">WHAT YOU CAN EXPLORE</span><h2>Four steps to a customer-ready answer</h2></div></div><div className="pd-flow">{pages.map((page,index)=>{const Icon=icons[index];return <button key={page} onClick={()=>jump(page)} type="button"><span className="pd-flow-step">0{index+1} <Icon size={19}/></span><strong>{page}</strong><small>{['See what is available','Review OCR source values','Map a question to evidence','Preview limitations and disclosures'][index]}</small><ArrowRight size={16}/></button>;})}</div></section>
     <section className="pd-panel"><div className="pd-card-heading"><div><span className="pd-eyebrow">EVIDENCE INVENTORY</span><h2>Available sample records</h2></div><button className="pd-quiet" type="button" onClick={()=>jump('Records')}>Explore records <ArrowRight size={15}/></button></div><div className="pd-record-list">{list.map(s=><button key={s.id} type="button" onClick={()=>{setActiveId(s.id);jump('Records');}}><FileText size={20}/><span><strong>{s.title}</strong><small>{s.period} · {s.disclosure}</small></span><b>{Number(s.quantity).toLocaleString('en-MY')} {s.unit}</b><ArrowRight size={15}/></button>)}</div></section>
    </>}
    {screen==='Records'&&<><div className="pd-record-switcher">{PUBLIC_DEMO_SAMPLES.map(s=><button key={s.id} type="button" className={activeId===s.id?'active':''} onClick={()=>setActiveId(s.id)}>{s.title}<small>{s.period}</small></button>)}</div>{renderRecord(selected)}</>}
    {screen==='Customer request'&&<div className="pd-request-layout"><section className="pd-panel"><span className="pd-eyebrow">SYNTHETIC BUYER QUESTION</span><h2>Questionnaire mapping</h2><label htmlFor="pd-select-question">Choose a sample customer question</label><select id="pd-select-question" value={questionId} onChange={e=>{setQuestionId(e.target.value);setPreviewReady(false);setAcknowledged(false);}}>{PUBLIC_DEMO_SAMPLES.map(s=><option value={s.id} key={s.id}>{s.question}</option>)}</select><div className="pd-question"><FileText size={21}/><p>{question.question}</p></div><div className="pd-suggestion"><div className="pd-note-head"><Sparkles size={18}/> Suggested SEDG match: <strong>{question.disclosure}</strong><span className="pd-pill amber">Needs review</span></div><p>Evidence: {question.file} · {Number(question.quantity).toLocaleString('en-MY')} {question.unit} · {question.period}</p></div><label className="pd-checkbox"><input type="checkbox" checked={allReviewed} onChange={()=>toggleReviewed(question.id)}/> I reviewed this synthetic source and its limitations (simulation only).</label></section><section className="pd-panel"><span className="pd-eyebrow">DRAFT RESPONSE</span><h2>Proposed answer</h2><p className="pd-answer">{question.answer}</p><div className="pd-warning"><ShieldAlert size={16}/>{question.caveat}</div><button type="button" className="pd-button primary pd-full" onClick={()=>{setAcknowledged(false);setPreviewReady(false);jump('Passport preview');}}>Continue to owner review <ArrowRight size={16}/></button></section></div>}
    {screen==='Passport preview'&&<div className="pd-request-layout"><section className="pd-panel"><span className="pd-eyebrow">OWNER REVIEW · SIMULATION</span><h2>Review before sharing</h2><p className="pd-muted">A real owner must verify disclosures and choose evidence. This public demonstration cannot approve or publish a live Passport.</p><div className="pd-check-row"><span>Disclosure</span><strong>{question.disclosure} · {question.metric}</strong></div><div className="pd-check-row"><span>Source record</span><strong>{question.file}</strong></div><div className="pd-check-row"><span>Clerk review (demo)</span><strong>{allReviewed?'Marked reviewed':'Not yet reviewed'}</strong></div><div className="pd-warning"><ShieldAlert size={16}/>{question.caveat}</div><label className="pd-checkbox"><input type="checkbox" checked={acknowledged} onChange={e=>{setAcknowledged(e.target.checked);setPreviewReady(false);}}/> I understand these synthetic answers have unresolved limitations and are not certified.</label><button type="button" disabled={!acknowledged||!allReviewed} className="pd-button primary pd-full" onClick={()=>setPreviewReady(true)}>Generate local preview <Eye size={16}/></button>{!allReviewed&&<p className="pd-muted pd-hint">Mark this sample record reviewed in the Customer request step first.</p>}</section><section className="pd-panel pd-preview"><span className="pd-eyebrow">CUSTOMER VIEW · NOT A REAL SHARE LINK</span><h2>{previewReady?'Illustrative ESG Passport':'Preview not generated'}</h2>{previewReady?<><span className="pd-pill">Browser-only simulation</span><div className="pd-passport-mark"><Leaf size={24}/> Meranti Demo Manufacturing</div><h3>{question.disclosure}: {question.metric}</h3><p>{question.answer}</p><div className="pd-warning"><ShieldAlert size={16}/>{question.caveat}</div><p className="pd-muted">Sample evidence: {question.file}. No real customer receives a link; no Supabase records are accessed.</p></>:<div className="pd-empty"><FileCheck2 size={45}/><p>A sample disclosure and its caveats will appear here after you complete the simulated review.</p></div>}</section></div>}
    <footer className="pd-footer"><span>ESG Passport · Public sandbox · Fictional records and offline UI interactions only</span><a href="/login">Open protected staff login <ExternalLink size={14}/></a></footer>
   </main>
  </div>
 </div>;
}

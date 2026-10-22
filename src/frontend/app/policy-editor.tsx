import {useId} from 'react';
import {ShieldCheck, BadgeDollarSign, MessageSquare, HeartPulse, CheckCircle2, CircleMinus, CircleHelp, Paperclip} from 'lucide-react';
import {POLICIES, POLICY_STATUSES, policyStatus, policyStatusLabel, setPolicyStatus, knownPolicyCount} from './policy-fields.mjs';
import type {PolicyAnswer} from './policy-fields.mjs';

type PolicyDocument={id:string;name:string;period?:string|null;archived?:boolean;unavailable?:boolean};
export type PolicyEditorProps={
  answer:unknown;onChange:(answer:PolicyAnswer)=>void;period:string;disabled?:boolean;
  owner?:string|null;savedAt?:string|null;previousAnswer?:unknown;previousPeriod?:string|null;
  documents:PolicyDocument[];selectedEvidence:string[];onEvidenceChange:(ids:string[])=>void;
};
const policyIcons=[ShieldCheck,BadgeDollarSign,MessageSquare,HeartPulse];
const statusIcons={'in place':CheckCircle2,'not in place':CircleMinus,unknown:CircleHelp};

export function PolicyEditor({answer,onChange,period,disabled=false,owner,savedAt,previousAnswer,previousPeriod,documents,selectedEvidence,onEvidenceChange}:PolicyEditorProps){
  const instance=useId();
  const known=knownPolicyCount(answer);
  const savedDate=savedAt?new Date(savedAt):null;
  const savedLabel=savedDate&&!Number.isNaN(savedDate.valueOf())?savedDate.toLocaleString('en-GB',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Kuala_Lumpur'})+' MYT':savedAt;
  const hasPrevious=!!previousPeriod&&previousPeriod!==period&&previousAnswer!=null;
  return <section className="policy-editor" aria-label={`Policy declaration for ${period}`}>
    <div className="policy-progress"><div><span className="policy-eyebrow">MONTHLY OWNER DECLARATION</span><h3>{known} of 4 policy statuses known</h3><p>Confirm what is in place for <strong>{period}</strong>. Unknown answers remain incomplete.</p></div><span className={`policy-completion ${known===4?'complete':''}`}>{known===4?'All answered':`${4-known} to confirm`}</span></div>
    <div className="policy-attribution"><span>Owner: <strong>{owner||'Not yet recorded'}</strong></span><span>Saved: {savedLabel?<time dateTime={savedAt||undefined}>{savedLabel}</time>:'Not yet saved for this month'}</span></div>
    {hasPrevious&&<p className="policy-reference-note">Reference only: previous month answers are shown below. Confirm each policy for {period}.</p>}
    <div className="policy-cards">{POLICIES.map((policy,index)=>{
      const Icon=policyIcons[index];const status=policyStatus(answer,policy.name);const descriptionId=`${instance}-policy-${index}-description`;
      return <fieldset className="policy-card" key={policy.name} disabled={disabled} aria-describedby={descriptionId}>
        <legend><span className="policy-card-icon"><Icon size={20} aria-hidden="true"/></span>{policy.name}</legend>
        <p id={descriptionId} className="policy-description">{policy.description}</p>
        <div className="policy-options">{POLICY_STATUSES.map(choice=>{const StatusIcon=statusIcons[choice];return <label key={choice} className={`policy-option policy-${choice.replaceAll(' ','-')} ${status===choice?'is-selected':''}`}>
          <input type="radio" disabled={disabled} name={`${instance}-policy-${index}`} value={choice} checked={status===choice} onChange={()=>onChange(setPolicyStatus(answer,policy.name,choice))}/>
          <StatusIcon size={15} aria-hidden="true"/><span>{policyStatusLabel(choice)}</span>
        </label>;})}</div>
        {hasPrevious&&<p className="policy-previous">Previous month ({previousPeriod}): <strong>{policyStatusLabel(policyStatus(previousAnswer,policy.name))}</strong></p>}
      </fieldset>;
    })}</div>
    <section className="policy-attachments" aria-label="Supporting attachments">
      <h3><Paperclip size={17} aria-hidden="true"/>Supporting attachments <span>(optional)</span></h3>
      <p>Attach supporting files to this declaration. Files from other months show their reporting month.</p>
      {documents.length?<div className="policy-attachment-list">{documents.map(document=>{const selected=selectedEvidence.includes(document.id);return <label className={`policy-attachment ${selected?'is-selected':''}`} key={document.id}>
        <input type="checkbox" disabled={disabled||!!((document.archived||document.unavailable)&&!selected)} checked={selected} onChange={event=>onEvidenceChange(event.target.checked?[...new Set([...selectedEvidence,document.id])]:selectedEvidence.filter(id=>id!==document.id))}/>
        <span className="policy-attachment-name">{document.name}{document.archived?' · Archived — remove before saving':document.unavailable?' · Unavailable — remove before saving':''}<small>Reporting month: {document.period||'Not supplied'}</small></span><span className="policy-attachment-state">{selected?'Selected':'Not selected'}</span>
      </label>;})}</div>:<p className="policy-attachments-empty">No files uploaded yet. You can save your declaration without an attachment.</p>}
    </section>
  </section>;
}

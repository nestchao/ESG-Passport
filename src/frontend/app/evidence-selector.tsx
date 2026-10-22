import {evidenceSelection,retainEvidenceSelection} from './review-recovery.mjs';
type Data=Record<string,any>;
export function EvidenceSelector({request,documents,selectedIds,onChange,disabled}:{request:Data;documents:Data[];selectedIds:string[];onChange:(ids:string[])=>void;disabled:boolean}){
  const summary=evidenceSelection(request,selectedIds,documents);
  return <section className="evidence-selection" aria-label="Evidence selection">
    <div className="flex-between"><h4>Select evidence to share</h4><button className="button secondary small" disabled={disabled||!summary.recommendedIds.length} onClick={()=>onChange(retainEvidenceSelection([...selectedIds,...summary.recommendedIds],documents))}>Select supporting evidence</button></div>
    <p role="status">{summary.selectedRecommendedCount} of {summary.recommendedIds.length} supporting files selected · {retainEvidenceSelection(selectedIds,documents).length} attachments total</p>
    {summary.noAttachments?<div className="info-note">No attachments will be shared. The customer will receive the approved answers only.</div>:summary.excludedIds.length>0?<div className="info-note">Supporting files not included: {summary.excludedIds.map(id=>documents.find(doc=>doc.id===id)?.name||id).join(', ')}. You may approve with these files excluded.</div>:null}
    <div className="evidence-checkboxes">{documents.map(doc=><label className="checkbox-label" key={doc.id}><input type="checkbox" disabled={disabled} checked={selectedIds.includes(doc.id)} onChange={event=>onChange(event.target.checked?[...selectedIds,doc.id]:selectedIds.filter(id=>id!==doc.id))}/>{doc.name}{summary.recommendedIds.includes(doc.id)&&<small className="supporting-label">Supporting file</small>}</label>)}</div>
  </section>;
}

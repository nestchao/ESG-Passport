import {needsReconfirmation,latestApprovedPack} from './review-recovery.mjs';
type Data=Record<string,any>;
export function RequestRecoveryNotice({request,shares,role,conflict,busy,onReload,onOpenPack}:{request:Data;shares:Data[];role:string;conflict:boolean;busy:boolean;onReload:()=>void;onOpenPack:(token:string)=>void}){
  const again=needsReconfirmation(request);
  const previous=role==='owner'?latestApprovedPack(shares,request.id):undefined;
  return <div className="request-notices">
    {(again||conflict)&&<div className="recovery-notice" role="status"><p>{again?'Your answers need reviewing again because source data or mappings changed.':'This request has changed. Reload the latest answers before continuing.'}</p><button className="button secondary small" disabled={busy} onClick={onReload}>Reload latest answers</button></div>}
    {previous&&request.status!=='shared'&&<div className="recovery-notice previous-pack"><p>Draft changed · Previous approved pack remains available</p><button className="text-button" disabled={busy} onClick={()=>onOpenPack(previous.token)}>Open approved pack</button></div>}
  </div>;
}

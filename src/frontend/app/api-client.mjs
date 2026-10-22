const DEFAULT_API_URL='http://127.0.0.1:8000';

function errorMessage(payload,status){
  const detail=payload?.detail??payload;
  if(Array.isArray(detail))return detail.map(item=>{
    const field=Array.isArray(item.loc)?item.loc.filter(part=>!['body','query','path'].includes(part)).join('.'):item.field;
    return `${field?`${field}: `:''}${item.msg||item.message||'Invalid value.'}`;
  }).join(' · ');
  if(typeof detail==='string')return detail;
  if(detail?.message)return `${detail.field?`${detail.field}: `:''}${detail.message}`;
  return status===403?'This simulated role cannot perform this action.':status===409?'The draft changed. Reopen it before continuing.':status===503?'Backend storage is unavailable. Configure the backend Supabase settings, restart it, and retry.':`The backend could not complete this action (HTTP ${status}). Retry or check the backend setup.`;
}

export function createApiClient({baseUrl=DEFAULT_API_URL,fetchImpl=(...args)=>fetch(...args)}={}){
  const base=baseUrl.replace(/\/+$/,'');
  const connectionMessage=`Cannot reach the ESG Passport API at ${base}. Start the backend, configure its Supabase settings, and check NEXT_PUBLIC_API_URL and the backend CORS origins. Then retry.`;
  async function send(path,options={},role='owner'){
    const headers=new Headers(options.headers);
    // A share token is the capability for these public endpoints; no role is needed.
    const publicShare=/^\/shares\/[^/]+(?:\/evidence\/[^/]+)?(?:\?.*)?$/.test(path);
    headers.delete('X-Demo-Role');
    if(!publicShare)headers.set('X-Demo-Role',role);
    if(options.body instanceof FormData)headers.delete('Content-Type');
    else if(options.body!=null&&!headers.has('Content-Type'))headers.set('Content-Type','application/json');
    let response;
    try{response=await fetchImpl(`${base}${path}`,{...options,headers,credentials:'omit',cache:'no-store'});}
    catch{throw Error(connectionMessage);}
    if(!response.ok){
      let payload;try{payload=await response.json();}catch{}
      const error=Error(errorMessage(payload,response.status));error.status=response.status;
      if(response.status===409&&payload?.detail?.document_id)error.existingDocument={id:payload.detail.document_id,period:payload.detail.period,archived:!!payload.detail.archived};
      if(Array.isArray(payload?.detail))error.fieldErrors=Object.fromEntries(payload.detail.map(item=>[
        Array.isArray(item.loc)?item.loc.filter(part=>!['body','query','path'].includes(part)).join('.'):item.field,
        item.msg||item.message||'Invalid value.',
      ]).filter(([field])=>field));
      throw error;
    }
    return response;
  }
  function decoratePack(pack,token){
    if(!pack?.snapshot?.evidence||!token)return pack;
    const selected=new Set(pack.snapshot.selected_evidence_ids||pack.snapshot.evidence_ids||pack.selected_evidence_ids||[]);
    return {...pack,snapshot:{...pack.snapshot,evidence:pack.snapshot.evidence.map(({preview_url,...doc})=>({...doc,...(selected.has(doc.id)?{preview_url:`${base}/shares/${encodeURIComponent(token)}/evidence/${encodeURIComponent(doc.id)}`}:{})}))}};
  }
  async function request(path,options={},role='owner'){
    const response=await send(path,options,role);
    if(response.status===204)return null;
    let result;try{result=await response.json();}catch{throw Error('The backend returned an unreadable response. Check the API URL and retry.');}
    const match=path.match(/^\/shares\/([^/?]+)(?:\?.*)?$/);
    if(match)return decoratePack(result,result.token||decodeURIComponent(match[1]));
    return result;
  }
  async function preview(documentId,role='owner'){
    const response=await send(`/documents/${encodeURIComponent(documentId)}/file`,{},role);
    return URL.createObjectURL(await response.blob());
  }
  return {request,preview};
}

const api=createApiClient({baseUrl:process.env.NEXT_PUBLIC_API_URL||DEFAULT_API_URL});
export const apiRequest=(path,options,role)=>api.request(path,options,role);
export const apiPreview=(documentId,role)=>api.preview(documentId,role);

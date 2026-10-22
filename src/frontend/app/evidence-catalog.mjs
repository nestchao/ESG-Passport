export async function hydrateEvidence(api,documents,ids){
 const known=new Set(documents.map(doc=>doc.id));const missing=[...new Set(ids)].filter(id=>!known.has(id));
 const extra=await Promise.all(missing.map(async id=>{try{return await api(`/documents/${encodeURIComponent(id)}`);}catch(error){if(error.status===404)return{id,name:'Unavailable evidence '+id,unavailable:true};throw error;}}));
 return [...documents,...extra];
}

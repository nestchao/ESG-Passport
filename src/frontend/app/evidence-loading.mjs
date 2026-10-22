/** Each loader belongs to one mounted workspace; no persistent or cross-role cache. */
export function createEvidenceLoader({details,preview,onDetails,onSource,revoke}){
 let generation=0,sourceGeneration=0,url='';
 const release=()=>{if(url){revoke(url);url='';}};
 const fetchSource=id=>Promise.resolve().then(()=>preview(id)).then(value=>({url:value}),error=>({error}));
 function cancel(){generation++;sourceGeneration++;release();}
 async function consume(source,version,sourceVersion){
  const result=await source;
  if(version!==generation||sourceVersion!==sourceGeneration){if(result.url)revoke(result.url);return;}
  if(result.error){onSource({status:'error',url:'',error:result.error?.message||'Source file could not load.'});return;}
  release();url=result.url;onSource({status:'ready',url,error:''});
 }
 async function open(id,context){
  cancel();const version=generation,sourceVersion=sourceGeneration;
  onSource({status:'loading',url:'',error:''});
  const document=Promise.resolve().then(()=>details(id));
  const source=fetchSource(id);
  try{
   const value=await document;
   if(version!==generation){void consume(source,version,sourceVersion);return;}
   onDetails(value,context);
   void consume(source,version,sourceVersion);
  }catch(error){
   if(version===generation){cancel();onSource({status:'idle',url:'',error:''});}
   void consume(source,version,sourceVersion);
   throw error;
  }
 }
 async function retry(id){const version=generation,sourceVersion=++sourceGeneration;release();onSource({status:'loading',url:'',error:''});await consume(fetchSource(id),version,sourceVersion);}
 return{open,retry,cancel};
}

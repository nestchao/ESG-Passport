"use client";
import {useEffect,useMemo,useRef,useState} from 'react';
import Link from 'next/link';
import {ArrowLeft,FileText,Upload,ShieldCheck,AlertTriangle,LoaderCircle,CheckCircle2,ScanText,Download,RotateCcw,Info} from 'lucide-react';
import {parseBrowserBill,type BrowserOcrResult} from '../../browser-ocr-candidates.mjs';
import './ocr.css';

const types=['electricity','water','diesel','petrol','waste'] as const;
type Stage='idle'|'scanning'|'ready'|'failed';
const cap=10*1024*1024;
const required=(file:File)=>{
 if(file.size===0||file.size>cap)throw new Error('Select a non-empty file under 10 MB.');
 if(!['image/png','image/jpeg','application/pdf'].includes(file.type))throw new Error('Only PNG, JPEG or PDF documents are supported.');
};

export default function LiveOcr(){
 const [file,setFile]=useState<File|null>(null);
 const [url,setUrl]=useState('');
 const [category,setCategory]=useState('electricity');
 const [month,setMonth]=useState('2026-05');
 const [stage,setStage]=useState<Stage>('idle');
 const [progress,setProgress]=useState('');
 const [raw,setRaw]=useState('');
 const [draft,setDraft]=useState<BrowserOcrResult|null>(null);
 const [error,setError]=useState('');
 const [verified,setVerified]=useState(false);
 const [method,setMethod]=useState('');
 const [edited,setEdited]=useState(false);
 const input=useRef<HTMLInputElement|null>(null);
 const workerRef=useRef<{terminate:()=>Promise<unknown>}|null>(null);
 const alive=useRef(true);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;void workerRef.current?.terminate();};},[]);
 useEffect(()=>{if(!file){setUrl('');return;}const next=URL.createObjectURL(file);setUrl(next);return()=>URL.revokeObjectURL(next);},[file]);
 const reset=(newFile:File|null)=>{setFile(newFile);setStage('idle');setRaw('');setDraft(null);setProgress('');setError('');setVerified(false);setMethod('');setEdited(false);};
 const reparse=()=>{try{setDraft(parseBrowserBill(raw,category,month));setVerified(false);setEdited(false);setError('');}catch(e){setError(e instanceof Error?e.message:'Cannot parse text.');}};
 const scan=async()=>{
  if(!file||stage==='scanning')return;
  setStage('scanning');setError('');setRaw('');setDraft(null);setVerified(false);setProgress('Loading OCR engine…');
  let worker:null|Awaited<ReturnType<typeof import('tesseract.js')['createWorker']>>=null;
  try{
   required(file);
   let content='';let recognitionMethod='';
   const ocr=async(image:File|HTMLCanvasElement)=>{
    if(!worker){
     const {createWorker}=await import('tesseract.js');
     worker=await createWorker('eng',1,{logger:entry=>{if(alive.current&&entry.status==='recognizing text')setProgress(`Recognizing text: ${Math.round((entry.progress??0)*100)}%`);}});
     workerRef.current=worker;
    }
    const result=await worker.recognize(image);
    return result.data.text;
   };
   if(file.type==='application/pdf'){
    setProgress('Opening PDF in this browser…');
    const pdfjs=await import('pdfjs-dist');
    pdfjs.GlobalWorkerOptions.workerSrc='/ocr-assets/pdf.worker.min.mjs';
    const pdf=await pdfjs.getDocument({data:new Uint8Array(await file.arrayBuffer())}).promise;
    try{
     if(pdf.numPages>3)throw new Error('Use a PDF with three pages or fewer to limit browser memory usage.');
     let textPage=0,scannedPage=0;
     for(let n=1;n<=pdf.numPages;n++){
      if(!alive.current)throw new Error('OCR interrupted.');
      setProgress(`Reading page ${n} of ${pdf.numPages}…`);
      const page=await pdf.getPage(n);
      const embedded=await page.getTextContent();
      const embeddedText=embedded.items.map(item=>('str' in item ? item.str : '')).join(' ').trim();
      if(embeddedText.length>=35){content+=embeddedText+'\n';textPage++;}
      else{
       const view=page.getViewport({scale:1});const scale=Math.min(2.0,2600/Math.max(view.width,view.height));
       const viewport=page.getViewport({scale});
       const canvas=document.createElement('canvas');canvas.width=Math.ceil(viewport.width);canvas.height=Math.ceil(viewport.height);
       const context=canvas.getContext('2d',{willReadFrequently:true});
       if(!context)throw new Error('Your browser could not render this PDF page.');
       await page.render({canvasContext:context,viewport,canvas}).promise;
       setProgress(`Scanning PDF page ${n} of ${pdf.numPages}…`);
       content+=(await ocr(canvas))+'\n';canvas.width=0;canvas.height=0;scannedPage++;
      }
      page.cleanup();
     }
     recognitionMethod=scannedPage?`Tesseract.js (browser) on ${scannedPage} scanned page(s)${textPage?` + PDF text on ${textPage} page(s)`:''}`:'Embedded PDF text extraction (browser)';
    }finally{await pdf.destroy();}
   }else{
    setProgress('Scanning image on your device…');
    const image=await createImageBitmap(file);
    try{if(image.width*image.height>18_000_000)throw new Error('Image resolution is too large. Please resize below 18 megapixels.');}finally{image.close();}
    content=await ocr(file);
    recognitionMethod='Tesseract.js WebAssembly (browser)';
   }
   if(!alive.current)return;
   const result=parseBrowserBill(content,category,month);
   setRaw(content);setDraft(result);setMethod(recognitionMethod);setStage('ready');setProgress('Recognition complete. Review and correct every field.');
  }catch(e){if(alive.current){setError(e instanceof Error?e.message:'OCR could not read this file.');setStage('failed');}}
  finally{const active=workerRef.current;if(active){await active.terminate();workerRef.current=null;}}
 };
 const patch=(field:keyof BrowserOcrResult,value:string)=>{setDraft(old=>old?{...old,[field]:value,verified:false}:null);setVerified(false);setEdited(true);};
 const valid=useMemo(()=>!!draft&&!!draft.quantity&&!!draft.unit&&!!draft.period_start&&!!draft.period_end&&draft.period_start<=draft.period_end&&verified,[draft,verified]);
 const exportResult=()=>{
  if(!file||!draft||!valid)return;
  const safe={version:1,source:'browser-only OCR; not a verified ESG record',file_name:file.name,recognition_method:method,detected:{...draft,verified:true,rawText:raw},exported_at:new Date().toISOString()};
  const blob=new Blob([JSON.stringify(safe,null,2)],{type:'application/json'});
  const href=URL.createObjectURL(blob);const link=document.createElement('a');link.href=href;link.download='esg-ocr-review.json';link.click();URL.revokeObjectURL(href);
 };
 return <div className="bo-shell">
  <header className="bo-top"><Link href="/" className="bo-brand"><span className="bo-mark">✧</span> ESG Passport</Link><Link href="/" className="bo-back"><ArrowLeft size={17}/> Back to Records</Link></header>
  <main className="bo-main"><div className="bo-intro"><span className="bo-eyebrow"><ScanText size={16}/> REAL OCR · LOCAL BROWSER PROCESSING</span><h1>Scan an ESG document</h1><p>Read PNG, JPEG or PDF source documents with real OCR. Examine and correct the extracted fields before using the results. Your source image/PDF never goes to Supabase or the shared demo database.</p></div>
  <div className="bo-trust"><ShieldCheck size={20}/><span><b>Private on-device extraction.</b> OCR runs in your browser. Language models are downloaded when first used. Text and documents aren't sent to our backend by this scanner; closing the page clears them. This is a review tool, not a submitted ESG record.</span></div>
  <div className="bo-grid"><section className="bo-panel"><h2><Upload size={19}/> 1. Choose document</h2>
   <label>ESG document category<select value={category} disabled={stage==='scanning'} onChange={e=>{setCategory(e.target.value);if(raw){setDraft(null);setVerified(false);}}}>{types.map(t=><option key={t} value={t}>{t[0].toUpperCase()+t.slice(1)}</option>)}</select></label>
   <label>Reporting month<input type="month" value={month} disabled={stage==='scanning'} min="2020-01" max="2035-12" onChange={e=>{setMonth(e.target.value);if(raw){setDraft(null);setVerified(false);}}}/></label>
   <input ref={input} className="bo-native" type="file" accept="image/png,image/jpeg,application/pdf" disabled={stage==='scanning'} onChange={e=>{reset(e.target.files?.[0]??null);}}/>
   <button type="button" className="bo-drop" disabled={stage==='scanning'} onClick={()=>input.current?.click()}><FileText size={28}/><b>{file?.name??'Choose image or PDF'}</b><span>{file?`${(file.size/1024).toFixed(0)} KB`:'PNG · JPG · PDF · up to 10 MB (PDF max 3 pages)'}</span></button>
   <div className="bo-actions"><button type="button" className="bo-primary" onClick={scan} disabled={!file||stage==='scanning'}>{stage==='scanning'?<LoaderCircle className="bo-spin" size={17}/>:<ScanText size={17}/>} {stage==='scanning'?'Scanning…':'Run live OCR'}</button><button type="button" className="bo-secondary" onClick={()=>{reset(null);if(input.current)input.current.value='';}} disabled={stage==='scanning'}><RotateCcw size={16}/> Clear</button></div>
   {progress&&<div role="status" className="bo-progress">{progress}</div>}{error&&<div role="alert" className="bo-error"><AlertTriangle size={17}/>{error}</div>}
   <div className="bo-preview">{url?file?.type==='application/pdf'?<iframe src={url} title="Local PDF source preview"/>:<img alt="Your local source document" src={url}/>:<div className="bo-placeholder"><FileText size={35}/><span>Original document preview</span></div>}</div>
  </section>
  <section className="bo-panel"><h2><CheckCircle2 size={19}/> 2. Review candidate values</h2>
   {!draft&&<p className="bo-empty">Choose a file and run OCR. Detected text, quantities and dates will appear here for manual verification.</p>}
   {draft&&<><div className="bo-method">{method} · <b>Unverified OCR candidate</b>{edited?' · Manually edited':''}</div>
   <div className="bo-fields"><label>Supplier / document issuer<input value={draft.supplier} onChange={e=>patch('supplier',e.target.value)}/></label><label>Document date<input type="date" value={draft.document_date} onChange={e=>patch('document_date',e.target.value)}/></label><label>Quantity<input inputMode="decimal" value={draft.quantity} placeholder="Enter verified quantity" onChange={e=>patch('quantity',e.target.value)}/></label><label>Unit<select value={draft.unit} onChange={e=>patch('unit',e.target.value)}><option value="">Choose unit</option>{['kWh','m3','L','kg','t'].map(u=><option key={u} value={u}>{u}</option>)}</select></label><label>Period start<input type="date" value={draft.period_start} onChange={e=>patch('period_start',e.target.value)}/></label><label>Period end<input type="date" value={draft.period_end} onChange={e=>patch('period_end',e.target.value)}/></label></div>
   <label>Category / classification<input value={draft.category.replaceAll('_',' ')} readOnly/></label>
   {draft.notes.map((n,i)=><div className="bo-note" key={i}><Info size={16}/><span>{n}</span></div>)}
   {category==='waste'&&<div className="bo-error"><AlertTriangle size={17}/>A weighbridge transfer cannot automatically count as waste diverted, disposed or generated. The category must be verified with separate evidence.</div>}
   <label className="bo-checkbox"><input type="checkbox" checked={verified} onChange={e=>setVerified(e.target.checked)}/> I have checked the source and corrected the OCR values. This review applies only to my local export.</label>
   <button type="button" className="bo-primary" disabled={!valid} onClick={exportResult}><Download size={16}/> Export reviewed result as JSON</button>
   <p className="bo-small">Exports are local files; they do not create or approve an ESG Passport record. The protected staff workspace retains its own backend OCR + save/confirm workflow.</p></>}
  </section></div>
  <section className="bo-panel bo-text-panel"><div className="bo-text-heading"><h2>3. Recognized source text</h2><button type="button" className="bo-secondary" disabled={!raw||stage==='scanning'} onClick={reparse}>Re-extract candidates from edited text</button></div><textarea value={raw} spellCheck={false} placeholder="OCR text will appear here after scanning. You can edit incorrect characters and re-extract candidates." onChange={e=>{setRaw(e.target.value);setVerified(false);setDraft(null);}} rows={11}/></section>
  <div className="bo-bottom"><Link href="/">← Return to original ESG Passport</Link><span>English / Latin-script document OCR · Review before using any claim</span></div>
  </main></div>;
}

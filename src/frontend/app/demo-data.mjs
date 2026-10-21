/* Browser-only UI fixtures. There is no network API, OCR or live AI in this build. */
const PERIOD='2026-09';
const clone=value=>structuredClone(value);
const now=()=>new Date().toISOString();
const id=prefix=>`${prefix}-${crypto.randomUUID()}`;
const titles={'E1.1':'Direct emissions','E1.2':'Electricity emissions','E2.1':'Energy consumption','E3.1':'Water withdrawn','E4.1':'Waste management','S1.1':'Labour incidents','S4.1':'Health & safety','G1.1':'Company directors','G2.1':'Policies in place','G3.1':'Financial reporting','G4.1':'Corruption incidents'};
const factors=[
  {id:'grid-v1',name:'Peninsular grid',value:.740,unit:'kg CO₂e/kWh',year:2024,version:'grid-v1',source:'https://myenergystats.st.gov.my/documents/d/guest/grid-emission-factor-gef-in-malaysia-2022-2024-provisional-',assumptions:'2024 provisional factor; Peninsular Malaysia grid basis.'},
  {id:'diesel-v1',name:'Mineral diesel proxy',value:2.66155,unit:'kg CO₂e/L',year:2025,version:'diesel-v1',source:'https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2025',assumptions:'Mineral-fuel proxy; no biodiesel adjustment.'},
  {id:'diesel-energy-v1',name:'Diesel energy proxy',value:2.66155/.26808,unit:'kWh/L',year:2025,version:'diesel-energy-v1',source:'https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2025',assumptions:'Derived mineral-fuel proxy; illustrative browser arithmetic.'},
  {id:'petrol-v1',name:'Mineral petrol proxy',value:2.33984,unit:'kg CO₂e/L',year:2025,version:'petrol-v1',source:'https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2025',assumptions:'Petrol energy factor unavailable.'},
];
function seed(){
  const samples=[['electricity','electricity','Electricity bill — September','1000','kWh',false],['diesel','diesel','Diesel receipt — September','100','L',true],['water','water','Purchased water bill — September','10','m3',true],['waste-generated','waste_generated','Waste generated record','100','kg',true],['waste-diverted','waste_diverted','Recycler collection slip','80','kg',true],['waste-disposed','waste_disposed','Waste disposal slip','20','kg',true]];
  const documents=samples.map(([slug,category,name,quantity,unit,confirmed])=>{
    const activities=[{category,quantity,unit,period_start:'2026-09-01',period_end:'2026-09-30',estimated:false,source_reference:'Synthetic quantity line',confirmed_by:confirmed?'Admin clerk':'',confirmed_at:confirmed?now():null}];
    const extraction={supplier_name:'Sample Utilities / Services',document_date:'2026-09-30',period_start:'2026-09-01',period_end:'2026-09-30',activities:clone(activities),uncertainty_notes:['Sample source record. Check all quantities before confirmation.']};
    return {id:`doc-${slug}`,name:`${name}.svg`,type:category.startsWith('waste')?'waste':category,period:PERIOD,confirmed,version:1,activities,extraction,original_extraction:clone(extraction),uploaded_at:now(),uploaded_by:'Admin clerk'};
  });
  const answers={'S1.1':{count:0,description:'No incidents reported in the synthetic month.'},'S4.1':{injuries:0,fatalities:0,description:'No injuries or fatalities reported.'},'G1.1':{directors:2},'G2.1':{policies:[{name:'Code of Conduct',status:'in place'},{name:'Anti-Corruption Policy',status:'not in place'},{name:'Whistleblowing Policy',status:'not in place'},{name:'Health and Safety Policy',status:'in place'}]},'G3.1':{year:2025},'G4.1':{count:0,description:'No confirmed corruption incidents reported.'}};
  const declarations=Object.entries(answers).map(([code,answer])=>({id:code,code,answer,period:PERIOD,declared_by:'Mr Lim',declared_at:now(),evidence_ids:[],complete:true,version:1}));
  const requests=[['Meridian Foods',['What are your Scope 2 electricity emissions?','How much water did you use?','How many directors does your company have?','What are your Scope 3 emissions?']],['Northstar Packaging',['Please disclose carbon emissions from purchased electricity.','State your purchased water volume.','List the number of company directors.']]].map(([customer,texts],i)=>({id:`request-${i+1}`,customer,period:PERIOD,due_date:'2026-10-23',status:'draft',version:1,questions:texts.map((text,j)=>({id:`request-${i+1}-q${j}`,text,codes:[],proposed_codes:[],reviewed:false,version:1,rationale:'Awaiting matching',manual_answer:null}))}));
  return {company:{name:'Lim Carton Industries',location:'Shah Alam',synthetic:true},documents,declarations,requests,shares:[],events:[{id:id('event'),action:'workspace_opened',actor:'System',role:'owner',time:now(),summary:'Sample workspace loaded.'}]};
}
function profile(state){
  const activity=category=>{
    const docs=state.documents.filter(d=>d.activities.some(a=>a.category===category));
    const rows=docs.filter(d=>d.confirmed).flatMap(d=>d.activities.filter(a=>a.category===category&&a.period_start?.slice(0,7)===PERIOD));
    return {value:rows.length?rows.reduce((sum,a)=>sum+Number(a.quantity)*(a.unit==='m3'?1000:a.unit==='t'?1000:1),0):null,ids:docs.filter(d=>d.confirmed).map(d=>d.id),pending:docs.some(d=>!d.confirmed),estimated:rows.some(a=>a.estimated)};
  };
  const electricity=activity('electricity'),diesel=activity('diesel'),petrol=activity('petrol'),water=activity('water');
  const metric=(code,value,unit,badge,evidence_ids,method,usedFactors=[],components=[])=>({code,title:titles[code],value,unit,badge,evidence_ids,method,factors:usedFactors,components,complete:value!==null&&['auto','declared'].includes(badge),confirmed_by:'Confirmed record'});
  const metricValue=(a,multiplier=1)=>a.pending||a.value===null?null:a.value*multiplier;
  const eValue=metricValue(electricity),dValue=metricValue(diesel),pValue=metricValue(petrol);
  const fuelMissing=(diesel.pending||petrol.pending)||(dValue===null&&pValue===null);
  const emissions=fuelMissing?null:(dValue??0)*factors[1].value+(pValue??0)*factors[3].value;
  const fuelEnergy=dValue===null?null:dValue*factors[2].value;
  const energy=eValue===null||fuelEnergy===null||pValue!==null?null:eValue+fuelEnergy;
  const metrics=[
    metric('E1.1',emissions,'kg CO₂e',emissions===null?'missing':'estimated',[...diesel.ids,...petrol.ids],'Illustrative confirmed litres × versioned mineral-fuel proxy.',[factors[1],...(pValue!==null?[factors[3]]:[])]),
    metric('E1.2',eValue===null?null:eValue*.740,'kg CO₂e',eValue===null?'missing':electricity.estimated?'estimated':'auto',electricity.ids,'Confirmed kWh × 0.740 kg CO₂e/kWh. No annual extrapolation.',[factors[0]]),
    metric('E2.1',energy,'kWh',energy===null?'missing':'estimated',[...electricity.ids,...diesel.ids],'Electricity plus diesel energy proxy. Petrol energy unavailable.',[factors[2]],[{name:'Electricity',value:eValue,unit:'kWh'},{name:'Fuel',value:fuelEnergy,unit:'kWh'}]),
    metric('E3.1',metricValue(water),'L',water.pending||water.value===null?'missing':water.estimated?'estimated':'auto',water.ids,'Purchased water: m³ × 1,000 = litres.'),
  ];
  const waste=['waste_generated','waste_diverted','waste_disposed'].map(category=>({category,...activity(category)}));
  const wasteMissing=waste.some(a=>a.value===null||a.pending);
  metrics.push(metric('E4.1',wasteMissing?null:waste[0].value/1000,'t',wasteMissing?'missing':waste.some(a=>a.estimated)?'estimated':'auto',[...new Set(waste.flatMap(a=>a.ids))],'kg ÷ 1,000. Generated waste is not added to diverted/disposed waste.',[],waste.map(a=>({name:a.category.replace('waste_',''),value:a.value===null?null:a.value/1000,unit:'t'}))));
  for(const [code] of Object.entries(titles).filter(([code])=>!code.startsWith('E'))){
    const declaration=state.declarations.find(d=>d.code===code),answer=declaration?.answer;
    const value=!declaration?.complete?null:code==='G1.1'?answer.directors:code==='G3.1'?answer.year:answer;
    metrics.push(metric(code,value,code==='G1.1'?'directors':'',value===null?'missing':'declared',declaration?.evidence_ids||[],'Owner declaration for the synthetic reporting month; not independently verified.'));
  }
  const breakdown={complete:0,partial:0,estimated:0,missing:0};
  for(const m of metrics){if(m.complete)breakdown.complete++;else if(m.badge==='estimated')breakdown.estimated++;else if(m.components.some(c=>c.value!==null))breakdown.partial++;else breakdown.missing++;}
  return {company:state.company,period:PERIOD,metrics,factors,readiness:{complete:breakdown.complete,total:11,percent:breakdown.complete/11*100,breakdown},gaps:metrics.filter(m=>!m.complete).map(m=>({code:m.code,title:m.title,badge:m.badge,reason:m.badge==='estimated'?'Estimated proxy; not complete.':m.components.some(c=>c.value!==null)?'Partial data available.':'Evidence or review is missing.'}))};
}
function renderRequest(state,request){
  const metrics=profile(state).metrics;
  return {...clone(request),questions:request.questions.map(q=>{
    const selected=(q.codes||[]).map(code=>metrics.find(m=>m.code===code)).filter(Boolean);
    const answer=!q.reviewed?'Not available — confirm this mapping first.':q.manual_answer||(!selected.length?'Not available — outside supported disclosures.':selected.map(m=>`${PERIOD} · Partial-year · ${m.code} ${m.title}: ${m.value===null?'Not available':typeof m.value==='object'?JSON.stringify(m.value):m.code==='E1.1'||m.code==='E1.2'?(m.value/1000).toFixed(3)+' t CO₂e':`${m.value} ${m.unit}`}.`).join('\n'));
    const badge=!q.reviewed?'missing':q.manual_answer?'declared':!selected.length||selected.some(m=>m.badge==='missing')?'missing':selected.some(m=>m.badge==='estimated')?'estimated':selected.every(m=>m.badge==='declared')?'declared':'auto';
    return {...clone(q),answer,badge,metrics:q.reviewed?clone(selected):[],evidence_ids:q.reviewed?[...new Set(selected.flatMap(m=>m.evidence_ids))]:[]};
  })};
}
function match(text){
  const t=text.toLowerCase();if(/scope\s*3/.test(t))return [];
  const codes=[];
  if(/electricity|scope\s*2|purchased.*emission/.test(t))codes.push('E1.2');
  if(/diesel|petrol|scope\s*1|direct.*emission/.test(t))codes.push('E1.1');
  if(/energy|kwh/.test(t))codes.push('E2.1');if(/water/.test(t))codes.push('E3.1');if(/waste/.test(t))codes.push('E4.1');
  if(/child|forced|labour|labor/.test(t))codes.push('S1.1');if(/injur|fatal|safety/.test(t))codes.push('S4.1');
  if(/director|board/.test(t))codes.push('G1.1');if(/polic/.test(t))codes.push('G2.1');if(/audit|financial/.test(t))codes.push('G3.1');if(/corrupt|brib/.test(t))codes.push('G4.1');return codes;
}
export function createDemo({load=async()=>null,save=async()=>{}}={}){
  let state,initializing;
  const ready=async()=>{if(!state)await(initializing??=(async()=>{state=await load()||seed();
      for(const doc of state.documents){
        if(doc.file)continue;
        for(const record of [doc.extraction,doc.original_extraction].filter(Boolean)){
          if(record.supplier_name==='Demo Utilities / Services')record.supplier_name='Sample Utilities / Services';
          record.uncertainty_notes=record.uncertainty_notes?.map(note=>note==='Prepared fixture for UI demonstration; check before confirmation.'?'Sample source record. Check all quantities before confirmation.':note);
        }
        if(doc.uploaded_by==='Demo clerk')doc.uploaded_by='Admin clerk';
        for(const activity of doc.activities||[])if(activity.confirmed_by==='Demo clerk')activity.confirmed_by='Admin clerk';
      }
    })());};
  const log=(action,role,target)=>state.events.unshift({id:id('event'),action,role,actor:role==='owner'?'Mr Lim':'Admin clerk',target,time:now(),summary:'Workspace updated.'});
  const invalidate=()=>state.requests.forEach(r=>{r.version++;r.status='draft';r.questions.forEach(q=>{q.reviewed=false;q.version++;});});
  const document=(documentId)=>{const doc=state.documents.find(d=>d.id===documentId);if(!doc)throw Error('Record not found.');return doc;};
  const requestById=requestId=>{const r=state.requests.find(r=>r.id===requestId);if(!r)throw Error('Request not found.');return r;};
  async function request(path,options={},role='owner'){
    await ready();const parts=path.split('?')[0].split('/').filter(Boolean),method=options.method||'GET';
    const body=typeof options.body==='string'?JSON.parse(options.body||'{}'):{};
    const owner=()=>{if(role!=='owner')throw Error('Only the Owner can approve or save owner declarations in this workspace.');};
    if(role==='customer'&&parts[0]!=='shares')throw Error('Customer preview contains approved packs only.');
    let result;
    if(parts[0]==='profile')result=profile(state);
    else if(parts[0]==='documents'){
      if(parts.length===1&&method==='GET')result=state.documents.map(({file,...doc})=>clone(doc));
      else if(parts.length===1){
        const file=options.body?.get('file'),type=options.body?.get('type');
        if(!(file instanceof Blob)||!file.size||file.size>10*1024*1024||!['image/jpeg','image/png','application/pdf'].includes(file.type))throw Error('Choose a JPEG, PNG or single-page PDF up to 10 MB. Files stay in this browser.');
        if(!['electricity','diesel','petrol','water','waste'].includes(type))throw Error('Select a supported category.');
        const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await file.arrayBuffer()))).map(n=>n.toString(16).padStart(2,'0')).join('');
        if(state.documents.some(d=>d.hash===hash))throw Error('This file is already in your records.');
        const doc={id:id('doc'),name:file.name,type,mime_type:file.type,period:PERIOD,file,hash,confirmed:false,version:1,activities:[],extraction:null,original_extraction:null};state.documents.push(doc);result={...doc,file:undefined};log('local_file_added',role,doc.id);
      }else{
        const doc=document(parts[1]);
        if(parts[2]==='extract'){
          if(body.mode==='timeout')throw Error('Document processing timed out. Enter the quantities manually.');
          if(doc.file)doc.extraction={activities:[{category:doc.type==='waste'?'waste_generated':doc.type,quantity:'',unit:({electricity:'kWh',diesel:'L',petrol:'L',water:'m3',waste:'kg'})[doc.type],period_start:'2026-09-01',period_end:'2026-09-30',estimated:false,source_reference:'Manual entry required'}],uncertainty_notes:['Enter this file’s quantities manually. Automatic reading is not connected.']};
          else doc.extraction=clone(doc.original_extraction);
          doc.version++;result=clone({...doc,file:undefined});log('fixture_preview',role,doc.id);
        }else if(parts[2]==='activities'){
          if(!Array.isArray(body.activities)||!body.activities.length||typeof body.confirmed!=='boolean')throw Error('Add at least one quantity.');
          const units={electricity:['kWh'],diesel:['L'],petrol:['L'],water:['m3','L'],waste_generated:['kg','t'],waste_diverted:['kg','t'],waste_disposed:['kg','t']};
          for(const a of body.activities){if(a.quantity===''||!Number.isFinite(Number(a.quantity))||Number(a.quantity)<0||!units[a.category]?.includes(a.unit))throw Error('Enter a non-negative quantity and a supported unit.');if(!a.period_start||!a.period_end||a.period_start>a.period_end)throw Error('Check the reporting dates.');if(a.period_start.slice(0,7)!==a.period_end.slice(0,7)&&(!a.estimated||!a.assumptions||!a.allocated_period))throw Error('Cross-month quantities need an allocation and an estimation method.');}
          if(new Set(body.activities.map(a=>a.category)).size!==body.activities.length)throw Error('Use one total per category per document.');
          doc.activities=clone(body.activities).map(a=>({...a,confirmed_by:body.confirmed?role==='owner'?'Mr Lim':'Admin clerk':'',confirmed_at:body.confirmed?now():null}));doc.confirmed=body.confirmed;doc.version++;invalidate();result=clone({...doc,file:undefined});log(body.confirmed?'activity_confirmed':'draft_saved',role,doc.id);
        }else result=clone({...doc,file:undefined});
      }
    }else if(parts[0]==='declarations'){
      if(method==='GET')result=clone(state.declarations);
      else{owner();if(!titles[parts[1]]||parts[1].startsWith('E'))throw Error('Unsupported declaration.');const answer=body.answer||{};if(Object.values(answer).some(v=>typeof v==='number'&&(!Number.isFinite(v)||v<0)))throw Error('Declaration counts must be non-negative.');const old=state.declarations.find(d=>d.code===parts[1]);const complete=parts[1]==='G2.1'?answer.policies?.length>0&&answer.policies.every(p=>['in place','not in place'].includes(p.status)):Object.keys(answer).length>0&&Object.values(answer).every(v=>v!==''&&v!==null);const declaration={id:parts[1],code:parts[1],period:PERIOD,answer,evidence_ids:body.evidence_ids||[],complete,declared_by:'Mr Lim',declared_at:now(),version:(old?.version||0)+1};state.declarations=state.declarations.filter(d=>d.code!==parts[1]);state.declarations.push(declaration);invalidate();result=declaration;log('declaration_saved',role,parts[1]);}
    }else if(parts[0]==='questionnaires'){
      if(parts.length===1&&method==='GET')result=state.requests.map(r=>renderRequest(state,r));
      else if(parts.length===1){if(!body.customer?.trim()||!body.questions?.length)throw Error('Enter a customer and at least one question.');const r={id:id('request'),customer:body.customer,period:PERIOD,due_date:body.due_date,status:'draft',version:1,questions:body.questions.map(text=>({id:id('question'),text,codes:[],proposed_codes:[],reviewed:false,version:1}))};state.requests.push(r);result=renderRequest(state,r);log('questionnaire_created',role,r.id);}
      else{
        const r=requestById(parts[1]);
        if(parts[2]==='map'){if(body.mode==='timeout')throw Error('Matching timed out. Choose disclosures manually or retry.');r.questions.forEach(q=>Object.assign(q,{proposed_codes:match(q.text),codes:[],reviewed:false,manual_answer:null,rationale:'Suggested from the question wording. Confirm or correct the disclosure.',uncertainty:'Wording-based suggestion; human confirmation required.',version:q.version+1}));r.status='draft';r.version++;log('fixture_mapping',role,r.id);}
        else if(parts[2]==='approve-share'){
          owner();if(body.version!==r.version)throw Error('The draft changed. Reopen it before approving.');if(!r.questions.length||r.questions.some(q=>!q.reviewed))throw Error('Review every question before sharing.');if(!body.recipient?.trim())throw Error('Enter a recipient.');
          const selected=[...new Set(body.selected_evidence_ids||[])];const evidence=selected.map(e=>clone(document(e)));
          const pack={token:id('demo'),recipient:body.recipient,approved_by:'Mr Lim',created_at:now(),snapshot:{company:clone(state.company),period:PERIOD,recipient:body.recipient,approved_by:'Mr Lim',approved_at:now(),questions:renderRequest(state,r).questions,selected_evidence_ids:selected,evidence}};
          state.shares.push(pack);r.status='shared';r.version++;result=clone(pack);log('demo_pack_approved',role,r.id);
        }else if(method==='PUT'){if(r.questions.some(q=>!q.reviewed))throw Error('Confirm every mapping before handing off.');r.status='ready_for_owner';r.version++;log('ready_for_owner',role,r.id);}
        result??=renderRequest(state,r);
      }
    }else if(parts[0]==='questions'){
      const r=state.requests.find(r=>r.questions.some(q=>q.id===parts[1]));if(!r)throw Error('Question not found.');const q=r.questions.find(q=>q.id===parts[1]);if(!Array.isArray(body.codes)||body.codes.some(c=>!titles[c]))throw Error('Choose supported disclosures.');if(body.manual_answer)owner();Object.assign(q,{codes:body.codes,reviewed:!!body.reviewed,manual_answer:body.manual_answer||null,version:q.version+1});r.status='draft';r.version++;result=clone(q);log('question_reviewed',role,q.id);
    }else if(parts[0]==='shares'){
      if(parts.length===1){owner();result=clone(state.shares);}
      else{const pack=state.shares.find(s=>s.token===parts[1]);if(!pack)throw Error('Pack not found. Local links work only in the browser and website address where the pack was created.');result=clone(pack);log('pack_viewed',role,pack.token);}
    }else if(parts[0]==='activity-log')result=clone(state.events);
    else if(parts[0]==='demo'&&parts[1]==='reset'){owner();state=seed();result={reset:true};}
    else throw Error('This action is not supported.');
    if(method!=='GET'||parts[0]==='shares'&&parts.length>1)await save(clone(state));
    return clone(result);
  }
  async function preview(documentId,token){await ready();const doc=token?state.shares.find(s=>s.token===token)?.snapshot.evidence.find(d=>d.id===documentId):document(documentId);if(!doc)throw Error('This record was not included in the approved pack.');return URL.createObjectURL(doc.file||new Blob([billSvg(doc)],{type:'image/svg+xml'}));}
  return {request,preview};
}
function billSvg(doc){
  const escape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
  const rows=[doc.name,'Lim Carton Industries (fictional)','Shah Alam, Selangor','Period: 01–30 September 2026',...(doc.original_extraction?.activities||doc.activities).map(a=>`${a.category}: ${a.quantity} ${a.unit}`),'Sample evidence for the starting workspace.','Not a real bill.'];
  return `<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1000" viewBox="0 0 900 1000"><rect width="900" height="1000" fill="#f5f8f7"/><rect width="900" height="150" fill="#123c35"/><text x="45" y="85" fill="white" font-family="Arial" font-size="30">SAMPLE SOURCE RECORD</text>${rows.map((text,i)=>`<text x="45" y="${220+i*65}" fill="#172d28" font-family="Arial" font-size="23">${escape(text)}</text>`).join('')}</svg>`;
}
async function browserStorage(mode,value){
  if(typeof indexedDB==='undefined')return null;
  return new Promise(resolve=>{const opening=indexedDB.open('esg-passport-ui',1);opening.onupgradeneeded=()=>opening.result.createObjectStore('demo');opening.onerror=()=>resolve(null);opening.onsuccess=()=>{const db=opening.result;const transaction=db.transaction('demo',mode==='read'?'readonly':'readwrite');const operation=mode==='read'?transaction.objectStore('demo').get('workspace'):transaction.objectStore('demo').put(value,'workspace');let result=null;operation.onsuccess=()=>{result=operation.result;};transaction.oncomplete=()=>{db.close();resolve(result);};transaction.onerror=transaction.onabort=()=>{db.close();resolve(null);};};});
}
const demo=createDemo({load:()=>browserStorage('read'),save:value=>browserStorage('write',value)});
export const demoRequest=async(path,options,role)=>{
  const result=await demo.request(path,options,role);
  if(result?.snapshot?.evidence)for(const doc of result.snapshot.evidence)doc.preview_url=await demo.preview(doc.id,result.token);
  return result;
};
export const demoPreview=(documentId,token)=>demo.preview(documentId,token);

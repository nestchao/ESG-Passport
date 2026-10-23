'use client';

import { DesktopOverview, FlowSteps } from './desktop-overview';
import { reviewSummary } from './workflow.mjs';
import { DeclarationSummary } from './declaration-summary';
import { DraftAnswer } from './draft-answer';
import { RoleSwitcher } from './role-switcher';
import { customerPortalMessage } from './presentation.mjs';
import { replaceRequest, saveQuestionReview, loadApproval } from './request-updates.mjs';
import { apiRequest, apiPreview } from './api-client.mjs';
import { RecordFields } from './record-fields-form';
import { normaliseActivities, validateActivities, categoryLabel, cleanDecimal, reclassifyActivities } from './record-fields.mjs';
import { approvalKey, declarationKey, questionDraftChanged, createDraftNavigator, warnBeforeUnload } from './draft-state.mjs';
import { reloadRequestContext, recommendedEvidence, retainEvidenceSelection, packQuestionEvidence, createAndMatchRequest } from './review-recovery.mjs';
import { UnsavedChangesDialog } from './unsaved-changes-dialog';
import { EvidenceSelector } from './evidence-selector';
import { RequestRecoveryNotice } from './request-recovery-notice';
import { MetricAvailability } from './metric-availability';
import { DEFAULT_PERIOD, isValidPeriod, monthBounds, monthLabel, previousMonth, selectedPeriod, periodSearch, periodPath, recordDraftKey, validateRecordMetadata, defaultDeclaration } from './monthly.mjs';
import { RecordMetadataFields } from './record-metadata-fields';
import { PolicyEditor } from './policy-editor';
import { hydrateEvidence } from './evidence-catalog.mjs';
import { replaceDeclaration } from './declaration-updates.mjs';
import { createWorkspaceLoader, type WorkspaceSection, type WorkspaceSectionState } from './workspace-loading.mjs';
import { createEvidenceLoader, type SourceState } from './evidence-loading.mjs';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowDownToLine, ArrowRight, ArrowUpRight, BarChart3, BookOpen, Check, CheckCircle2, ChevronDown, ChevronRight, CircleHelp, ClipboardCheck, Clock3, FileText, FolderOpen, History, Leaf, Link2, LoaderCircle, LockKeyhole, Menu, Plus, RefreshCw, Send, ShieldCheck, Sparkles, Upload, X, Zap, Droplets, Fuel, Recycle, Building2, ExternalLink, Eye, AlertTriangle } from 'lucide-react';


type Role = 'owner'|'clerk'|'customer';
type Tab = 'Overview'|'Evidence'|'Declarations'|'Customer requests'|'Activity log'|'Factor register';
type Json = Record<string, any>;
type Metric = {code:string;title:string;value:any;unit:string;badge:string;evidence_ids:string[];method:string;factors:Json[];complete:boolean;components?:Json[];confirmed_by?:string|string[]};
const codes = ['E1.1','E1.2','E2.1','E3.1','E4.1','S1.1','S4.1','G1.1','G2.1','G3.1','G4.1'];
const titles:Record<string,string> = {'E1.1':'Direct emissions','E1.2':'Electricity emissions','E2.1':'Energy consumption','E3.1':'Water withdrawn','E4.1':'Waste management','S1.1':'Labour incidents','S4.1':'Health & safety','G1.1':'Company directors','G2.1':'Policies in place','G3.1':'Financial reporting','G4.1':'Corruption incidents'};
const nav = [{name:'Overview',label:'Overview',icon:BarChart3},{name:'Evidence',label:'Records',icon:FolderOpen},{name:'Customer requests',label:'Customer requests',icon:Send}] as const;
const secondaryNav = [{name:'Declarations',icon:ClipboardCheck},{name:'Activity log',icon:History},{name:'Factor register',icon:BookOpen}] as const;
const initials = (name:string) => name.split(' ').map(s=>s[0]).slice(0,2).join('');
const humanDate = (date:string) => date ? new Intl.DateTimeFormat('en-MY',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Kuala_Lumpur'}).format(new Date(date)) : '—';
function number(value:any, digits=2) { if (value == null || value === '') return '—'; if(typeof value==='object') return Object.entries(value).map(([k,v])=>`${k}: ${typeof v==='object'?JSON.stringify(v):v}`).join(' · '); const n=Number(value); return Number.isFinite(n)?n.toLocaleString('en-MY',{maximumFractionDigits:digits}):String(value); }
function Badge({value}:{value:string}) { return <span className={`badge ${value?.replaceAll(' ','_')}`}><i/>{value==='auto'?'Calculated':value==='declared'?'Owner declared':value==='estimated'?'Estimated':value==='missing'?'Missing':value?.replaceAll('_',' ')}</span>; }

export default function Home() {
  const [selectedMonth,setSelectedMonth]=useState<string>(DEFAULT_PERIOD);
  const activeMonth=useRef(selectedMonth);activeMonth.current=selectedMonth;
  const [periodReady,setPeriodReady]=useState(false);
  const [recordView,setRecordView]=useState<'active'|'archived'>('active');
  const [archivedDocuments,setArchivedDocuments]=useState<Json[]>([]);
  const [archiveLoading,setArchiveLoading]=useState(false);
  const [archiveError,setArchiveError]=useState('');
  const [archiveRetry,setArchiveRetry]=useState(0);
  const [archiveTarget,setArchiveTarget]=useState<Json|null>(null);
  const [duplicateRecord,setDuplicateRecord]=useState<Json|null>(null);
  const [pendingOpen,setPendingOpen]=useState<Json|null>(null);
  const [documentMeta,setDocumentMeta]=useState({name:'',period:DEFAULT_PERIOD as string,type:'electricity'});
  const documentMetaInitial=useRef({name:'',period:DEFAULT_PERIOD as string,type:'electricity'});
  const [recordConflict,setRecordConflict]=useState(false);
  const [declDocuments,setDeclDocuments]=useState<Json[]>([]);
  const [requestDocuments,setRequestDocuments]=useState<Json[]>([]);
  const [evidenceCatalogLoading,setEvidenceCatalogLoading]=useState(false);
  const [evidenceCatalogError,setEvidenceCatalogError]=useState('');
  const [catalogRetry,setCatalogRetry]=useState(0);
  const [previousPolicy,setPreviousPolicy]=useState<Json|null>(null);
  const [previousPolicyLoading,setPreviousPolicyLoading]=useState(false);
  const [previousPolicyError,setPreviousPolicyError]=useState('');
  useEffect(()=>{setSelectedMonth(selectedPeriod(window.location.search));setPeriodReady(true);},[]);
  const [tab,setTab] = useState<Tab>('Overview');
  const [role,setRole] = useState<Role>('owner');
  const activeRole = useRef<Role>(role);
  activeRole.current=role;
  const [historyLoading,setHistoryLoading] = useState(false);
  const [historyRetry,setHistoryRetry] = useState(0);
  const [profile,setProfile] = useState<Json|null>(null);
  const [documents,setDocuments] = useState<Json[]>([]);
  const [declarations,setDeclarations] = useState<Json[]>([]);
  const [requests,setRequests] = useState<Json[]>([]);
  const [events,setEvents] = useState<Json[]>([]);
  const [shares,setShares] = useState<Json[]>([]);
  const [loading,setLoading] = useState(true);
  const [retry,setRetry] = useState(0);
  const workspaceLoader=useRef(createWorkspaceLoader());
  const workspaceEpoch=useRef(0);
  const [sectionStates,setSectionStates]=useState<Partial<Record<WorkspaceSection,WorkspaceSectionState&{hasData?:boolean}>>>({});
  const [busy,setBusy] = useState('');
  const [error,setError] = useState('');
  const [notice,setNotice] = useState('');
  const [unsavedOpen,setUnsavedOpen] = useState(false);
  const [requestConflict,setRequestConflict] = useState(false);
  const [requestEditorEpoch,setRequestEditorEpoch] = useState(0);
  const [recordErrors,setRecordErrors] = useState<Record<string,string>>({});
  const recordInitial=useRef<Json[]>([]);
  const declarationInitial=useRef<{answer:Json;evidence:string[]}>({answer:{},evidence:[]});
  const approvalInitial=useRef<{recipient:string;evidence:string[]}>({recipient:'',evidence:[]});
  const [modal,setModal] = useState<string|null>(null);
  const [detail,setDetail] = useState<Json|null>(null);
  const [token,setToken] = useState('');
  const [pack,setPack] = useState<Json|null>(null);
  const [mobile,setMobile] = useState(false);
  const [query,setQuery] = useState('');
  const [recipient,setRecipient] = useState('');
  const [dirtyQuestions,setDirtyQuestions] = useState<string[]>([]);
  const [questionDrafts,setQuestionDrafts] = useState<Record<string,{codes:string[];manual:string}>>({});
  const [dueDate,setDueDate] = useState('');
  const [selectedEvidence,setSelectedEvidence] = useState<string[]>([]);
  const [activityRows,setActivityRows] = useState<Json[]>([]);
  const [fileUrl,setFileUrl] = useState('');
  const [sourceState,setSourceState]=useState<SourceState>({status:'idle',url:'',error:''});
  const evidenceLoader=useRef<ReturnType<typeof createEvidenceLoader>|null>(null);
  const evidenceHandlers=useRef<any>(null);
  evidenceHandlers.current={apiAction:(id:string)=>apiRequest(`/documents/${encodeURIComponent(id)}`,{},role),preview:(id:string)=>apiPreview(id,role),onDetails:(d:Json,context:any)=>{
    if(context.role!==activeRole.current||context.period!==activeMonth.current)return;
    const extraction=d.extraction||{};
    const sourceRows=d.activities?.length?d.activities:extraction.activities||extraction.quantities||[];
    const month=d.period||selectedMonth;
    const bounds=monthBounds(month);
    const rows=normaliseActivities(sourceRows.length?sourceRows:[{category:d.type==='waste'?'waste_generated':d.type||'electricity',quantity:'',unit:d.type==='water'?'m3':d.type==='electricity'?'kWh':d.type==='waste'?'kg':'L',period_start:bounds.start,period_end:bounds.end,estimated:false,assumptions:''}]);
    recordInitial.current=structuredClone(rows);documentMetaInitial.current={name:d.name,period:month,type:d.type};setDocumentMeta({name:d.name,period:month,type:d.type});setRecordConflict(false);setActivityRows(rows);setRecordErrors({});setDetail(d);setRequestReturn(context.parent);setTab('Evidence');setModal('document');
  }};
  if(!evidenceLoader.current)evidenceLoader.current=createEvidenceLoader({details:id=>evidenceHandlers.current.apiAction(id),preview:id=>evidenceHandlers.current.preview(id),onDetails:(d,context)=>evidenceHandlers.current.onDetails(d,context),onSource:state=>{setSourceState(state);setFileUrl(state.url);},revoke:url=>URL.revokeObjectURL(url)});
  useEffect(()=>{if(modal!=='document'){evidenceLoader.current?.cancel();setFileUrl('');setSourceState({status:'idle',url:'',error:''});}},[modal,role]);
  useEffect(()=>()=>evidenceLoader.current?.cancel(),[]);
  const [declCode,setDeclCode] = useState('S1.1');
  const [declAnswer,setDeclAnswer] = useState<Json>({count:0,description:'No incidents reported for the selected period.'});
  const [declEvidence,setDeclEvidence] = useState<string[]>([]);
  const [declErrors,setDeclErrors] = useState('');
  const [newCustomer,setNewCustomer] = useState('');
  const [newQuestions,setNewQuestions] = useState('');
  const [sourceType,setSourceType] = useState('electricity');
  const [pendingFile,setPendingFile] = useState<File|null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const workspaceScreen = !!modal && ['upload','document','new-request','request','owner-review','pack'].includes(modal);
  const isDialog = !!modal && !workspaceScreen;
  const review = reviewSummary(detail?.questions || [], dirtyQuestions);
  const [requestReturn,setRequestReturn] = useState<{request:Json;stage:string}|null>(null);
  const screenTitle = modal==='archive-record'?'Archive record':modal==='upload'?'Add your supporting records':modal==='document'?'Check record data':modal==='new-request'?'Prepare a customer request':modal==='request'?'Review every answer':modal==='owner-review'?(role==='clerk'?'Send prepared answers to owner':'Review & approve sharing'):modal==='pack'?'Customer pack':'';
  useEffect(()=>{if(workspaceScreen)window.scrollTo({top:0,behavior:'instant'});},[modal,workspaceScreen]);
  const documentDirty=modal==='document'&&recordDraftKey({...documentMeta,activities:activityRows})!==recordDraftKey({...documentMetaInitial.current,activities:recordInitial.current});
  const declarationDirty=modal==='declaration'&&declarationKey(declAnswer,declEvidence)!==declarationKey(declarationInitial.current.answer,declarationInitial.current.evidence);
  const inRequest=modal==='request'||modal==='owner-review'||!!requestReturn;
  const approvalDirty=inRequest&&approvalKey(recipient,selectedEvidence)!==approvalKey(approvalInitial.current.recipient,approvalInitial.current.evidence);
  const hasUnsaved=documentDirty||declarationDirty||(inRequest&&(dirtyQuestions.length>0||approvalDirty))||
    (modal==='new-request'&&!!(newCustomer.trim()||newQuestions.trim()||dueDate))||
    (modal==='upload'&&!!(pendingFile||sourceType!=='electricity'));
  const dirtyRef=useRef(hasUnsaved);dirtyRef.current=hasUnsaved;
  const discardRef=useRef<()=>void>(()=>{});discardRef.current=discardAllChanges;
  const navigatorRef=useRef<ReturnType<typeof createDraftNavigator>|null>(null);
  if(!navigatorRef.current)navigatorRef.current=createDraftNavigator({isDirty:()=>dirtyRef.current,onDiscard:()=>discardRef.current()});
  useEffect(()=>{if(!hasUnsaved)return;window.addEventListener('beforeunload',warnBeforeUnload);return()=>window.removeEventListener('beforeunload',warnBeforeUnload);},[hasUnsaved]);
  function discardQuestionChanges(){setQuestionDrafts({});setDirtyQuestions([]);setRequestEditorEpoch(n=>n+1);}
  function discardRecordChanges(){setDocumentMeta({...documentMetaInitial.current});setActivityRows(recordInitial.current.map(row=>({...row})));setRecordErrors({});}
  function discardAllChanges(){
    discardQuestionChanges();discardRecordChanges();
    setDeclAnswer(structuredClone(declarationInitial.current.answer));setDeclEvidence([...declarationInitial.current.evidence]);
    setRecipient(approvalInitial.current.recipient);setSelectedEvidence([...approvalInitial.current.evidence]);
    setNewCustomer('');setNewQuestions('');setDueDate('');setPendingFile(null);setSourceType('electricity');
  }
  function navigate(action:()=>void,options?:{dirty?:boolean;discard?:()=>void}){
    if(busy)return;
    setUnsavedOpen(navigatorRef.current!.request(action,options));
  }
  const closeWorkspace = () => {
    if(modal==='document'&&requestReturn){
      const parent=requestReturn;
      navigate(()=>{setDetail(parent.request);setModal(parent.stage);setTab('Customer requests');setRequestReturn(null);setError('');},{dirty:documentDirty,discard:discardRecordChanges});return;
    }
    if(modal==='owner-review'){setModal('request');return;}
    navigate(()=>{setModal(null);setRequestReturn(null);setError('');});
  };
  function changeRole(next:Role){navigate(()=>{if(next===role)return;evidenceLoader.current?.cancel();workspaceLoader.current.invalidate();workspaceEpoch.current++;activeRole.current=next;setLoading(next!=='customer');setSectionStates({});setProfile(null);setDocuments([]);setDeclarations([]);setRequests([]);setEvents([]);setShares([]);setArchivedDocuments([]);setArchiveError('');setPendingOpen(null);setFileUrl('');setToken('');setNotice('');window.history.replaceState(null,'',window.location.pathname+periodSearch('',selectedMonth));setRole(next);setModal(null);setRequestReturn(null);setPack(null);setDetail(null);setError('');setRequestConflict(false);});}
  function switchMonth(next:string){
    evidenceLoader.current?.cancel();workspaceLoader.current.invalidate();workspaceEpoch.current++;activeMonth.current=next;
    setSelectedMonth(next);setLoading(true);setSectionStates({});setProfile(null);setDocuments([]);setDeclarations([]);setRequests([]);setShares([]);setArchivedDocuments([]);setArchiveError('');setRecordView('active');setModal(null);setRequestReturn(null);setDetail(null);setPack(null);setError('');setNotice('');setDuplicateRecord(null);setPreviousPolicy(null);
    window.history.replaceState(null,'',window.location.pathname+periodSearch(window.location.search,next));
  }
  function changeMonth(next:string){if(isValidPeriod(next)&&next!==selectedMonth)navigate(()=>{setPendingOpen(null);switchMonth(next);});}
  function openDuplicate(){if(!duplicateRecord)return;const record=duplicateRecord;navigate(()=>{switchMonth(record.period);setRecordView(record.archived?'archived':'active');setTab('Evidence');setPendingOpen(record);});}
  function startUpload(){navigate(()=>{setPendingFile(null);setDuplicateRecord(null);setSourceType('electricity');setTab('Evidence');setModal('upload');});}
  function startRequest(){navigate(()=>{setNewCustomer('');setNewQuestions('');setDueDate('');setModal('new-request');});}
  function openDeclaration(code:string,record:Json|undefined){navigate(()=>{
    const answer=structuredClone(record?.answer||defaultDeclaration(code));const evidence=[...(record?.evidence_ids||[])];
    declarationInitial.current={answer:structuredClone(answer),evidence:[...evidence]};
    setDeclDocuments(documents);setDeclCode(code);setDeclAnswer(answer);setDeclEvidence(evidence);setDeclErrors('');setModal('declaration');
  });}

  const apiAction = useCallback((path:string,options:RequestInit={})=>apiRequest(periodPath(path,selectedMonth),options,role),[role,selectedMonth]);

  const refresh = useCallback(async()=>{
    if(!periodReady)return;
    if (typeof window !== 'undefined' && new URLSearchParams(window.location.search).has('share') && role!=='customer') return;
    if(role==='customer') {setLoading(false);return;}
    const epoch=++workspaceEpoch.current;
    try{
      const current=await workspaceLoader.current.load({role,request:key=>apiAction(`/${key}`),onState:(key,state)=>{
        if(workspaceEpoch.current!==epoch||activeRole.current!==role||activeMonth.current!==selectedMonth)return;
        setSectionStates(previous=>({...previous,[key]:{...state,hasData:state.status==='ready'||previous[key]?.hasData}}));
        if(state.status!=='ready')return;
        const value=state.value;
        if(key==='profile')setProfile(value);
        if(key==='documents')setDocuments(Array.isArray(value)?value:value.documents||[]);
        if(key==='questionnaires')setRequests(Array.isArray(value)?value:value.questionnaires||[]);
        if(key==='declarations')setDeclarations(Array.isArray(value)?value:value.declarations||[]);
        if(key==='shares')setShares(Array.isArray(value)?value:value.shares||[]);
      }});
      if(current&&workspaceEpoch.current===epoch)setLoading(false);
    }catch(error){
      if(workspaceEpoch.current!==epoch||activeRole.current!==role||activeMonth.current!==selectedMonth)return;
      setLoading(false);throw error;
    }
  },[apiAction,role,selectedMonth,periodReady]);
  useEffect(()=>{refresh().catch(e=>setError(e.message));return()=>{workspaceLoader.current.invalidate();workspaceEpoch.current++;};},[refresh,retry]);
  useEffect(()=>{const t=new URLSearchParams(window.location.search).get('share'); if(t){setToken(t);setRole('customer');apiRequest(`/shares/${encodeURIComponent(t)}`,{},'customer').then(setPack).catch(e=>setError(e.message));}},[]);
  useEffect(()=>{if(!notice)return;const id=setTimeout(()=>setNotice(''),5000);return()=>clearTimeout(id);},[notice]);
  useEffect(()=>{if(role==='customer'){setProfile(null);setDocuments([]);setDeclarations([]);setRequests([]);setEvents([]);setShares([]);}},[role]);
  useEffect(()=>{if(!isDialog||unsavedOpen)return;const previous=document.activeElement as HTMLElement;const dialog=dialogRef.current;const selector='button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex="0"]';const first=dialog?.querySelector<HTMLElement>(selector);first?.focus();const key=(e:KeyboardEvent)=>{if(e.key==='Escape'&&!busy)closeWorkspace();if(e.key==='Tab'&&dialog){const items=Array.from(dialog.querySelectorAll<HTMLElement>(selector));const first=items[0],last=items[items.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}}};document.addEventListener('keydown',key);return()=>{document.removeEventListener('keydown',key);previous?.focus();};},[isDialog,busy,unsavedOpen]);

  const act = async(label:string,fn:()=>Promise<void>)=>{setBusy(label);setError('');try{await fn();}catch(e:any){setError(e.message||'The action could not be completed.');if(e.existingDocument)setDuplicateRecord(e.existingDocument);if(e.status===409&&modal==='document')setRecordConflict(true);if(e.status===409&&(modal==='request'||modal==='owner-review'))setRequestConflict(true);}finally{setBusy('');}};
  useEffect(()=>{
    if(tab!=='Activity log'||role==='customer'||modal)return;
    let cancelled=false;
    setHistoryLoading(true);
    apiAction('/activity-log').then(log=>{
      if(!cancelled&&activeRole.current===role)setEvents(Array.isArray(log)?log:log.events||[]);
    }).catch(e=>{if(!cancelled)setError(e.message);}).finally(()=>{if(!cancelled)setHistoryLoading(false);});
    return()=>{cancelled=true;};
  },[tab,role,modal,apiAction,historyRetry]);
  const go=(next:Tab)=>navigate(()=>{setTab(next);setModal(null);setRequestReturn(null);setMobile(false);setQuery('');setError('');});
  const coreReady=['profile','documents','questionnaires'].every(key=>sectionStates[key as WorkspaceSection]?.hasData);
  const coreLoading=['profile','documents','questionnaires'].some(key=>sectionStates[key as WorkspaceSection]?.status==='loading');
  useEffect(()=>{
    if(recordView!=='archived'||role==='customer'||!periodReady)return;
    let cancelled=false;setArchiveLoading(true);setArchiveError('');
    apiAction('/documents?archived=true').then(rows=>{if(!cancelled)setArchivedDocuments(rows);}).catch(error=>{if(!cancelled)setArchiveError(error.message);}).finally(()=>{if(!cancelled)setArchiveLoading(false);});
    return()=>{cancelled=true;};
  },[recordView,role,selectedMonth,periodReady,archiveRetry,apiAction]);
  useEffect(()=>{
    if(!pendingOpen||pendingOpen.period!==selectedMonth||!coreReady||busy)return;
    const record=pendingOpen;setPendingOpen(null);void loadDocument(record,null);
  },[pendingOpen,selectedMonth,coreReady,busy]);
  useEffect(()=>{
    setPreviousPolicy(null);setPreviousPolicyError('');
    const prior=previousMonth(selectedMonth);if(modal!=='declaration'||declCode!=='G2.1'||!prior){setPreviousPolicyLoading(false);return;}
    let cancelled=false;setPreviousPolicyLoading(true);
    apiRequest(`/declarations?period=${prior}`,{},role).then(rows=>{if(!cancelled)setPreviousPolicy(rows.find((row:Json)=>row.code==='G2.1')||null);}).catch(error=>{if(!cancelled)setPreviousPolicyError(error.message);}).finally(()=>{if(!cancelled)setPreviousPolicyLoading(false);});
    return()=>{cancelled=true;};
  },[modal,declCode,selectedMonth,role]);
  useEffect(()=>{
    const declaration=modal==='declaration';const request=(modal==='request'||modal==='owner-review')&&detail?.questions;
    if(!declaration&&!request){setEvidenceCatalogLoading(false);return;}
    let cancelled=false;setEvidenceCatalogLoading(true);setEvidenceCatalogError('');
    const ids=declaration?declEvidence:[...(detail?.questions||[]).flatMap((q:Json)=>q.evidence_ids||[]),...selectedEvidence];
    hydrateEvidence(apiAction,documents,ids).then(catalog=>{if(cancelled)return;if(declaration)setDeclDocuments(catalog);else{setRequestDocuments(catalog);setSelectedEvidence(ids=>retainEvidenceSelection(ids,catalog));}}).catch(error=>{if(!cancelled)setEvidenceCatalogError(error.message);}).finally(()=>{if(!cancelled)setEvidenceCatalogLoading(false);});
    return()=>{cancelled=true;};
  },[modal,declCode,detail?.id,detail?.version,role,selectedMonth,catalogRetry]);
  function catalogNotice(){return evidenceCatalogLoading?<p role="status">Loading supporting evidence…</p>:evidenceCatalogError?<div className="info-note" role="alert">{evidenceCatalogError}<button className="text-button" onClick={()=>setCatalogRetry(n=>n+1)}>Retry supporting evidence</button></div>:null;}
  const shownDocuments=recordView==='archived'?archivedDocuments:documents;
  function openArchive(doc:Json){navigate(()=>{setArchiveTarget(doc);setModal('archive-record');setError('');});}
  async function archiveRecord(){if(!archiveTarget)return;await act('Archiving record',async()=>{await apiAction(`/documents/${archiveTarget.id}/archive`,{method:'POST',body:JSON.stringify({expected_version:archiveTarget.version})});await refresh();setArchiveRetry(n=>n+1);setModal(null);setNotice('Record archived. Previous approved packs remain unchanged.');});}
  async function restoreRecord(doc:Json){await act('Restoring record',async()=>{const restored=await apiAction(`/documents/${doc.id}/restore`,{method:'POST',body:JSON.stringify({expected_version:doc.version})});if(modal==='document'&&detail?.id===restored.id){setDetail(restored);setRecordConflict(false);}await refresh();setArchiveRetry(n=>n+1);setNotice('Record restored. Review and confirm it before it enters calculations.');});}
  function reloadRecord(){if(!detail)return;navigate(()=>{void loadDocument(detail,requestReturn);},{dirty:documentDirty,discard:()=>{}});}
  function sectionNotice(key:WorkspaceSection,label:string){
    const state=sectionStates[key];
    if(!state||state.status==='ready')return null;
    return <div className="info-note" role={state.status==='error'?'alert':'status'}>{state.status==='loading'?<><LoaderCircle size={16} className="spin"/>{state.hasData?'Updating':'Loading'} {label}…</>:<><AlertTriangle size={16}/><span>{label} could not be updated. {state.error}</span><button className="text-button" onClick={()=>{setError('');setRetry(value=>value+1);}}>Retry {label}</button></>}</div>;
  }
  const period=selectedMonth;
  const metrics:Metric[]=profile?.metrics||[];
  const readiness=profile?.readiness||{complete:0,total:11,percent:0};
  const confirmedDocs=documents.filter(d=>d.confirmed).length;
  const breakdown=readiness.breakdown||{complete:readiness.complete,partial:0,estimated:0,missing:11-readiness.complete};
  const periodLabel=monthLabel(period);
  const companyName=profile?.company?.name||'Lim Carton Manufacturing';

  async function loadDocument(doc:Json,parent:{request:Json;stage:string}|null){
    await act('Opening evidence',()=>evidenceLoader.current!.open(doc.id,{parent,role,period:selectedMonth}));
  }
  function retrySource(){if(detail?.id&&modal==='document')void evidenceLoader.current?.retry(detail.id);}
  function openDocument(doc:Json){
    const parent=(modal==='request'||modal==='owner-review')&&detail?.questions?{request:detail,stage:modal}:null;
    navigate(()=>{void loadDocument(doc,parent);},{...(parent?{dirty:false}:{})});
  }
  function acceptWorkspaceSection(key:WorkspaceSection){
    workspaceLoader.current.accept(key);
    setSectionStates(previous=>({...previous,[key]:{status:'ready',hasData:true}}));
  }
  function acceptRequest(request:Json){
    if(activeRole.current!==role)return;
    acceptWorkspaceSection('questionnaires');setDetail(request);setRequests(current=>replaceRequest(current,request));setRequestConflict(false);
  }
  function showRequest(request:Json){
    if(activeRole.current!==role)return;
    acceptRequest(request);setRequestDocuments(documents);discardQuestionChanges();setTab('Customer requests');
    const selected=retainEvidenceSelection(recommendedEvidence(request),documents);
    approvalInitial.current={recipient:request.customer,evidence:[...selected]};
    setRecipient(request.customer);setSelectedEvidence(selected);setModal('request');
  }
  function openRequest(request:Json){navigate(()=>{void act('Opening request',async()=>showRequest(await apiAction(`/questionnaires/${request.id}`)));});}
  function reloadLatestAnswers(){
    if(!detail?.id)return;
    const requestId=detail.id;
    navigate(()=>{void act('Loading latest answers',async()=>{
      const latest=await reloadRequestContext(apiAction,requestId,role);
      const catalog=await hydrateEvidence(apiAction,latest.documents,[...(latest.request.questions||[]).flatMap((q:Json)=>q.evidence_ids||[]),...selectedEvidence,...approvalInitial.current.evidence]);
      if(activeRole.current!==role||activeMonth.current!==selectedMonth)return;
      setRequestDocuments(catalog);
      acceptWorkspaceSection('documents');setDocuments(latest.documents);if(role==='owner'){acceptWorkspaceSection('shares');setShares(latest.shares);}
      setSelectedEvidence(current=>retainEvidenceSelection(current,catalog));
      approvalInitial.current={...approvalInitial.current,evidence:retainEvidenceSelection(approvalInitial.current.evidence,catalog)};
      acceptRequest(latest.request);discardQuestionChanges();setNotice('Latest answers loaded. Review and confirm each changed answer.');
    });},{dirty:dirtyQuestions.length>0,discard:()=>{}});
  }
  function updateQuestionDraft(question:Json,draft:{codes:string[];manual:string}){
    const changed=questionDraftChanged(question,draft);
    setQuestionDrafts(current=>{const next={...current};if(changed)next[question.id]=draft;else delete next[question.id];return next;});
    setDirtyQuestions(current=>changed?[...new Set([...current,question.id])]:current.filter(id=>id!==question.id));
  }
  function focusRecordError(errors:Record<string,string>){
    const first=Object.keys(errors)[0];if(!first)return;
    window.requestAnimationFrame(()=>Array.from(document.querySelectorAll<HTMLElement>('[data-field]')).find(element=>element.dataset.field===first)?.focus());
  }
  async function confirmActivity(confirmed=true){
    if(!detail||detail.archived)return;
    if(confirmed&&sourceState.status!=='ready'){setError('Wait for the source file to load before confirming.');return;}
    const errors={...validateRecordMetadata(documentMeta),...validateActivities(activityRows,documentMeta.type,documentMeta.period)};setRecordErrors(errors);
    if(Object.keys(errors).length){focusRecordError(errors);return;}
    const parent=requestReturn;
    await act(confirmed?'Confirming evidence':'Saving changes',async()=>{
      let saved=detail;
      const activities=activityRows.map(row=>({...row,quantity:cleanDecimal(row.quantity),estimated:!!row.estimated,assumptions:row.assumptions||'',allocated_period:row.allocated_period||null}));
      try{
        const metadataChanged=documentMeta.name!==detail.name||documentMeta.period!==detail.period||documentMeta.type!==detail.type;
        if(metadataChanged){
          saved=await apiAction(`/documents/${detail.id}`,{method:'PUT',body:JSON.stringify({...documentMeta,activities,expected_version:detail.version})});
          setDetail(saved);recordInitial.current=structuredClone(activityRows);documentMetaInitial.current={...documentMeta};
        }
        if(!metadataChanged||confirmed)saved=await apiAction(`/documents/${detail.id}/activities`,{method:'PUT',body:JSON.stringify({confirmed,activities,expected_version:saved.version})});
      }catch(e:any){if(e.fieldErrors){setRecordErrors(e.fieldErrors);focusRecordError(e.fieldErrors);}throw e;}
      setDetail(saved);recordInitial.current=structuredClone(activityRows);documentMetaInitial.current={...documentMeta};setRecordConflict(false);
      await refresh();setArchiveRetry(n=>n+1);
      if(parent){const updated=await apiAction(`/questionnaires/${parent.request.id}`);acceptRequest(updated);setModal(parent.stage);setTab('Customer requests');setRequestReturn(null);}else setModal(null);
      setNotice(confirmed?'Record confirmed. Affected monthly profiles are updated.':'Changes saved. Review and confirm this record before it enters calculations.');
    });
  }
  function showPack(t:string){navigate(()=>{void act('Opening approved pack',async()=>{const p=await apiAction(`/shares/${encodeURIComponent(t)}`);setToken(t);setPack(p);setModal('pack');});});}
  async function upload(){await act('Uploading evidence',async()=>{
    if(!pendingFile)throw Error('Choose a supporting document first.');
    const data=new FormData();data.append('file',pendingFile);data.append('type',sourceType);data.append('period',selectedMonth);
    const d=await apiAction('/documents',{method:'POST',body:data});setPendingFile(null);setSourceType('electricity');await refresh();
    await loadDocument(d,null);setNotice('Record stored on the server. Enter the quantities and check them against the source.');
  });}
  function requestNotices(){return detail&&<RequestRecoveryNotice request={detail} shares={shares} role={role} conflict={requestConflict} busy={!!busy} onReload={reloadLatestAnswers} onOpenPack={showPack}/>;}
  function sourceLink(id:string){const doc=documents.find(d=>String(d.id)===String(id));return <button key={id} className="evidence-link" onClick={()=>openDocument(doc||{id})}><FileText size={14}/>{doc?.name||id}<ArrowUpRight size={12}/></button>;}
  function metricCard(m:Metric){const Icon=m.code==='E1.1'?Fuel:m.code==='E1.2'?Zap:m.code==='E3.1'?Droplets:m.code==='E4.1'?Recycle:BarChart3;return <button className="metric-card" key={m.code} onClick={()=>navigate(()=>{setDetail(m);setModal('metric');})}><div className="flex-between"><span className="metric-icon"><Icon size={18}/></span><span className="code">{m.code}</span></div><p>{titles[m.code]||m.title}</p><div className="metric-number">{m.code==='E1.1'||m.code==='E1.2'?number(m.value==null?null:m.unit?.startsWith('kg')?Number(m.value)/1000:m.value,3):m.code==='E4.1'?number(m.value,3):number(m.value)} <small>{m.code==='E1.1'||m.code==='E1.2'?'t CO₂e':m.unit}</small></div><MetricAvailability metric={m}/><div className="flex-between"><Badge value={m.badge}/><ArrowUpRight size={16}/></div></button>;}

  const renderPack=(p:Json)=>{
    const snapshot=p.snapshot||p;
    const questions=snapshot.questions||snapshot.answers||[];
    return <div className="customer-pack"><div className="pack-top"><div className="brand-mark"><Leaf size={25}/></div><span>ESG Passport</span><span className="approved-label"><ShieldCheck size={15}/> Owner approved</span></div><p className="eyebrow">CUSTOMER DISCLOSURE PACK</p><h1>{snapshot.company?.name||'Supplier disclosure pack'}</h1><p>Prepared for <strong>{snapshot.recipient||p.recipient||'Customer'}</strong> · {snapshot.period||'Period not supplied'} · Partial-year coverage</p><div className="pack-note">Approved snapshot · Estimates and unavailable information remain visible.</div><div className="pack-meta"><span>Approved by <strong>{snapshot.approved_by||p.approved_by||'Owner'}</strong></span><span>{humanDate(snapshot.shared_on||snapshot.approved_at||snapshot.created_at||p.created_at)}</span></div>{questions.map((q:Json,i:number)=><div className="pack-answer" key={i}><span className="code">{(q.codes||q.mapped_codes||[]).join(' + ')||'Owner response'}</span><h3>{q.text||q.question}</h3><p className="answer-text">{typeof q.answer==='string'?q.answer:JSON.stringify(q.answer)}</p><Badge value={q.badge||'missing'}/>{packQuestionEvidence(q,snapshot).length>0&&<div className="evidence-list" aria-label="Supporting evidence">{packQuestionEvidence(q,snapshot).map(doc=><a className="evidence-link" key={doc.id} href={doc.preview_url} target="_blank" rel="noreferrer"><FileText size={14}/>{doc.name}<ExternalLink size={13}/></a>)}</div>}{q.manual_declaration&&<p className="field-note">Owner statement by {q.manual_declaration.declared_by} · {humanDate(q.manual_declaration.declared_at)} · {q.manual_declaration.period}</p>}{(q.metrics||[]).map((m:Metric)=><div className="pack-metric" key={m.code}><Badge value={m.badge}/><span>{m.method}</span>{m.factors?.map((f:Json,j:number)=><small key={j}>{number(f.value,6)} {f.unit} · {f.year} · {f.version} <a href={f.source_url||f.source} target="_blank" rel="noreferrer">Source</a></small>)}</div>)}</div>)}<h3>Approved evidence</h3><div className="evidence-list">{packQuestionEvidence({evidence_ids:snapshot.selected_evidence_ids||snapshot.evidence_ids||[]},snapshot).map(doc=><a className="evidence-link" key={doc.id} href={doc.preview_url} target="_blank" rel="noreferrer"><FileText size={15}/>{doc.name}<ExternalLink size={13}/></a>)}</div>{(snapshot.evidence||[]).filter((e:Json)=>e.activities?.length).map((e:Json)=><section className="approved-inputs" key={e.id}><h4>{e.name} · approved inputs</h4>{e.activities.map((a:Json,i:number)=><div key={i}><strong>{number(a.quantity,6)} {a.unit}</strong><span>{a.category?.replaceAll('_',' ')} · {a.period_start} to {a.period_end}</span><small>Confirmed by {a.confirmed_by} · {humanDate(a.confirmed_at)}</small>{a.assumptions&&<small>Assumptions: {a.assumptions}</small>}</div>)}</section>)}<div className="pack-footer">This pack preserves the answers and evidence selected at approval. No certification or legal assurance is provided.</div><button className="button primary no-print" onClick={()=>window.print()}><ArrowDownToLine size={16}/> Print / Save as PDF</button></div>;
  };

  return <div className="app-shell">
    <aside inert={isDialog||unsavedOpen} aria-hidden={isDialog||unsavedOpen ? true : undefined} className={`sidebar ${mobile?'is-open':''}`}><a className="brand" href="/" onClick={event=>{event.preventDefault();go('Overview');}} aria-label="ESG Passport home"><span className="brand-mark"><Leaf size={24}/></span><span>ESG <b>Passport</b><small>BY ORBYTE</small></span></a><div className="workspace-label">YOUR WORKSPACE</div><div className="workspace"><span className="company-avatar">LC</span><div><strong>Lim Carton</strong><small>Manufacturing · Shah Alam</small></div><ChevronDown size={15}/></div><nav aria-label="Main navigation">{nav.map(({name,label,icon:Icon})=><button key={name} className={tab===name?'active':''} onClick={()=>go(name)} disabled={role==='customer'||!!busy}><Icon size={19}/><span>{label}</span>{name==='Customer requests'&&<span className="nav-count">{requests.length}</span>}</button>)}</nav><nav className="secondary-nav" aria-label="Workspace tools">{secondaryNav.map(({name,icon:Icon})=><button key={name} className={tab===name?'active':''} disabled={role==='customer'||!!busy} onClick={()=>go(name)}><Icon size={17}/>{name==='Declarations'?'Owner declarations':name}</button>)}</nav><div className="sidebar-bottom"><div className="passport-note"><ShieldCheck size={23}/><strong>Your evidence. Your control.</strong><p>Nothing is shared until the owner approves.</p></div><div className="identity"><span className="avatar">{role==='owner'?'ML':role==='clerk'?'AT':'CU'}</span><div><strong>{role==='owner'?'Mr Lim':role==='clerk'?'Aina Tan':'Customer'}</strong><small>{role==='owner'?'Company owner':role==='clerk'?'Admin clerk':'Approved pack only'}</small></div><span className="online-dot"/></div></div></aside>

    <div className="main-shell" inert={isDialog||unsavedOpen} aria-hidden={isDialog||unsavedOpen ? true : undefined}><header className="topbar"><div className="breadcrumb"><button className="icon-button mobile-toggle" aria-label="Toggle navigation" onClick={()=>setMobile(!mobile)}><Menu size={20}/></button><span>Lim Carton</span><ChevronRight size={14}/><strong>{role==='customer'?'Customer pack':workspaceScreen?screenTitle:tab==='Evidence'?'Records':tab}</strong></div><div className="top-actions">{role!=='customer'&&<label className="month-selector">Reporting month<input aria-label="Reporting month" type="month" min="0001-01" max="9999-12" value={selectedMonth} disabled={!!busy} onChange={e=>changeMonth(e.target.value)}/></label>}<span className="top-period">Partial-year <strong>{role==='customer'?pack?.snapshot?.period||'Approved period':periodLabel}</strong></span><RoleSwitcher value={role} disabled={!!busy} onChange={changeRole}/><button className="icon-button" aria-label="Workspace help" onClick={()=>navigate(()=>setModal('help'))}><CircleHelp size={19}/></button></div></header>
    <main>
      {error&&<div role="alert" className="alert error"><AlertTriangle size={18}/><div><strong>Action needs attention</strong><p>{error}</p></div><button className="icon-button" aria-label="Dismiss error" onClick={()=>setError('')}><X size={16}/></button></div>}
      {notice&&<div role="status" className="toast"><CheckCircle2 size={18}/>{notice}</div>}
      {busy&&<div className="busy-status" role="status"><LoaderCircle size={15} className="spin"/>{busy}…</div>}
      {role==='customer'?<><div className="page-heading"><div><p className="eyebrow">OWNER-APPROVED DISCLOSURES</p><h1>Your customer portal</h1><p>{customerPortalMessage(pack)}</p></div></div>{pack?renderPack(pack):<section className="panel customer-entry"><LockKeyhole size={30}/><h2>Only what was shared with you</h2><p>Enter an approved share token to open your disclosure pack.</p><label>Share token<input value={token} onChange={e=>setToken(e.target.value)} placeholder="Paste token from your share link"/></label><button className="button primary" onClick={()=>act('Loading pack',async()=>setPack(await apiAction(`/shares/${encodeURIComponent(token)}`)))} disabled={!token||!!busy}>Open approved pack <ArrowRight size={16}/></button></section>}</>:
      !coreReady&&(loading||coreLoading)?<div className="loading"><LoaderCircle className="spin" size={28}/><h2>Opening your passport</h2><p>Loading the evidence workspace from the server…</p></div>:
      !coreReady?<section className="panel customer-entry"><AlertTriangle size={30}/><h2>Connect your evidence workspace</h2><p>The server workspace could not be loaded. Start the backend, configure its Supabase database and storage, and check NEXT_PUBLIC_API_URL. Then retry.</p><button className="button primary" onClick={()=>setRetry(value=>value+1)}><RefreshCw size={16}/> Retry connection</button></section>:
      <>
      {sectionNotice('profile','profile')}{sectionNotice('documents','source records')}{sectionNotice('questionnaires','customer requests')}
      <div className="page-heading"><div><p className="eyebrow">{tab==='Overview'?'YOUR ESG, WITH THE EVIDENCE TO BACK IT UP':tab==='Evidence'?'FROM RECORDS TO RELIABLE ANSWERS':tab==='Customer requests'?'FILL ONCE. SHARE MANY.':'ESG PASSPORT WORKSPACE'}</p><h1>{tab==='Overview'?`Your ${periodLabel.split(' ')[0]} snapshot`:tab==='Evidence'?'Your source records':tab==='Declarations'?'Owner information':tab}</h1><p>{tab==='Overview'?`${periodLabel} · ${companyName}`:tab==='Evidence'?'Upload, check, and confirm the records behind your profile.':tab==='Declarations'?'Record what the owner knows. Keep the source of every answer clear.':tab==='Customer requests'?'Turn different questionnaires into one consistent, evidence-backed response.':tab==='Activity log'?'A clear history of who changed, confirmed, and shared what.':'Every calculation starts with a traceable, versioned factor.'}</p></div><div className="heading-actions">{tab==='Overview'&&<button className="button secondary" onClick={()=>act('Refreshing profile',async()=>{await apiAction('/profile/recalculate',{method:'POST',body:JSON.stringify({period})});await refresh();setNotice('Profile refreshed from confirmed evidence.');})} disabled={!!busy}><RefreshCw size={16}/> Refresh profile</button>}{tab==='Evidence'&&<button className="button secondary" onClick={startUpload}><Plus size={17}/> Add records</button>}{tab==='Customer requests'&&<button className="button primary" onClick={startRequest}><Plus size={17}/> New request</button>}</div></div>
      <div className={`period-row ${tab==='Overview'?'overview-period':''}`}><span><Building2 size={15}/>{companyName}</span><span className="period"><span className="calendar-dot"/>{periodLabel} <span className="partial">One month · Partial-year coverage</span></span></div>

      {tab==='Overview'&&<DesktopOverview readiness={readiness} breakdown={breakdown} documents={documents} requests={requests} gaps={(profile?.gaps||[]).map((g:Json)=>({...g,badge:metrics.find(m=>m.code===g.code)?.badge,partial:metrics.find(m=>m.code===g.code)?.components?.some(c=>c.value!=null)}))} periodLabel={periodLabel} titles={titles} onUpload={startUpload} onReview={openDocument} onRecords={()=>go('Evidence')} onRequest={openRequest} onAllRequests={()=>go('Customer requests')} onGap={code=>{const m=metrics.find(m=>m.code===code);if(m)navigate(()=>{setDetail(m);setModal('metric');});}}/>}

      {tab==='Evidence'&&<><div className="records-tabs"><span className="active">Bills & records</span><button onClick={()=>go('Declarations')}>Owner declarations <ArrowUpRight size={14}/></button><button onClick={()=>go('Factor register')}>Calculation factors <ArrowUpRight size={14}/></button></div><details className="profile-metrics"><summary>Environmental profile · View calculated metrics</summary><div className="metrics-grid">{metrics.filter(m=>m.code.startsWith('E')).map(metricCard)}</div></details><div className="summary-chips"><span><FileText size={16}/><strong>{documents.length}</strong> source documents</span><span><CheckCircle2 size={16}/><strong>{confirmedDocs}</strong> confirmed</span><span><Clock3 size={16}/><strong>{documents.length-confirmedDocs}</strong> awaiting review</span></div><section className="panel"><div className="panel-heading"><div><h2>Source records</h2><p>Only confirmed quantities enter your calculations.</p></div><input className="search" aria-label="Search documents" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Find a document…"/></div><div className="record-toolbar"><div role="group" aria-label="Record visibility"><button className={`button small ${recordView==='active'?'primary':'secondary'}`} onClick={()=>navigate(()=>setRecordView('active'))}>Active</button><button className={`button small ${recordView==='archived'?'primary':'secondary'}`} onClick={()=>navigate(()=>setRecordView('archived'))}>Archived</button></div><span>{recordView==='archived'?'Archived records do not enter calculations.':'Edit a record, or archive it to remove it from calculations.'}</span></div>{recordView==='archived'&&archiveLoading&&<p role="status">Loading archived records…</p>}{recordView==='archived'&&archiveError&&<div role="alert" className="info-note">{archiveError}<button className="text-button" onClick={()=>setArchiveRetry(n=>n+1)}>Retry archived records</button></div>}<div className="table-scroll"><table><thead><tr><th>Document</th><th>Category</th><th>Period</th><th>Review status</th><th/></tr></thead><tbody>{(recordView==='archived'&&(archiveLoading||archiveError)?[]:shownDocuments).filter(d=>`${d.name} ${d.type}`.toLowerCase().includes(query.toLowerCase())).map(d=><tr key={d.id}><td><div className="table-document"><span className="document-icon"><FileText size={19}/></span><strong>{d.name}</strong></div></td><td>{categoryLabel(d.type)}</td><td>{d.period||period}</td><td><Badge value={d.archived?'archived':d.confirmed?'confirmed':'needs_review'}/></td><td><div className="record-actions"><button className="text-button" disabled={!!busy} onClick={()=>openDocument(d)}>{d.archived?'View record':'Edit record'}<ArrowUpRight size={14}/></button>{d.archived?<button className="text-button" disabled={!!busy} onClick={()=>restoreRecord(d)}>Restore</button>:<button className="text-button danger" disabled={!!busy} onClick={()=>openArchive(d)}>Archive</button>}</div></td></tr>)}</tbody></table></div>{!shownDocuments.length&&!(recordView==='archived'&&(archiveLoading||archiveError))&&<p className="empty-records">{recordView==='archived'?'No archived records for this month.':'No records for this month. Add your first supporting record.'}</p>}</section><div className="info-note"><Eye size={17}/> Check the source, quantity, unit, and reporting dates before confirming.</div></>}

      {tab==='Declarations'&&<>{sectionNotice('declarations','owner declarations')}{sectionStates.declarations?.hasData&&<><div className="info-note"><ShieldCheck size={18}/> Declarations record the owner’s statement. They do not certify compliance or verify the absence of incidents.</div><div className="declaration-grid">{codes.filter(c=>c.startsWith('S')||c.startsWith('G')).map(code=>{const d=declarations.find(d=>d.code===code);const m=metrics.find(m=>m.code===code);return <section className="panel declaration-card" key={code}><div className="flex-between"><span className="code">{code}</span><Badge value={m?.badge||'missing'}/></div><h2>{titles[code]}</h2><DeclarationSummary code={code} value={code==='G2.1'?d?.answer??m?.value:m?.value}/><div className="declaration-bottom"><small>{d?.declared_by?`Declared by ${d.declared_by}`:'Owner declaration required'}</small><button className="text-button" disabled={role!=='owner'} onClick={()=>openDeclaration(code,d)}>{role==='owner'?'Review / edit':'Owner only'}<ArrowUpRight size={14}/></button></div></section>;})}</div></>}</>}

      {tab==='Customer requests'&&<><section className="panel"><div className="panel-heading"><div><h2>Questionnaires</h2><p>Review every proposed SEDG match before sharing.</p></div><span className="count-pill">{requests.length} requests</span></div><div className="request-table">{requests.map(q=><button className="request-row" key={q.id} onClick={()=>openRequest(q)}><span className="customer-avatar">{initials(q.customer||'Customer')}</span><div><h3>{q.customer}</h3><p>{q.questions?.length||q.question_count||'—'} questions · {q.period||period} · {q.due_date?`Due ${q.due_date}`:'No due date'}</p></div><Badge value={q.status||'draft'}/><ArrowUpRight size={18}/></button>)}</div></section>{role==='owner'&&<section className="panel shared-panel"><div className="panel-heading"><div><h2>Approved packs</h2><p>Each share preserves an owner-approved snapshot.</p></div><ShieldCheck size={21}/></div>{sectionNotice('shares','approved packs')}{sectionStates.shares?.hasData&&(shares.length?shares.map(s=><div className="share-row" key={s.token}><div><strong>{s.recipient||s.snapshot?.recipient}</strong><small>{humanDate(s.created_at||s.shared_on)}</small></div><button className="text-button" onClick={()=>showPack(s.token)}>Open pack <ExternalLink size={14}/></button><button className="button secondary small" onClick={()=>act('Copying share link',async()=>{await navigator.clipboard.writeText(`${window.location.origin}/?share=${encodeURIComponent(s.token)}`);setNotice('Pack link copied. It can open in another browser while the frontend and API are running on this computer.');})}><Link2 size={14}/>Copy pack link</button></div>):<div className="empty compact"><LockKeyhole size={23}/><p>No approved packs yet. Review a request to create the first.</p></div>)}</section>}</>}

      {tab==='Activity log'&&<section className="panel"><div className="panel-heading"><div><h2>Workspace history</h2><p>Times shown in Malaysia time (MYT).</p></div><button className="button secondary small" disabled={historyLoading} onClick={()=>{setError('');setHistoryRetry(n=>n+1);}}><RefreshCw size={14}/>Refresh history</button></div>{historyLoading?<p role="status">Loading latest activity…</p>:<div className="timeline">{events.map((e,i)=><div key={e.id||i}><span className="timeline-dot"><Check size={13}/></span><div><strong className="capitalize">{String(e.action).replaceAll('_',' ')}</strong><p>{e.note||e.summary||e.target}</p><small>{e.actor||e.user||'System'} · {e.role} · {e.period?monthLabel(e.period):'Workspace'} · {humanDate(e.time||e.timestamp||e.created_at)}</small></div></div>)}</div>}</section>}

      {tab==='Factor register'&&<><div className="info-note"><BookOpen size={17}/> Factors are versioned. Diesel and petrol use a mineral-fuel proxy; actual Malaysian biodiesel blends remain unresolved.</div><section className="panel"><div className="panel-heading"><div><h2>Calculation factors</h2><p>Source, year, and assumptions travel with every result.</p></div><span className="code">FACTOR REGISTER · V1</span></div><div className="factor-list">{(profile?.factors||[]).map((f:Json,i:number)=><div key={f.id||i}><div className="flex-between"><h3>{f.name||f.fuel||f.id}</h3><span className="factor-value">{number(f.value,6)} <small>{f.unit}</small></span></div><details className="factor-explanation"><summary>Factor basis and source precision</summary><p>{f.assumptions||f.note||'See source for factor basis and applicability.'}</p></details>{f.source_value&&<p className="field-note">Source value: {f.source_value} · {f.source_cell||'See publication'}<br/>{f.verification||'Verification not recorded'}</p>}<div className="factor-meta"><span>{f.year} · {f.version}</span><a href={f.source_url||f.source} target="_blank" rel="noreferrer">Official source <ExternalLink size={13}/></a></div></div>)}</div></section><section className="panel mt"><div className="panel-heading"><h2>Deferred disclosures</h2><span className="count-pill">Not currently supported</span></div><div className="deferred-list">{['E5.1 · Materials','S2.1 · Training','S2.3 · Minimum wage','S3.1 · Workforce demographics','S5.1 · Community investment'].map(s=><span key={s}>{s}</span>)}</div></section></>}
      <footer className="workspace-footer"><span><Leaf size={14}/> Prepared with reference to selected SEDG Basic disclosures.</span><button onClick={()=>navigate(()=>setModal('help'))}>Workspace help <ArrowUpRight size={13}/></button></footer>
      </>}
    </main></div>

    {modal&&<div className={`${workspaceScreen?'workspace-screen':'modal-backdrop'} ${modal==='pack'?'print-backdrop':''}`} inert={unsavedOpen} aria-hidden={unsavedOpen?true:undefined} onClick={e=>{if(!workspaceScreen&&e.target===e.currentTarget&&!busy)closeWorkspace();}}><section ref={dialogRef} className={workspaceScreen?'screen-content':`modal ${['document','request','pack'].includes(modal)?'wide':''}`} role={workspaceScreen?'region':'dialog'} aria-modal={isDialog?true:undefined} aria-label={modal==='document'?'Review evidence':modal==='request'?'Review customer request':modal==='owner-review'?'Owner review':modal==='metric'?'Calculation details':'ESG Passport dialog'}><div className="modal-header no-print"><div><p className="eyebrow">ESG PASSPORT</p>{workspaceScreen?<h1>{screenTitle}</h1>:<h2>{modal==='archive-record'?'Archive record':modal==='declaration'?'Owner declaration':modal==='metric'?'Follow the evidence':'Workspace help'}</h2>}</div><button className={workspaceScreen?"button secondary":"icon-button"} onClick={closeWorkspace} disabled={!!busy} aria-label={workspaceScreen?"Back to previous page":"Close dialog"}>{workspaceScreen?<>Back <ArrowRight size={15}/></>:<X size={22}/>}</button></div>{workspaceScreen&&modal!=='pack'&&<><p className="screen-subtitle">{periodLabel} · Partial-year coverage · {modal==='document'?'Check the source before quantities enter your profile.':modal==='owner-review'?'Choose exactly what the customer receives.':'Your evidence stays private until the owner approves sharing.'}</p><FlowSteps customer={['new-request','request','owner-review'].includes(modal||'')} current={modal==='document'||modal==='request'?1:modal==='owner-review'?2:0}/></>}
    {workspaceScreen&&notice&&<div role="status" className="toast"><CheckCircle2 size={18}/>{notice}</div>}{workspaceScreen&&busy&&<div role="status" className="busy-status"><LoaderCircle className="spin" size={15}/>{busy}…</div>}{error&&<div role="alert" className="alert error modal-error"><AlertTriangle size={18}/><div><strong>Action needs attention</strong><p>{error}</p></div><button className="icon-button" onClick={()=>setError('')} aria-label="Dismiss error"><X size={16}/></button></div>}
    {modal==='upload'&&duplicateRecord&&<div className="info-note" role="status">This file already exists in {monthLabel(duplicateRecord.period)}{duplicateRecord.archived?' and is archived':''}.<button className="button secondary small" onClick={openDuplicate}>{duplicateRecord.archived?'View archived record / Restore':'Open existing record'}</button></div>}{modal==='upload'&&<div className="modal-body upload-layout"><section className="upload-form panel"><div className="info-note">JPEG, PNG, or single-page PDF · up to 10 MB.</div><label>Document category<select disabled={!!busy} value={sourceType} onChange={e=>setSourceType(e.target.value)}>{['electricity','diesel','petrol','water','waste'].map(t=><option key={t} value={t}>{categoryLabel(t)}</option>)}</select></label><input type="file" disabled={!!busy} ref={inputRef} accept="image/png,image/jpeg,application/pdf" onChange={e=>setPendingFile(e.target.files?.[0]||null)} className="file-input"/><button className="upload-zone" onClick={()=>inputRef.current?.click()}><Upload size={30}/><strong>{pendingFile?.name||'Choose a bill or supporting record'}</strong><span>{pendingFile?`${(pendingFile.size/1024).toFixed(0)} KB`:'PNG, JPEG or single-page PDF'}</span></button><p className="muted">Your source file is stored through the backend in Supabase Storage. Enter its quantity, unit and reporting dates, then check each value before confirming.</p><button className="button primary full" disabled={!pendingFile||!!busy} onClick={upload}>Upload and review <ArrowRight size={16}/></button></section><aside className="upload-guidance"><section className="panel"><h2>A good record includes</h2><p>The company name, reporting dates and a readable usage quantity.</p><p>Keep the original. Corrections are saved alongside the source record.</p></section><div className="info-note">Uploaded does not mean complete. Every quantity requires your confirmation.</div><section className="panel upload-queue"><h2>Existing records · {documents.length}</h2>{documents.map(d=><button key={d.id} className="upload-queue-item" onClick={()=>openDocument(d)}><FileText size={17}/><span>{d.name}</span><Badge value={d.archived?'archived':d.confirmed?'confirmed':'needs_review'}/><ChevronRight size={15}/></button>)}</section></aside></div>}
    {modal==='document'&&detail&&<><div className="document-review"><div className="source-preview"><div className="source-title"><FileText size={16}/>{detail.name}</div>{fileUrl&&(detail.mime_type==='application/pdf'||detail.name?.endsWith('.pdf')?<iframe src={fileUrl} title="Source document"/>:<img src={fileUrl} alt={`Source evidence: ${detail.name}`}/>)}{sourceState.status==='loading'&&<div className="source-loading" role="status"><LoaderCircle size={24}/>Loading source file… You can prepare fields while it loads.</div>}{sourceState.status==='error'&&<div className="source-load-error" role="alert"><strong>Source file could not load</strong><p>{sourceState.error}</p><button className="button secondary" onClick={retrySource}>Retry source file</button><p>Your entered values are preserved. Load the source before confirming.</p></div>}<div className="source-caption">Source document · Original retained with corrections</div></div><div className="source-fields"><div className="flex-between"><h3>{detail.archived?'Archived record':'Edit record'}</h3><Badge value={detail.confirmed?'confirmed':'needs_review'}/></div><p className="muted">Compare with the source. Manual entries remain linked to this document and require confirmation; an entry without supporting evidence belongs in an owner declaration.</p><p className="field-note">Enter or correct each quantity using the source document shown here.</p><RecordMetadataFields name={documentMeta.name} period={documentMeta.period} type={documentMeta.type} onChange={metadata=>{if(metadata.type!==documentMeta.type)setActivityRows(reclassifyActivities(activityRows,metadata.type));setDocumentMeta(metadata);setRecordErrors({});}} errors={recordErrors} disabled={!!busy||!!detail.archived}/>{documentMeta.period!==detail.period&&<div className="info-note">Check the source dates for the destination month. Saving will require reconfirmation and update both months.</div>}{recordConflict&&<div className="info-note" role="alert">This record changed. Your edits have been kept.<button className="button secondary small" disabled={!!busy} onClick={reloadRecord}>Reload latest record</button></div>}{detail.archived&&<div className="info-note">Archived records do not enter calculations. Restore this record, then review and confirm it.<button className="button secondary small" disabled={!!busy} onClick={()=>restoreRecord(detail)}>Restore record</button></div>}<ExtractionMetadata extraction={detail.extraction}/>{detail.original_extraction&&<details className="original-extraction"><summary>Original record values</summary><ExtractionMetadata extraction={detail.original_extraction}/>{(detail.original_extraction.activities||[]).map((r:Json,i:number)=><p key={i}>{categoryLabel(r.category)}: {r.quantity==null?'Missing':cleanDecimal(r.quantity)} {r.unit==='m3'?'m³':r.unit||''} · {r.source_reference||'Page 1'}{r.uncertainty?` · ${r.uncertainty}`:''}</p>)}</details>}{documentMeta.type!==detail.type&&<div className="info-note" role="status">Document category changed. Re-enter quantities and units from the source before saving. Previous values remain in the revision history; confirmation is required again.</div>}<RecordFields documentType={documentMeta.type} rows={activityRows} onChange={rows=>{setActivityRows(rows);setRecordErrors({});}} errors={recordErrors} disabled={!!busy||!!detail.archived}/></div></div><div className="modal-footer"><button className="button secondary" disabled={!!busy||!!detail.archived} onClick={()=>confirmActivity(false)}>Save changes</button><span><ShieldCheck size={15}/> Your confirmation enters these values into the profile.</span><button className="button primary" disabled={!!busy||!!detail.archived||sourceState.status!=='ready'} onClick={()=>confirmActivity()}><Check size={17}/> Confirm and calculate</button></div></>}
    {modal==='archive-record'&&archiveTarget&&<div className="modal-body"><h2>Archive {archiveTarget.name}?</h2><p>This removes the record from {monthLabel(archiveTarget.period)} calculations. Previous approved packs and their original evidence stay available.</p><p>You can restore this record later. Restoration requires confirmation before it contributes again.</p>{error&&<div role="alert" className="info-note">{error}<button className="text-button" onClick={()=>act('Reloading record',async()=>setArchiveTarget(await apiAction(`/documents/${archiveTarget.id}`)))}>Reload latest record</button></div>}<div className="flex-between"><button className="button secondary" disabled={!!busy} onClick={closeWorkspace}>Keep record</button><button className="button primary" disabled={!!busy||!!archiveTarget.archived} onClick={archiveRecord}>Archive record</button></div></div>}
    {modal==='metric'&&detail&&<div className="modal-body"><div className="flex-between"><span className="code">{detail.code} · {period}</span><Badge value={detail.badge}/></div><h2>{titles[detail.code]||detail.title}</h2><div className="detail-value">{number(detail.value,3)} <small>{detail.unit}</small></div><p className="field-note">Reporting coverage: {periodLabel} only. This is not an annual total.</p><MetricAvailability metric={detail}/><h3>Calculation / data path</h3><p className="method">{detail.method||'No source information available yet.'}</p>{detail.components?.map((c:Json,i:number)=><div className="detail-row" key={i}><span>{c.name}</span><strong>{number(c.value,3)} {c.unit}</strong></div>)}{detail.factors?.length>0&&<><h3>Versioned factors</h3>{detail.factors.map((f:Json,i:number)=><div className="factor-detail" key={i}><strong>{f.name||f.id}: {number(f.value,6)} {f.unit}</strong><p>{f.year} · {f.version} · {f.assumptions}</p>{f.source_value&&<p>Source value: {f.source_value} · {f.source_cell}<br/>{f.verification}</p>}<a href={f.source_url||f.source} target="_blank" rel="noreferrer">Source publication <ExternalLink size={13}/></a></div>)}</>}<h3>Evidence</h3><div className="evidence-list">{detail.evidence_ids?.length?detail.evidence_ids.map(sourceLink):<p className="muted">No document linked. Review the owner declaration or add evidence.</p>}</div><p className="field-note">Confirmation: {Array.isArray(detail.confirmed_by)?detail.confirmed_by.join(', ')||'See source records':detail.confirmed_by||'See source records'} · Partial-year coverage</p></div>}
    {modal==='declaration'&&<div className="modal-body"><span className="code">{declCode} · {period}</span><h2>{titles[declCode]}</h2><div className="info-note">This records your statement as the owner. It does not certify legal compliance.</div>{declCode==='G2.1'?<><PolicyEditor answer={declAnswer} onChange={setDeclAnswer} period={period} disabled={!!busy||role!=='owner'} owner={declarations.find(d=>d.code===declCode)?.declared_by} savedAt={declarations.find(d=>d.code===declCode)?.declared_at} previousAnswer={previousPolicy?.answer} previousPeriod={previousPolicy?.period} documents={declDocuments.map(d=>({id:d.id,name:d.name,period:d.period,archived:d.archived,unavailable:d.unavailable}))} selectedEvidence={declEvidence} onEvidenceChange={setDeclEvidence}/>{previousPolicyLoading&&<p role="status">Loading previous-month reference…</p>}{previousPolicyError&&<p role="status">Previous-month reference is unavailable. Your answers have not changed.</p>}</>:Object.entries(declAnswer).map(([key,value])=><label className="capitalize" key={key}>{key.replaceAll('_',' ')}{['count','injuries','fatalities','directors','year'].includes(key)?<input disabled={!!busy} type="number" min="0" max={key==='year'?new Date().getUTCFullYear():undefined} value={value as string|number} onChange={e=>setDeclAnswer({...declAnswer,[key]:e.target.value===''?'':Number(e.target.value)})}/>:<textarea disabled={!!busy} value={String(value)} onChange={e=>setDeclAnswer({...declAnswer,[key]:e.target.value})}/>}</label>)}{catalogNotice()}{declCode!=='G2.1'&&<><h3>Supporting attachments (optional)</h3>{declDocuments.map(d=><label className="checkbox-label" key={d.id}><input disabled={!!busy||!!((d.archived||d.unavailable)&&!declEvidence.includes(d.id))} type="checkbox" checked={declEvidence.includes(d.id)} onChange={e=>setDeclEvidence(e.target.checked?[...declEvidence,d.id]:declEvidence.filter(id=>id!==d.id))}/>{d.name} · {d.period}{d.archived?' · Archived — remove before saving':d.unavailable?' · Unavailable — remove before saving':''}</label>)}</>}{error&&<p className="danger" role="alert">{error}</p>}{declErrors&&<p className="danger">{declErrors}</p>}<button className="button primary full" disabled={role!=='owner'||!!busy||evidenceCatalogLoading||!!evidenceCatalogError} onClick={()=>act('Saving declaration',async()=>{const saved=await apiAction(`/declarations/${declCode}`,{method:'PUT',body:JSON.stringify({period,answer:declAnswer,evidence_ids:declEvidence})});acceptWorkspaceSection('declarations');setDeclarations(current=>replaceDeclaration(current,saved));declarationInitial.current={answer:structuredClone(declAnswer),evidence:[...declEvidence]};await refresh();setModal(null);setNotice('Owner declaration saved with attribution.');})}><Check size={16}/> Save owner declaration</button></div>}
    {modal==='new-request'&&<div className="modal-body new-request-form panel"><label>Customer name<input disabled={!!busy} value={newCustomer} onChange={e=>setNewCustomer(e.target.value)}/></label><label>Due date (optional)<input disabled={!!busy} type="date" value={dueDate} onChange={e=>setDueDate(e.target.value)}/></label><label>Questions · one per line<textarea disabled={!!busy} rows={8} value={newQuestions} onChange={e=>setNewQuestions(e.target.value)}/></label><p className="muted">Reporting period: {period}. Free-text questions will be matched to the selected disclosure catalogue.</p><button className="button primary full" disabled={!!busy||!newCustomer.trim()||!newQuestions.trim()} onClick={()=>act('Creating request',async()=>{const matched=await createAndMatchRequest(apiAction,{customer:newCustomer,period,...(dueDate?{due_date:dueDate}:{}),questions:newQuestions.split('\n').map(line=>line.trim()).filter(Boolean)},saved=>{if(activeRole.current!==role)return;showRequest(saved);setNewCustomer('');setNewQuestions('');setDueDate('');});acceptRequest(matched);})}>Match questions <ArrowRight size={16}/></button></div>}
    {modal==='request'&&detail&&<>{requestNotices()}<div className="request-review-heading"><div><span className="code">{detail.period} · Partial-year coverage</span><h2>{detail.customer}</h2><Badge value={detail.status}/></div><button className="button secondary" disabled={!!busy||dirtyQuestions.length>0} onClick={()=>act('Matching questions',async()=>{const matched=await apiAction(`/questionnaires/${detail.id}/map`,{method:'POST',body:JSON.stringify({})});acceptRequest(matched);setDirtyQuestions([]);setNotice('Proposed matches ready. Review every question.');})}><Sparkles size={16}/>Match questions</button></div><div className="request-disclaimer"><Eye size={15}/> Suggested matches are based on question wording. Rules prepare the numeric answers. Confirm every match.</div><div className="question-list">{detail.questions?.map((q:Json,i:number)=><Question key={`${q.id}-${q.version}-${requestEditorEpoch}`} q={q} period={detail.period} index={i} role={role} busy={!!busy} draft={questionDrafts[q.id]} onDraftChange={draft=>updateQuestionDraft(q,draft)} onSave={async(codes,manual)=>act('Saving reviewed answer',async()=>{const updated=await saveQuestionReview(apiAction,detail.id,q.id,{codes,reviewed:true,...(manual?{manual_answer:manual}:{})});if(activeRole.current!==role)return;acceptRequest(updated);setQuestionDrafts(current=>{const next={...current};delete next[q.id];return next;});setDirtyQuestions(ids=>ids.filter(id=>id!==q.id));setNotice('Question reviewed. Draft answer updated.');})} onEvidence={id=>{const doc=documents.find(d=>d.id===id);openDocument(doc||{id});}}/>)}</div><div className="review-progress-bar"><button className="button secondary" disabled={!!busy} onClick={()=>navigate(()=>{setModal(null);setRequestReturn(null);})}>Back to requests</button><span><strong>{review.reviewed} of {review.total}</strong> answers confirmed{dirtyQuestions.length>0?' · Save your edited mappings':''}</span><button className="button primary" disabled={!!busy||!review.canContinue} onClick={()=>setModal('owner-review')}>{role==='owner'?'Continue to owner review':'Review handoff'}<ArrowRight size={16}/></button></div></>}
    {modal==='owner-review'&&detail&&<>{requestNotices()}<div className="owner-review-layout"><div className="owner-response-preview panel"><div className="panel-heading"><div><h2>Answer preview</h2><p>{detail.customer} · {detail.period} · Partial-year coverage</p></div><Badge value={detail.status}/></div>{detail.questions?.map((q:Json)=><div className="owner-answer" key={q.id}><div><strong>{q.text}</strong><p>{q.answer||'Not available'}</p></div><Badge value={q.badge||'missing'}/></div>)}</div><div className="approval-section">{dirtyQuestions.length>0&&<div className="info-note" role="status">Confirm {dirtyQuestions.length} edited question{dirtyQuestions.length===1?'':'s'} before marking ready or sharing. The saved answers remain unchanged until confirmation.</div>}<h3><ShieldCheck size={19}/> Owner review and sharing</h3><div className="approval-summary"><div><strong>{detail.questions?.filter((q:Json)=>q.reviewed).length||0} / {detail.questions?.length||0}</strong><span>Answers reviewed</span></div><div><strong>{detail.questions?.filter((q:Json)=>q.badge==='estimated'||q.metrics?.some((m:Metric)=>m.badge==='estimated')).length||0}</strong><span>With estimates</span></div><div><strong>{detail.questions?.filter((q:Json)=>!q.reviewed||q.badge==='missing'||!q.codes?.length&&!q.manual_answer).length||0}</strong><span>Missing / unsupported</span></div><div><strong>{selectedEvidence.length}</strong><span>Attachments selected</span></div></div><p className="approval-period">Approval covers {detail.period} only · partial-year. The saved answers above, recipient below, and checked attachments form the customer pack.</p><p>Confirm each question first, then approve the saved answers, including any labelled estimates or missing information. Only selected source files are accessible to the customer.</p><label>Recipient<input value={recipient} onChange={e=>setRecipient(e.target.value)} disabled={role!=='owner'||!!busy}/></label>{catalogNotice()}<EvidenceSelector request={detail} documents={requestDocuments} selectedIds={selectedEvidence} onChange={setSelectedEvidence} disabled={role!=='owner'||!!busy||evidenceCatalogLoading||!!evidenceCatalogError}/><div className="flex-between approval-actions">{role==='clerk'&&<button className="button secondary" disabled={!!busy||!review.canContinue} onClick={()=>act('Marking ready for owner',async()=>{const updated=await apiAction(`/questionnaires/${detail.id}`,{method:'PUT',body:JSON.stringify({status:'ready_for_owner'})});if(activeRole.current!==role)return;acceptRequest(updated);setModal(null);setNotice('Sent to owner. No answers or attachments have been shared.');})}><ClipboardCheck size={16}/> Send to owner</button>}<span><LockKeyhole size={14}/> {role==='owner'?'You are approving an immutable snapshot.':'Only the owner can approve and share.'}</span><button className="button primary" disabled={role!=='owner'||!!busy||evidenceCatalogLoading||!!evidenceCatalogError||!recipient.trim()||!review.canContinue} onClick={()=>act('Approving and sharing',async()=>{const s=await apiAction(`/questionnaires/${detail.id}/approve-share`,{method:'POST',body:JSON.stringify({version:detail.version,recipient,selected_evidence_ids:selectedEvidence})});approvalInitial.current={recipient,evidence:[...selectedEvidence]};const approved=await loadApproval(apiAction,detail.id,s.token);if(activeRole.current!==role)return;acceptRequest(approved.request);acceptWorkspaceSection('shares');setShares(approved.shares);setToken(s.token);setPack(approved.pack);setModal('pack');setNotice('Approved pack saved on the server. Copy its link or download the PDF.');})}><ShieldCheck size={17}/> Approve & share</button></div></div></div></>}
    {modal==='pack'&&pack&&<div className="modal-body">{renderPack(pack)}<div className="share-link no-print"><label>Pack link · API must be running<input readOnly value={typeof window==='undefined'?'':`${window.location.origin}/?share=${encodeURIComponent(pack.token||token)}`}/></label><button className="button secondary" onClick={()=>act('Copying link',async()=>{await navigator.clipboard.writeText(`${window.location.origin}/?share=${encodeURIComponent(pack.token||token)}`);setNotice('Pack link copied. It can open in another browser while the frontend and API are running on this computer.');})}><Link2 size={15}/>Copy</button></div></div>}
    {modal==='help'&&<div className="modal-body"><div className="help-brand"><Leaf size={32}/><h2>Get ready before your customer asks.</h2></div><p>Prepare monthly records, reuse your ESG profile and review customer answers in one workspace.</p><div className="help-rows"><p><strong>Records and calculations.</strong> Enter quantities from your bills, confirm them, and inspect the factors and evidence behind each result. No automatic document reading is connected.</p><p><strong>Question matching.</strong> Suggestions use question wording. Confirm or correct each disclosure before preparing an answer.</p><p><strong>Owner approval.</strong> Review the recipient, answers and attachments, then approve a fixed snapshot. Copy its pack link or download its PDF to send to a customer.</p><p><strong>Storage and access.</strong> Records, edits and approved packs are saved by the backend in Supabase; source files use Supabase Storage. Pack links can open in another browser while this frontend and API are running. A localhost link works only on this computer. The role selector sends a simulated demo role for backend permission checks; it is not account authentication. Customers need an approved share token and can open only its selected evidence.</p><p><strong>Sample records.</strong> The starting workspace includes fictional September records and declarations. Source previews identify these records as samples.</p></div><a className="text-button" href="https://sedg.capitalmarketsmalaysia.com/wp-content/uploads/2025/07/SEDG-v2.pdf" target="_blank" rel="noreferrer">Read the SEDG guide <ExternalLink size={14}/></a>{role==='owner'&&<div className="reset-area"><h3>Restore sample workspace</h3><p>Restores fictional records and removes server demo changes and share links. Available only when demo reset is enabled on the backend.</p><button className="button secondary" disabled={!!busy} onClick={()=>{if(window.confirm('Restore sample records? This removes current edits, uploaded files and saved packs from the server demo workspace. The backend must allow demo reset.'))act('Restoring sample records',async()=>{await apiAction('/demo/reset',{method:'POST'});await refresh();setModal(null);setNotice('Sample workspace restored.');});}}><RefreshCw size={15}/> Restore sample records</button></div>}</div>}
    </section></div>}
    {unsavedOpen&&<UnsavedChangesDialog onKeep={()=>{navigatorRef.current!.keepEditing();setUnsavedOpen(false);}} onDiscard={()=>{setUnsavedOpen(false);navigatorRef.current!.discardAndContinue();}}/>}
  </div>;
}



function Question({q,period,index,role,busy,onSave,onEvidence,draft,onDraftChange}:{q:Json;period?:string;index:number;role:Role;busy:boolean;draft?:{codes:string[];manual:string};onDraftChange:(draft:{codes:string[];manual:string})=>void;onSave:(codes:string[],manual:string)=>Promise<void>;onEvidence:(id:string)=>void}) {
  const [selected,setSelected]=useState<string[]>(draft?.codes??(q.reviewed?(q.codes||[]):(q.proposed_codes?.length?q.proposed_codes:q.codes||[])));
  const [manual,setManual]=useState(draft?.manual??q.manual_answer??'');
  const changed=questionDraftChanged(q,{codes:selected,manual});
  return <article className="question-card"><div className="question-top"><span className="question-index">{String(index+1).padStart(2,'0')}</span><h3>{q.text}</h3><Badge value={changed?'needs_review':q.reviewed?'reviewed':'needs_review'}/></div><p className="section-kicker">PROPOSED MATCH · HUMAN REVIEW REQUIRED</p><p className="mapping-rationale">{q.rationale||'Match this question to a disclosure, or keep it unsupported.'}{q.uncertainty&&<span className="mapping-uncertainty">{q.uncertainty}</span>}</p>{selected.includes('S1.1')&&<div className="assurance-note"><AlertTriangle size={17}/><span>An incident declaration does not establish that child or forced labour is absent. Review broader assurance requests separately.</span></div>}<div className="mapping-selection">{selected.length?selected.map(code=><span key={code}>{titles[code]} <small>{code}</small></span>):<span className="owner-needed">{q.rationale?.startsWith('Awaiting')?'Match questions or choose a disclosure':'Owner answer needed · No supported match selected'}</span>}</div><details className="mapping-editor"><summary>Change disclosure match</summary><fieldset disabled={busy}><legend>SEDG matches · select all that apply</legend><div className="code-options">{codes.map(code=><label className={selected.includes(code)?'selected':''} title={titles[code]} key={code}><input type="checkbox" checked={selected.includes(code)} onChange={e=>{const next=e.target.checked?[...selected,code]:selected.filter(c=>c!==code);setSelected(next);onDraftChange({codes:next,manual});}}/>{titles[code]} <small>{code}</small></label>)}</div></fieldset></details><DraftAnswer question={q} period={period} changed={changed}/>{(!selected.length||!!q.unsupported_parts?.length)&&<label>Owner response (optional)<textarea value={manual} disabled={role!=='owner'||busy} onChange={e=>{setManual(e.target.value);onDraftChange({codes:selected,manual:e.target.value});}} placeholder={role==='owner'?'Enter an attributed declaration, or leave as Not available':'Only the owner can enter a manual answer'}/></label>}<div className="question-bottom"><div className="evidence-list">{(q.evidence_ids||[]).map((id:string)=><button key={id} className="evidence-link" onClick={()=>onEvidence(id)}><FileText size={13}/>View source {id} <ArrowUpRight size={12}/></button>)}</div><button className={`button ${q.reviewed&&!changed?'secondary':'primary'} small`} disabled={busy} onClick={()=>onSave(selected,manual)}><Check size={14}/>{q.reviewed&&!changed?'Confirm again':'Confirm mapping & answer'}</button></div></article>;
}


function ExtractionMetadata({extraction}:{extraction?:Json|null}) {
  if(!extraction)return <p className="field-note">Enter quantities from the source document.</p>;
  return <div className="extraction-metadata"><dl><div><dt>Supplier</dt><dd>{extraction.supplier_name||'Missing'}</dd></div><div><dt>Document date</dt><dd>{extraction.document_date||'Missing'}</dd></div><div><dt>Reporting period</dt><dd>{extraction.period_start||'Missing'} to {extraction.period_end||'Missing'}</dd></div></dl>{(extraction.uncertainty_notes||[]).map((note:string,i:number)=><p key={i}><AlertTriangle size={12}/>{note}</p>)}</div>;
}

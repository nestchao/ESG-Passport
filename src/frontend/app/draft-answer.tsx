import {DeclarationSummary} from './declaration-summary';
import {cleanDecimal} from './record-fields.mjs';
import {isValidPeriod,monthLabel} from './monthly.mjs';

type Data=Record<string,any>;
const provenance:Record<string,{label:string;tone:string}>={auto:{label:'Calculated',tone:'complete'},declared:{label:'Owner declared',tone:'complete'},estimated:{label:'Estimated',tone:'attention'},missing:{label:'Missing',tone:'neutral'}};
const present=(value:any)=>value!==null&&value!==undefined&&value!=='';
const displayQuantity=(value:any)=>{const number=Number(value);return Number.isFinite(number)?new Intl.NumberFormat('en-MY',number!==0&&Math.abs(number)<0.001?{maximumSignificantDigits:3}:{maximumFractionDigits:3}).format(number):cleanDecimal(value);};
const titleCase=(value:string)=>value?value.charAt(0).toUpperCase()+value.slice(1):'Quantity';

export function DraftAnswer({question:q,period,changed=false}:{question:Data;period?:string;changed?:boolean}) {
 const metrics:Data[]=Array.isArray(q.metrics)?q.metrics:[];
 const owner=q.manual_declaration?.declared_by;
 const month=period||q.period||q.manual_declaration?.period;
 const text=typeof q.answer==='string'?q.answer:'Not available. Confirm a mapping to prepare an answer.';
 return <section className="draft-answer answer-preview" aria-label="Prepared answer preview">
  <div className="answer-preview-heading"><div><span className="section-kicker">ANSWER PREVIEW</span><h4>{q.reviewed?'Prepared answer':'Draft answer'}</h4></div>
   {month&&<span className="answer-period">{isValidPeriod(month)?monthLabel(month):month}<small>Partial-year coverage</small></span>}
  </div>
  {changed&&<p className="answer-review-note" role="status">Showing the last saved answer. Save and confirm your changes to update this preview.</p>}
  {metrics.length&&!owner?<div className="answer-metric-list">{metrics.map((metric,index)=>{
   const badge=provenance[metric.badge]||provenance.missing;
   const declared=metric.code?.startsWith('G')||metric.code?.startsWith('S');
   return <div className="answer-metric" key={`${metric.code}-${index}`}>
    <div className="answer-metric-heading"><h5>{metric.title||'Disclosure'} <span>{metric.code}</span></h5><span className={`status-tag ${badge.tone}`}>{badge.label}</span></div>
    {!present(metric.value)?<p className="answer-unavailable">Not available</p>:declared?<DeclarationSummary code={metric.code} value={metric.value}/>:<p className="answer-value" title={`${cleanDecimal(metric.value)} ${metric.unit||''}`}>{displayQuantity(metric.value)}{metric.unit&&<span>{metric.unit}</span>}</p>}
    {!declared&&metric.components?.length>1&&<dl className="answer-components">{metric.components.map((part:Data,i:number)=><div key={i}><dt>{titleCase(part.name||'Quantity')}{part.pending?' · review incomplete':''}</dt><dd>{present(part.value)?`${displayQuantity(part.value)} ${part.unit||''}`:'Not available'}</dd></div>)}</dl>}
    {metric.badge==='estimated'&&<p className="answer-assumption">Uses an estimate or proxy. Assumptions stay with this answer.</p>}
    {metric.badge==='declared'&&<p className="answer-attribution">Owner declaration by {(metric.confirmed_by||[]).join(', ')||'Owner'}</p>}
   </div>;
  })}</div>:<div className="answer-text-preview"><p>{text}</p>{owner&&<div className="answer-owner-footer"><span className="status-tag complete">Owner declared</span><span className="answer-attribution">Owner declaration by {owner}</span></div>}</div>}
  {metrics.length>0&&(q.unsupported_parts||[]).map((part:string)=><p key={part} className="answer-review-note">{part}: Not available — outside supported disclosures.</p>)}
 </section>;
}

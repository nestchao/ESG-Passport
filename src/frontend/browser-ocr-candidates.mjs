/** Conservative ESG candidate detection from OCR text, entirely client-side.
 * Does NOT attest values, invent a waste outcome, or persist any evidence.
 */
const quantityWithUnit=/(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(kwh|m[³3]|litres?|liters?|kg|tonnes?|\bt\b|\bL\b)(?![a-z])/gi;
const patterns={electricity:/electric|energy|usage|consum|penggunaan|kegunaan|tenaga|jumlah|total/i,water:/water|usage|consum|penggunaan|kegunaan|air|jumlah|total/i,diesel:/diesel|fuel|litre|bahan api|isipadu/i,petrol:/petrol|gasoline|fuel|bahan api|isipadu/i};
const desired={electricity:['kWh'],water:['m3','L'],diesel:['L'],petrol:['L']};
const normalizeUnit=x=>{const u=x.toLowerCase();return u==='kwh'?'kWh':u==='m³'||u==='m3'?'m3':u==='l'||u.startsWith('lit')?'L':u==='kg'?'kg':'t';};
function matches(line){return Array.from(line.matchAll(quantityWithUnit),m=>({value:m[1].replaceAll(',',''),unit:normalizeUnit(m[2]),source:line.slice(0,180)}));}
function periodRange(month){if(!/^20\d{2}-(0[1-9]|1[0-2])$/.test(month))throw new Error('Choose a valid reporting month');const [year,m]=month.split('-').map(Number);return {start:`${month}-01`,end:`${month}-${String(new Date(Date.UTC(year,m,0)).getUTCDate()).padStart(2,'0')}`};}
function parseDate(v){const parts=v.split(/[\/\-]/);if(parts[0].length===4){const parsed=new Date(`${parts[0]}-${parts[1].padStart(2,'0')}-${parts[2].padStart(2,'0')}T00:00:00Z`);return !Number.isNaN(+parsed)&&parsed.toISOString().slice(0,10)===`${parts[0]}-${parts[1].padStart(2,'0')}-${parts[2].padStart(2,'0')}`?parsed.toISOString().slice(0,10):null;}const [d,m,y]=parts;const iso=`${y}-${m.padStart(2,'0')}-${d.padStart(2,'0')}`;const parsed=new Date(`${iso}T00:00:00Z`);return Number.isNaN(+parsed)?null:parsed.toISOString().slice(0,10)===iso?iso:null;}
export function parseBrowserBill(text,category,month){
 if(!Object.hasOwn({...patterns,waste:true},category))throw new Error('Unsupported document category');
 if(typeof text!=='string'||text.length>60000)throw new Error('Text is too long');
 const lines=text.split(/\r?\n/).map(s=>s.replace(/\s+/g,' ').trim()).filter(Boolean).slice(0,700);
 const notes=['Unverified browser OCR candidates: compare every field with the original before use.'];
 let {start,end}=periodRange(month);
 const dates=/\b(?:20\d\d[-\/]\d{1,2}[-\/]\d{1,2}|\d{1,2}[-\/]\d{1,2}[-\/]20\d\d)\b/g;
 let documentDate=null;
 for(let i=0;i<lines.length;i++){
  if(/(?:bill(?:ing)?|reading|usage)\s*period|tempoh\s*(?:bil|penggunaan)/i.test(lines[i])){
   const found=[...lines[i].matchAll(dates)].map(x=>parseDate(x[0])).filter(Boolean);
   if(found.length===2&&found[0]<=found[1]){start=found[0];end=found[1];break;}
  }
 }
 for(const line of lines){if(/\b(?:date|tarikh|issued|bil date)\s*:/i.test(line)){
   documentDate=[...line.matchAll(dates)].map(x=>parseDate(x[0])).find(Boolean)??null;if(documentDate)break;
 }}
 if(category==='waste'&&documentDate&&start===`${month}-01`)start=end=documentDate;
 if(start.slice(0,7)!==month||end.slice(0,7)!==month)notes.push('Printed dates differ from the selected reporting month. Resolve before confirming.');
 let supplier=lines.slice(0,4).find(x=>/[A-Z]{3}/i.test(x)&&!/(?:invoice|bill date|account no|kwh|litres?|m3)/i.test(x))?.slice(0,150)||'';
 let unit='',quantity='',source='',suggestedCategory=category;
 if(category==='waste'){
  const net=lines.filter(x=>/\bnet\b|berat\s*bersih/i.test(x)&&!/\bgross\b|\btare\b/i.test(x)).flatMap(matches).filter(x=>['kg','t'].includes(x.unit));
  const unique=new Map(net.map(v=>[v.value+'|'+v.unit,v]));
  if(unique.size===1){const v=[...unique.values()][0];quantity=v.value;unit=v.unit;source=v.source;
   notes.push('Only NET TRANSFER weight was detected. A transfer does not prove generated, diverted or disposed waste.');
  }else notes.push('No single reliable NET weight found; enter the weight manually.');
  const route=lines.find(x=>/^\s*(?:tujuan|destination|destinasi|treatment\s*route|route)\s*[:\-]/i.test(x));
  if(route&&/recycl|kitar semula/i.test(route))notes.push('Possible recycling destination noted, but completed diversion is NOT verified.');
  suggestedCategory='unclassified_waste_transfer';
 }else{
  const label=patterns[category];const results=[];
  for(let i=0;i<lines.length;i++){
   const around=lines.slice(Math.max(0,i-1),Math.min(lines.length,i+2)).join(' ');
   if(!label.test(around))continue;
   for(const value of matches(lines[i]))if(desired[category].includes(value.unit))results.push(value);
  }
  const unique=new Map(results.map(x=>[x.value+'|'+x.unit,x]));
  if(unique.size===1){const x=[...unique.values()][0];quantity=x.value;unit=x.unit;source=x.source;}
  else notes.push(unique.size===0?'No reliably labeled quantity and unit found; enter them manually.':'Conflicting quantities found; choose the correct one manually.');
 }
 if(!quantity)notes.push('The OCR text may be incomplete or unclear; manual review is required.');
 return {category:suggestedCategory,quantity,unit,period_start:start,period_end:end,document_date:documentDate??'',supplier,source_reference:source,notes,rawText:text.slice(0,60000),verified:false};
}

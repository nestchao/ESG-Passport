const LABELS = {electricity:'Electricity',diesel:'Diesel',petrol:'Petrol',water:'Purchased water',waste:'Waste',waste_generated:'Waste generated',waste_diverted:'Waste diverted',waste_disposed:'Waste disposed'};
const UNITS = {electricity:['kWh'],diesel:['L'],petrol:['L'],water:['m3','L'],waste_generated:['kg','t'],waste_diverted:['kg','t'],waste_disposed:['kg','t']};
export function categoryLabel(code) {return LABELS[code] || String(code || 'Record').replaceAll('_',' ');}
export function allowedCategories(type) {return type==='waste'?['waste_generated','waste_diverted','waste_disposed']:UNITS[type]?[type]:[];}
export function allowedUnits(category) {return [...(UNITS[category] || [])];}
export function cleanDecimal(value) {const text=String(value ?? '').trim();if(!text.includes('.')||/[eE]/.test(text))return text;return text.replace(/(\.\d*?)0+$/,'$1').replace(/\.$/,'');}
export function normaliseActivities(rows) {return rows.map(row=>({...row,quantity:cleanDecimal(row.quantity)}));}
export function activityKey(rows) {return JSON.stringify(rows.map(row=>({category:row.category||'',quantity:cleanDecimal(row.quantity),unit:row.unit||'',period_start:row.period_start||'',period_end:row.period_end||'',estimated:!!row.estimated,assumptions:row.assumptions||'',allocated_period:row.allocated_period||null})));}
function validQuantity(value) {
 if(typeof value==='boolean'||value==null)return false;
 const text=String(value).trim(); const match=/^([+-]?)(\d*(?:\.\d*)?)(?:[eE]([+-]?\d+))?$/.exec(text);
 if(!match||!/[0-9]/.test(match[2]))return false;
 const [whole,fraction='']=match[2].split('.'); const digits=whole+fraction;
 if(match[1]==='-'&&/[1-9]/.test(digits))return false;
 if(!/[1-9]/.test(digits))return true;
 const exponent=Number(match[3]||0);if(!Number.isSafeInteger(exponent)||Math.abs(exponent)>1000)return false;
 const point=whole.length+exponent;const first=digits.search(/[1-9]/);const last=digits.search(/[1-9]0*$/);
 const integerDigits=Math.max(0,point-first);const fractionDigits=Math.max(0,last+1-point);
 return integerDigits<=18&&fractionDigits<=12&&integerDigits+fractionDigits<=30;
}
function validDate(value){if(!/^\d{4}-\d{2}-\d{2}$/.test(value||''))return false;const date=new Date(`${value}T00:00:00Z`);return !Number.isNaN(date.valueOf())&&date.toISOString().slice(0,10)===value;}
export function validateActivities(rows,documentType,period) {
 const errors={}; const seen=new Set();
 rows.forEach((row,index)=>{const set=(field,message)=>{errors[`activities.${index}.${field}`]=message;};
 if(!allowedCategories(documentType).includes(row.category))set('category','Choose a category matching this document type.');else if(seen.has(row.category))set('category','Use one total per category per document.');seen.add(row.category);
 if(!validQuantity(row.quantity))set('quantity','Enter a nonnegative quantity with at most 18 whole and 12 decimal digits.');
 if(!allowedUnits(row.category).includes(row.unit))set('unit','Choose a supported unit for this category.');
 const startValid=validDate(row.period_start),endValid=validDate(row.period_end);
 if(!startValid)set('period_start','Enter a valid start date.');if(!endValid)set('period_end','Enter a valid end date.');
 if(row.allocated_period!=null&&!/^\d{4}-(0[1-9]|1[0-2])$/.test(row.allocated_period))set('allocated_period','Choose a valid allocation month.');
 if(typeof row.estimated!=='boolean')set('estimated','Choose whether this value is estimated.');
 if(row.estimated&&!String(row.assumptions||'').trim())set('assumptions','Describe the estimation method.');
 if(String(row.assumptions||'').length>4000)set('assumptions','Use at most 4000 characters.');
 if(startValid&&endValid){const start=row.period_start.slice(0,7),end=row.period_end.slice(0,7);
 if(row.period_start>row.period_end)set('period_end','End date must follow the start date.');
 if(start!==end){if(!row.estimated)set('estimated','Mark a cross-month allocation as estimated.');if(!String(row.assumptions||'').trim())set('assumptions','Describe the allocation method.');if(row.allocated_period!==period)set('allocated_period','Explicitly allocate to the selected reporting month.');else if(period<start||period>end)set('allocated_period','Allocation must fall within the source period.');}
 else if(start!==period|| ![undefined,null,'',period].includes(row.allocated_period))set('period_start','Dates must belong to the selected reporting month.');
 }
 });return errors;
}


// A type correction must never reinterpret a previous numeric quantity in a new unit.
export function reclassifyActivities(rows,type) {
 const category=allowedCategories(type)[0];
 if(!category)throw new RangeError('Unsupported document category.');
 const first=rows[0]||{};
 return [{category,quantity:'',unit:allowedUnits(category)[0],period_start:first.period_start||'',period_end:first.period_end||'',estimated:false,assumptions:'',allocated_period:null}];
}

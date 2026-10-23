'use client';
import {useId} from 'react';
import {allowedCategories,allowedUnits,categoryLabel} from './record-fields.mjs';
type Row=Record<string,any>;
type Props={documentType:string;rows:Row[];onChange:(rows:Row[])=>void;errors:Record<string,string>;disabled:boolean};
const unitLabel=(unit:string)=>unit==='m3'?'m³':unit;
export function RecordFields({documentType,rows,onChange,errors,disabled}:Props){
 const prefix=useId();const categories=allowedCategories(documentType);const unused=categories.filter(category=>!rows.some(row=>row.category===category));
 const update=(index:number,field:string,value:any)=>onChange(rows.map((row,i)=>i===index?{...row,[field]:value}:row));
 return <>{rows.map((row,index)=>{
 const key=(field:string)=>`activities.${index}.${field}`;
 const props=(field:string)=>({id:`${prefix}-${index}-${field}`,'data-field':key(field),'aria-invalid':errors[key(field)]?true:undefined,'aria-describedby':errors[key(field)]?`${prefix}-${index}-${field}-error`:undefined,disabled});
 const error=(field:string)=>errors[key(field)]?<span className="field-error danger" id={`${prefix}-${index}-${field}-error`}>{errors[key(field)]}</span>:null;
 const units=row.category?allowedUnits(row.category):documentType==='waste'?['kg','t']:allowedUnits(row.category);const crossMonth=row.period_start?.slice(0,7)!==row.period_end?.slice(0,7);
 return <div className="activity-editor" key={index}><div className="flex-between"><strong>Quantity {index+1}</strong>{rows.length>1&&<button type="button" disabled={disabled} className="text-button danger" onClick={()=>onChange(rows.filter((_,i)=>i!==index))}>Remove</button>}</div>
 <label>Category<select {...props('category')} value={row.category||''} onChange={event=>{const category=event.target.value;onChange(rows.map((item,i)=>i===index?{...item,category,unit:allowedUnits(category).includes(item.unit)?item.unit:allowedUnits(category)[0]||''}:item));}}>{!categories.includes(row.category)&&<option value={row.category||''}>Choose category</option>}{categories.map(category=><option key={category} value={category}>{categoryLabel(category)}</option>)}</select>{error('category')}</label>
 <p className="field-note">Source: {row.source_reference||'Page 1; manually checked'}{row.uncertainty?` · ${row.uncertainty}`:''}</p>
 <div className="two-fields"><label>Quantity<input {...props('quantity')} type="text" inputMode="decimal" value={row.quantity??''} onChange={event=>update(index,'quantity',event.target.value)}/>{error('quantity')}</label><label>Unit<select {...props('unit')} value={row.unit||''} onChange={event=>update(index,'unit',event.target.value)}>{!units.includes(row.unit)&&<option value={row.unit||''}>Choose unit</option>}{units.map(unit=><option key={unit} value={unit}>{unitLabel(unit)}</option>)}</select>{error('unit')}</label></div>
 <div className="two-fields"><label>Period start<input {...props('period_start')} type="date" value={row.period_start||''} onChange={event=>update(index,'period_start',event.target.value)}/>{error('period_start')}</label><label>Period end<input {...props('period_end')} type="date" value={row.period_end||''} onChange={event=>update(index,'period_end',event.target.value)}/>{error('period_end')}</label></div>
 {(crossMonth||errors[key('allocated_period')])&&<label>Allocate this quantity to month<input {...props('allocated_period')} type="month" value={row.allocated_period||''} onChange={event=>update(index,'allocated_period',event.target.value)}/><span className="field-note">Enter the allocated quantity above, mark it estimated, and describe the allocation method.</span>{error('allocated_period')}</label>}
 <label className="checkbox-label"><input {...props('estimated')} type="checkbox" checked={!!row.estimated} onChange={event=>update(index,'estimated',event.target.checked)}/> This value is estimated or allocated{error('estimated')}</label>
 {(row.estimated||crossMonth||errors[key('assumptions')])&&<label>Method and assumptions<textarea {...props('assumptions')} value={row.assumptions||''} onChange={event=>update(index,'assumptions',event.target.value)}/>{error('assumptions')}</label>}
 </div>;})}{unused.length>0&&<button type="button" className="text-button" disabled={disabled} onClick={()=>{const category=unused[0];const first=rows[0]||{};onChange([...rows,{category,quantity:'',unit:allowedUnits(category)[0],period_start:first.period_start||'',period_end:first.period_end||'',estimated:false}]);}}>Add quantity</button>}</>;
}

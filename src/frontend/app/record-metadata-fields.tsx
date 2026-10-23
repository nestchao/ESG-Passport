'use client';
import {useId} from 'react';

type Metadata = {name:string;period:string;type:string};
type Props = Metadata & {onChange:(metadata:Metadata)=>void;errors?:Record<string,string>;disabled?:boolean};

export function RecordMetadataFields({name,period,type,onChange,errors={},disabled=false}:Props) {
  const prefix = useId();
  const fieldProps = (field:string) => ({id:`${prefix}-${field}`,'data-field':field,disabled,'aria-invalid':errors[field] ? true : undefined,'aria-describedby':errors[field] ? `${prefix}-${field}-error` : undefined});
  const error = (field:string) => errors[field] ? <span className="field-error danger" id={`${prefix}-${field}-error`}>{errors[field]}</span> : null;
  return <><label>Document category<select {...fieldProps('type')} value={type} onChange={event=>onChange({name,period,type:event.target.value})}><option value="electricity">Electricity</option><option value="diesel">Diesel</option><option value="petrol">Petrol</option><option value="water">Purchased water</option><option value="waste">Waste</option></select>{error('type')}</label><div className="two-fields">
    <label>Record name<input {...fieldProps('name')} value={name} onChange={event=>onChange({name:event.target.value,period,type})}/>{error('name')}</label>
    <label>Record reporting month<input {...fieldProps('period')} type="month" min="0001-01" max="9999-12" value={period} onChange={event=>onChange({name,period:event.target.value,type})}/>{error('period')}</label>
  </div></>;
}

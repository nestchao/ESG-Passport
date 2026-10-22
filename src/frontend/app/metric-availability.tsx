import {cleanDecimal} from './record-fields.mjs';
export function MetricAvailability({metric}:{metric:Record<string,any>}){
  if(metric.value!=null)return null;
  const available=(metric.components||[]).filter((component:Record<string,any>)=>component.value!=null);
  if(!available.length)return null;
  return <div className="metric-availability"><strong>Review incomplete</strong><p>Available partial quantities: {available.map((component:Record<string,any>)=>`${String(component.name||'Quantity').replaceAll('_',' ')}: ${cleanDecimal(component.value)} ${component.unit||''}`).join(' · ')}. These are not a complete disclosure.</p></div>;
}

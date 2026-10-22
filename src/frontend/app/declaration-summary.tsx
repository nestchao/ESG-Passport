import { declarationText, policyRows } from './presentation.mjs';

export function DeclarationSummary({code,value}:{code:string;value:any}) {
  const policies=code==='G2.1'?policyRows(value):[];
  if(code==='G2.1'&&policies.length) return <div className="policy-summary" role="list" aria-label="Policy status">
    {policies.map(policy=><div role="listitem" className="policy-summary-row" key={policy.name}>
      <span>{policy.name}</span><span className={`status-tag ${policy.tone}`}>{policy.label}</span>
    </div>)}
  </div>;
  return <p className="declaration-answer">{declarationText(code,code==='G2.1'?null:value)}</p>;
}

export const POLICIES=Object.freeze([
  {name:'Code of Conduct',description:'Sets expectations for ethical behaviour, fair treatment and responsible business decisions.',icon:'conduct'},
  {name:'Anti-Corruption Policy',description:'Explains how your business prevents bribery, improper gifts and conflicts of interest.',icon:'corruption'},
  {name:'Whistleblowing Policy',description:'Gives people a safe way to report concerns and explains how they are protected from retaliation.',icon:'reporting'},
  {name:'Health and Safety Policy',description:'Sets out how your business protects people at work and manages workplace health and safety risks.',icon:'safety'},
].map(Object.freeze));
export const POLICY_STATUSES=Object.freeze(['in place','not in place','unknown']);
export function policyStatus(answer,name){
  const rows=Array.isArray(answer?.policies)?answer.policies:[];
  const status=rows.find(row=>row?.name===name)?.status;
  return POLICY_STATUSES.includes(status)?status:'unknown';
}
export function canonicalPolicyAnswer(answer){
  return {policies:POLICIES.map(({name})=>({name,status:policyStatus(answer,name)}))};
}
export function setPolicyStatus(answer,name,status){
  const next=canonicalPolicyAnswer(answer);
  if(POLICY_STATUSES.includes(status))next.policies=next.policies.map(row=>row.name===name?{...row,status}:row);
  return next;
}
export function knownPolicyCount(answer){return canonicalPolicyAnswer(answer).policies.filter(row=>row.status!=='unknown').length;}
export function policyStatusLabel(status){return status==='in place'?'In place':status==='not in place'?'Not in place':'Unknown';}

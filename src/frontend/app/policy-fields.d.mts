export type PolicyStatus='in place'|'not in place'|'unknown';
export type PolicyAnswer={policies:{name:string;status:PolicyStatus}[]};
export const POLICIES:readonly Readonly<{name:string;description:string;icon:string}>[];
export const POLICY_STATUSES:readonly PolicyStatus[];
export function policyStatus(answer:unknown,name:string):PolicyStatus;
export function canonicalPolicyAnswer(answer:unknown):PolicyAnswer;
export function setPolicyStatus(answer:unknown,name:string,status:PolicyStatus):PolicyAnswer;
export function knownPolicyCount(answer:unknown):number;
export function policyStatusLabel(status:unknown):string;

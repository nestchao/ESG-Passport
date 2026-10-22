const sortedIds=ids=>[...new Set(ids||[])].sort();
function stable(value){
  if(Array.isArray(value))return value.map(stable);
  if(value&&typeof value==='object')return Object.fromEntries(Object.keys(value).sort().map(key=>[key,stable(value[key])]));
  return value;
}
export function approvalKey(recipient,ids){return JSON.stringify([recipient,sortedIds(ids)]);}
export function declarationKey(answer,ids){
  const numeric=new Set(['count','injuries','fatalities','directors','year']);
  const normal=Object.fromEntries(Object.entries(answer||{}).map(([key,value])=>[key,numeric.has(key)?String(value??''):value]));
  return JSON.stringify([stable(normal),sortedIds(ids)]);
}
export function questionDraftChanged(question,draft){
  const baseline=question.reviewed?(question.codes||[]):question.proposed_codes?.length?question.proposed_codes:question.codes||[];
  return JSON.stringify(sortedIds(baseline))!==JSON.stringify(sortedIds(draft.codes))||String(question.manual_answer||'')!==draft.manual;
}
export function createDraftNavigator({isDirty,onDiscard}){
  let pending=null;
  return {
    request(action,options={}){
      if(!(options.dirty??isDirty())){action();return false;}
      pending={action,discard:options.discard||onDiscard};return true;
    },
    keepEditing(){pending=null;},
    discardAndContinue(){const next=pending;pending=null;if(next){next.discard();next.action();}},
  };
}
export function warnBeforeUnload(event){event.preventDefault();event.returnValue='';}

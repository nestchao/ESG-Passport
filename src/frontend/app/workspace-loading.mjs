const core=['profile','documents','questionnaires'];

/** Each load starts a new role-scoped generation. Optional failures settle independently. */
export function createWorkspaceLoader(){
  let generation=0;
  const accepted={};
  return {
    invalidate(){generation++;},
    accept(key){accepted[key]=(accepted[key]||0)+1;},
    load({role,request,onState}){
      const current=++generation;
      const keys=[...core,'declarations',...(role==='owner'?['shares']:[])];
      const tasks={};
      for(const key of keys){
        const revision=accepted[key]||0;
        onState(key,{status:'loading'});
        let pending;
        try{pending=request(key);}catch(error){pending=Promise.reject(error);}
        tasks[key]=Promise.resolve(pending).then(value=>{
          if(current!==generation||revision!==(accepted[key]||0))return false;
          onState(key,{status:'ready',value});return true;
        },error=>{
          if(current!==generation||revision!==(accepted[key]||0))return false;
          onState(key,{status:'error',error:error?.message||'Could not load this section.'});throw error;
        });
        // Every section has a rejection handler even when it is outside the core await.
        tasks[key].catch(()=>{});
      }
      return Promise.allSettled(core.map(key=>tasks[key])).then(results=>{
        if(current!==generation)return false;
        const failed=results.find(result=>result.status==='rejected');
        if(failed)throw failed.reason;
        return true;
      });
    }
  };
}

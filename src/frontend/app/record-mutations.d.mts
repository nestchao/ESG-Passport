export function refreshAfterRecordChange(refresh:()=>Promise<unknown>,onRefreshError:(message:string)=>void):Promise<boolean>;

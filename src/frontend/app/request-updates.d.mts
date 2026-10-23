type Data=Record<string,any>;
type Api=(path:string,options?:RequestInit)=>Promise<any>;
export function replaceRequest<T extends Data>(requests:T[],updated:T):T[];
export function saveQuestionReview(api:Api,requestId:string,questionId:string,body:Data):Promise<Data>;
export function loadApproval(api:Api,requestId:string,token:string):Promise<{request:Data;shares:Data[];pack:Data}>;

export type DemoConfig = {enabled:false} | {enabled:true;publicOrigin?:string;password:string;secret:string;backendKey:string;backendUrl:string};
export function getDemoConfig(environment?:Record<string,string|undefined>):DemoConfig;
export function accessGate(request:Request,config:DemoConfig):Response|null;
export function handleLogin(request:Request,config:DemoConfig,limiter?:(request:Request)=>boolean):Promise<Response>;
export function handleLogout(request:Request,config:DemoConfig):Response;
export function proxyBackend(request:Request,segments:string[],config:DemoConfig,fetchImpl?:typeof fetch):Promise<Response>;

export function safeReturnTo(value:unknown):string;

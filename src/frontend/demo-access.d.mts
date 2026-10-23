export type DemoConfig = {enabled:false} | {enabled:true;publicOrigin?:string;password:string;secret:string;backendKey:string;backendUrl:string};
export function getDemoConfig(environment?:Record<string,string|undefined>):DemoConfig;
export function accessGate(request:Request,config:DemoConfig):Response|null;
export function handleLogin(request:Request,config:DemoConfig,limiter?:(request:Request)=>boolean):Promise<Response>;
export function handleLogout(request:Request,config:DemoConfig):Response;
export function proxyBackend(request:Request,segments:string[],config:DemoConfig,fetchImpl?:typeof fetch):Promise<Response>;

export function safeReturnTo(value:unknown):string;

export const LOGIN_CSRF_COOKIE:string;
export function createLoginCsrf(config:DemoConfig,now?:number):string;
export function verifyLoginCsrf(token:string|undefined,config:DemoConfig,now?:number):boolean;
export function loginCsrfCookie(token:string,secure?:boolean):string;
export function loginCsrfFromRequest(request:Request):string|undefined;

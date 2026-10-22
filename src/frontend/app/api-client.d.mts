export type DemoRole='owner'|'clerk'|'customer';
export function createApiClient(options?:{baseUrl?:string;fetchImpl?:typeof fetch}):{
  request(path:string,options?:RequestInit,role?:DemoRole):Promise<any>;
  preview(documentId:string,role?:DemoRole):Promise<string>;
};
export function apiRequest(path:string,options?:RequestInit,role?:DemoRole):Promise<any>;
export function apiPreview(documentId:string,role?:DemoRole):Promise<string>;

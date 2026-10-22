export function createDemo(storage?: {load?:()=>Promise<any>;save?:(value:any)=>Promise<any>}): {
  request(path:string,options?:RequestInit,role?:string):Promise<any>;
  preview(documentId:string,token?:string):Promise<string>;
};
export function demoRequest(path:string,options?:RequestInit,role?:string):Promise<any>;
export function demoPreview(documentId:string,token?:string):Promise<string>;

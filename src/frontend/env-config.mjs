// Node-only configuration: never import this module into a client component.
import {readFileSync} from 'node:fs';
import {parseEnv} from 'node:util';
import {resolve} from 'node:path';
import {getDemoConfig} from './demo-access.mjs';
function combinedEnvironment({environment=process.env,envFile=resolve(process.cwd(),'..','..','.env')}={}){
 let values={};
 try{values=parseEnv(readFileSync(envFile,'utf8'));}
 catch(error){if(error.code!=='ENOENT')throw Error('Cannot read the root .env configuration. Check file access.');}
 return {...values,...environment};
}
export function getServerDemoConfig(options){return getDemoConfig(combinedEnvironment(options));}
export function getPublicEnvironment(options){
 const environment=combinedEnvironment(options),demo=getDemoConfig(environment);
 // Force the same-origin boundary even if a shared local .env specifies an external API.
 if(demo.enabled)return {NEXT_PUBLIC_API_URL:'/api/backend'};
 const apiUrl=environment.NEXT_PUBLIC_API_URL||'http://127.0.0.1:8000';
 if(apiUrl==='/api/backend')return {NEXT_PUBLIC_API_URL:apiUrl};
 let parsed;try{parsed=new URL(apiUrl);}catch{throw Error('NEXT_PUBLIC_API_URL must be a public HTTP(S) address without credentials.');}
 if(!['http:','https:'].includes(parsed.protocol)||parsed.username||parsed.password)throw Error('NEXT_PUBLIC_API_URL must be a public HTTP(S) address without credentials.');
 // Explicit allowlist: no other public fields or server secrets are embedded.
 return {NEXT_PUBLIC_API_URL:apiUrl.replace(/\/+$/,'')};
}

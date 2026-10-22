// Node-only configuration: never import this module into a client component.
import {readFileSync} from 'node:fs';
import {parseEnv} from 'node:util';

export function getPublicEnvironment({environment=process.env,envFile=new URL('../../.env',import.meta.url)}={}){
  let values={};
  try{values=parseEnv(readFileSync(envFile,'utf8'));}
  catch(error){if(error.code!=='ENOENT')throw Error('Cannot read the root .env configuration. Check file access.');}
  const apiUrl=environment.NEXT_PUBLIC_API_URL||values.NEXT_PUBLIC_API_URL||'http://127.0.0.1:8000';
  let parsed;
  try{parsed=new URL(apiUrl);}catch{throw Error('NEXT_PUBLIC_API_URL must be a public HTTP(S) address without credentials.');}
  if(!['http:','https:'].includes(parsed.protocol)||parsed.username||parsed.password){
    throw Error('NEXT_PUBLIC_API_URL must be a public HTTP(S) address without credentials.');
  }
  // Explicit allowlist: Supabase/database secrets and other NEXT_PUBLIC_* fields
  // from the shared file are never added to Next.js's browser configuration.
  return {NEXT_PUBLIC_API_URL:apiUrl.replace(/\/+$/,'')};
}

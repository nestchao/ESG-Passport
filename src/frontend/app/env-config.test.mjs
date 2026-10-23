import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const moduleUrl=new URL('../env-config.mjs',import.meta.url).href;
const makeFile=content=>{
  const folder=fs.mkdtempSync(path.join(fileURLToPath(new URL('.',import.meta.url)),'.env-test-'));
  const file=path.join(folder,'.env');
  fs.writeFileSync(file,content);
  return file;
};

test('frontend exports only the API address from the shared root file',async(t)=>{
  const {getPublicEnvironment}=await import(moduleUrl);
  const file=makeFile('NEXT_PUBLIC_API_URL="http://127.0.0.1:8123"\nSUPABASE_SERVER_KEY=fake-server-secret\nDATABASE_URL=fake-database-secret\nNEXT_PUBLIC_UNEXPECTED=must-not-be-exposed\n');
  t.after(()=>{fs.unlinkSync(file);fs.rmdirSync(path.dirname(file));});
  assert.deepEqual(getPublicEnvironment({environment:{},envFile:file}),{NEXT_PUBLIC_API_URL:'http://127.0.0.1:8123'});
});
test('frontend process settings take precedence and absence uses the local default',async(t)=>{
  const {getPublicEnvironment}=await import(moduleUrl);
  const file=makeFile('NEXT_PUBLIC_API_URL=http://127.0.0.1:8123\n');
  t.after(()=>{fs.unlinkSync(file);fs.rmdirSync(path.dirname(file));});
  assert.deepEqual(getPublicEnvironment({environment:{NEXT_PUBLIC_API_URL:'http://localhost:8222'},envFile:file}),{NEXT_PUBLIC_API_URL:'http://localhost:8222'});
  assert.deepEqual(getPublicEnvironment({environment:{},envFile:file+'-absent'}),{NEXT_PUBLIC_API_URL:'http://127.0.0.1:8000'});
});
test('an API address containing credentials is never embedded in the browser',async(t)=>{
  const {getPublicEnvironment}=await import(moduleUrl);
  assert.throws(()=>getPublicEnvironment({environment:{NEXT_PUBLIC_API_URL:'https://fake-user:fake-secret@example.com'},envFile:'absent'}),/public HTTP/);
});

import {NextResponse,type NextRequest} from 'next/server';
import {accessGate} from './demo-access.mjs';
import {getServerDemoConfig} from './env-config.mjs';
export function proxy(request:NextRequest){
 const config=getServerDemoConfig(),blocked=accessGate(request,config);
 if(blocked)return blocked;
 const response=NextResponse.next();
 if(config.enabled){response.headers.set('Cache-Control','no-store, max-age=0');response.headers.set('Referrer-Policy','no-referrer');}
 return response;
}
export const config={matcher:['/((?!_next/static|_next/image|favicon.ico).*)']};

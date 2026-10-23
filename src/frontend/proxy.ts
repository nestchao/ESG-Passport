import {NextResponse,type NextRequest} from 'next/server';
import {accessGate,loginCsrfFromRequest,verifyLoginCsrf,createLoginCsrf,loginCsrfCookie} from './demo-access.mjs';
import {getServerDemoConfig} from './env-config.mjs';
export function proxy(request:NextRequest){
 const config=getServerDemoConfig(),blocked=accessGate(request,config);
 if(blocked)return blocked;
 if(config.enabled&&request.nextUrl.pathname==='/login'&&request.method==='GET'
    &&!verifyLoginCsrf(loginCsrfFromRequest(request),config)){
  const target=new URL(request.nextUrl.pathname+request.nextUrl.search,config.publicOrigin||request.url);
  const response=NextResponse.redirect(target);
  response.headers.append('Set-Cookie',loginCsrfCookie(createLoginCsrf(config),target.protocol==='https:'));
  response.headers.set('Cache-Control','no-store, max-age=0');
  return response;
 }
 const response=NextResponse.next();
 if(config.enabled){response.headers.set('Cache-Control','no-store, max-age=0');response.headers.set('Referrer-Policy','no-referrer');}
 return response;
}
export const config={matcher:['/((?!_next/static|_next/image|favicon.ico).*)']};

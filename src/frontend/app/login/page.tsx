import {safeReturnTo,LOGIN_CSRF_COOKIE} from '../../demo-access.mjs';
import {cookies} from 'next/headers';
import {redirect} from 'next/navigation';
import {getServerDemoConfig} from '../../env-config.mjs';
export const dynamic='force-dynamic';
export default async function DemoLogin({searchParams}:{searchParams:Promise<{error?:string;next?:string}>}){
 if(!getServerDemoConfig().enabled)redirect('/');
 const {error,next}=await searchParams;
 const loginToken=(await cookies()).get(LOGIN_CSRF_COOKIE)?.value||'';
 return <main className="demo-login"><section className="demo-login-card" aria-labelledby="login-title">
  <span className="demo-login-brand">Orbyte <span>ESG Passport</span></span>
  <p className="demo-login-eyebrow">PRIVATE DEMO</p>
  <h1 id="login-title">Welcome to your ESG workspace</h1>
  <p>Enter the demo password to explore the workspace and customer packs.</p>
  <form action="/api/demo/login" method="post">
   <input type="hidden" name="next" value={safeReturnTo(next)}/>
   <input type="hidden" name="csrf_token" value={loginToken}/>
   <label htmlFor="demo-password">Demo password</label>
   <input id="demo-password" name="password" type="password" autoComplete="current-password" required maxLength={1024} aria-describedby={error?'login-error':undefined}/>
   {error&&<p id="login-error" role="alert">Unable to sign in. Check the password and try again.</p>}
   <button type="submit">Enter workspace <span aria-hidden="true">→</span></button>
  </form>
  <p className="demo-public-option">Want to explore without a password? <a href="/demo">Open the public synthetic demo →</a></p>
  <small>Your session lasts eight hours. Sign out when you finish on a shared device.</small>
 </section></main>;
}

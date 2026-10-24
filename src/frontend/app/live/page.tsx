import {cookies} from 'next/headers';
import {redirect} from 'next/navigation';
import {getServerDemoConfig} from '../../env-config.mjs';
import {SESSION_COOKIE, verifySession} from '../../demo-access.mjs';
import ESGPassport from '../page';

// A protected entry into the REAL Supabase-backed backend. Unlike the
// password-free root demo, staff requests use /api/backend without /sandbox.
// The server component independently verifies the signed session.
export const dynamic='force-dynamic';
export default async function LiveWorkspace(){
 const config=getServerDemoConfig();
 const token=(await cookies()).get(SESSION_COOKIE)?.value||'';
 if(!config.enabled||(!config.publicLive&&!verifySession(token,config)))redirect('/login?next=%2Flive');
 return <ESGPassport/>;
}

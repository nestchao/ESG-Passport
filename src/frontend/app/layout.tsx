import type { Metadata } from 'next';
import './globals.css';
import './demo-access.css';
import {getServerDemoConfig} from '../env-config.mjs';
import {SESSION_COOKIE,verifySession} from '../demo-access.mjs';
import {cookies} from 'next/headers';
import './figma-desktop.css';
import './policy-cards.css';
export const dynamic='force-dynamic';
export const metadata: Metadata = { title: 'ESG Passport · Orbyte', description: 'Get ready before your customer asks. Prepare records, review ESG answers and create owner-approved customer packs.' };
export default async function RootLayout({ children }: Readonly<{children: React.ReactNode}>) {
 const config=getServerDemoConfig();
 const staffSession=config.enabled&&!config.publicLive&&verifySession((await cookies()).get(SESSION_COOKIE)?.value,config);
 return <html lang="en"><body>{children}{config.enabled&&config.publicLive&&<aside className="public-workspace-notice" role="note">Public live demo · Data is shared · Upload fictional documents only</aside>}{config.enabled&&config.publicWorkspaceEnabled&&!config.publicLive&&!staffSession&&<aside className="public-workspace-notice" role="note">Public synthetic workspace · Shared fictional test data · Do not upload private documents</aside>}{staffSession&&<form className="demo-logout" action="/api/demo/logout" method="post"><button type="submit">Sign out</button></form>}</body></html>;
}

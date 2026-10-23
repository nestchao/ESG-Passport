import type { Metadata } from 'next';
import './globals.css';
import './demo-access.css';
import {getServerDemoConfig} from '../env-config.mjs';
import './figma-desktop.css';
import './policy-cards.css';
export const dynamic='force-dynamic';
export const metadata: Metadata = { title: 'ESG Passport · Orbyte', description: 'Get ready before your customer asks. Prepare records, review ESG answers and create owner-approved customer packs.' };
export default function RootLayout({ children }: Readonly<{children: React.ReactNode}>) { return <html lang="en"><body>{children}{getServerDemoConfig().enabled&&<form className="demo-logout" action="/api/demo/logout" method="post"><button type="submit">Sign out of demo</button></form>}</body></html>; }

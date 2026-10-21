import type { Metadata } from 'next';
import './globals.css';
import './figma-desktop.css';
export const metadata: Metadata = { title: 'ESG Passport · Orbyte', description: 'Get ready before your customer asks. A synthetic-data ESG demonstration.' };
export default function RootLayout({ children }: Readonly<{children: React.ReactNode}>) { return <html lang="en"><body>{children}</body></html>; }

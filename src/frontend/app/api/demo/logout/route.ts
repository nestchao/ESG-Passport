import {handleLogout} from '../../../../demo-access.mjs';
import {getServerDemoConfig} from '../../../../env-config.mjs';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export function POST(request:Request){return handleLogout(request,getServerDemoConfig());}

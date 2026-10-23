import {handleLogin} from '../../../../demo-access.mjs';
import {getServerDemoConfig} from '../../../../env-config.mjs';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export async function POST(request:Request){return handleLogin(request,getServerDemoConfig());}

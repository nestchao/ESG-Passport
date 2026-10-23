import {proxyBackend} from '../../../../demo-access.mjs';
import {getServerDemoConfig} from '../../../../env-config.mjs';
export const runtime='nodejs';
export const dynamic='force-dynamic';
async function handle(request:Request,context:{params:Promise<{path:string[]}>}){
 return proxyBackend(request,(await context.params).path,getServerDemoConfig());
}
export {handle as GET,handle as POST,handle as PUT};

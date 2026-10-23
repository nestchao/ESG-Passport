import type {DemoConfig} from './demo-access.mjs';
type Options={environment?:Record<string,string|undefined>;envFile?:string|URL};
export function getPublicEnvironment(options?:Options):{NEXT_PUBLIC_API_URL:string};
export function getServerDemoConfig(options?:Options):DemoConfig;

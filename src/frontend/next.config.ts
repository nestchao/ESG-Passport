import type { NextConfig } from 'next';
import { getPublicEnvironment } from './env-config.mjs';
const config: NextConfig = { poweredByHeader: false, experimental: {proxyClientMaxBodySize: '12mb'}, env: getPublicEnvironment() };
export default config;

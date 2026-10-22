import type { NextConfig } from 'next';
import { getPublicEnvironment } from './env-config.mjs';
const config: NextConfig = { poweredByHeader: false, env: getPublicEnvironment() };
export default config;

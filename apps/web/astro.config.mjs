import node from '@astrojs/node';
import { defineConfig } from 'astro/config';

// Server-rendered from the pipeline's public API, so a publication shows up
// without a rebuild. No login, no AI at view time; responses are cacheable.
export default defineConfig({
  output: 'server',
  adapter: node({ mode: 'standalone' }),
  server: { port: 4322, host: true },
  trailingSlash: 'ignore',
});

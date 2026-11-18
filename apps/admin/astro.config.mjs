import node from '@astrojs/node';
import { defineConfig } from 'astro/config';

// Server-rendered: every page needs the logged-in user. Astro's origin check
// (security.checkOrigin, on by default) rejects cross-site form posts.
export default defineConfig({
  output: 'server',
  adapter: node({ mode: 'standalone' }),
  server: { port: 4321, host: true },
  security: { checkOrigin: true },
});

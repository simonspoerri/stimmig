import type { APIRoute } from 'astro';

export const GET: APIRoute = () =>
  Response.json({ status: 'ok', version: process.env.APP_VERSION ?? 'dev' });

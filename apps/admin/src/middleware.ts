import { defineMiddleware } from 'astro:middleware';
import { pipelineClient } from './lib/api.ts';
import { refresh } from './lib/oidc.ts';
import { clearSession, readSession, writeSession } from './lib/session.ts';

const PUBLIC_PATHS = ['/auth/login', '/auth/callback', '/auth/logout', '/healthz'];

/** Every page needs a session; access tokens are refreshed a minute before they expire. */
export const onRequest = defineMiddleware(async (context, next) => {
  const { pathname } = context.url;
  if (PUBLIC_PATHS.includes(pathname)) {
    context.locals.session = undefined;
    context.locals.pipeline = pipelineClient(undefined);
    return next();
  }

  let session = await readSession(context.cookies);
  if (session && session.accessTokenExpiresAt - 60 < Date.now() / 1000) {
    try {
      const tokens = await refresh(session.refreshToken, 'urn:stimmig:api');
      session = {
        ...session,
        accessToken: tokens.access_token,
        accessTokenExpiresAt: Math.floor(Date.now() / 1000) + (tokens.expires_in ?? 600),
        refreshToken: tokens.refresh_token ?? session.refreshToken,
      };
      await writeSession(context.cookies, session);
    } catch {
      clearSession(context.cookies);
      session = undefined;
    }
  }

  if (!session) {
    const returnTo = context.request.method === 'GET' ? pathname + context.url.search : '/';
    return context.redirect(`/auth/login?returnTo=${encodeURIComponent(returnTo)}`);
  }

  context.locals.session = session;
  context.locals.pipeline = pipelineClient(session);
  const response = await next();
  response.headers.set('Cache-Control', 'no-store');
  response.headers.set('X-Frame-Options', 'DENY');
  response.headers.set('Referrer-Policy', 'same-origin');
  return response;
});

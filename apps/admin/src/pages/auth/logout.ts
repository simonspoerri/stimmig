import type { APIRoute } from 'astro';
import { logoutUrl } from '../../lib/oidc.ts';
import { clearSession, readSession } from '../../lib/session.ts';

/** Ends the local session, then the session at the identity service. */
export const POST: APIRoute = async ({ cookies, redirect }) => {
  const session = await readSession(cookies);
  clearSession(cookies);
  if (!session) return redirect('/');
  return redirect((await logoutUrl(session.idToken)).href);
};

import type { APIRoute } from 'astro';
import { client, authorizationUrl } from '../../lib/oidc.ts';
import { writeLoginState } from '../../lib/session.ts';

/** Starts the login at the identity service. */
export const GET: APIRoute = async ({ url, cookies, redirect }) => {
  const requested = url.searchParams.get('returnTo') ?? '/';
  // Only same-site paths, never an absolute URL (open redirect).
  const returnTo = requested.startsWith('/') && !requested.startsWith('//') ? requested : '/';
  const state = client.randomState();
  const verifier = client.randomPKCECodeVerifier();
  await writeLoginState(cookies, { state, verifier, returnTo });
  return redirect((await authorizationUrl(state, verifier)).href);
};

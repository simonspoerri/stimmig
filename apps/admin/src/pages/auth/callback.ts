import type { APIRoute } from 'astro';
import { decodeJwt } from 'jose';
import { pipelineClient } from '../../lib/api.ts';
import { exchangeCode } from '../../lib/oidc.ts';
import { type Session, takeLoginState, writeSession } from '../../lib/session.ts';

interface Me {
  roles: string[];
  permissions: string[];
}

/** Back from the identity service: swap the code for tokens and open the session. */
export const GET: APIRoute = async ({ url, cookies, redirect }) => {
  const login = await takeLoginState(cookies);
  if (!login) return redirect('/auth/login');

  const tokens = await exchangeCode(url, login.state, login.verifier);
  const claims = tokens.claims();
  if (!claims || !tokens.refresh_token || !tokens.id_token) throw new Error('incomplete token response');
  const access = decodeJwt(tokens.access_token);

  const partial = {
    sub: claims.sub,
    email: String(claims.email ?? ''),
    name: String(claims.name ?? claims.email ?? ''),
    accessToken: tokens.access_token,
    accessTokenExpiresAt: Number(access.exp),
    refreshToken: tokens.refresh_token,
    idToken: tokens.id_token,
  };
  // The pipeline is the authority on what the roles allow; ask it once per login.
  const me = await pipelineClient({ ...partial, roles: [], permissions: [] }).get<Me>('/api/me');
  const session: Session = { ...partial, roles: me.roles, permissions: me.permissions };
  await writeSession(cookies, session);
  return redirect(login.returnTo);
};

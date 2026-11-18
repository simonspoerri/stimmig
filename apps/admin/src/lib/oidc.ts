import * as client from 'openid-client';
import { config } from './config.ts';

/** OIDC client for the identity service: authorization code flow with PKCE. */

let discovered: Promise<client.Configuration> | undefined;

export function oidc(): Promise<client.Configuration> {
  discovered ??= client
    .discovery(new URL(config.issuer), config.clientId, config.clientSecret, undefined, {
      // Local development runs the identity service over plain http.
      execute: new URL(config.issuer).protocol === 'http:' ? [client.allowInsecureRequests] : [],
    })
    .catch((error: unknown) => {
      discovered = undefined;
      throw error;
    });
  return discovered;
}

export const redirectUri = () => new URL('/auth/callback', config.publicUrl).href;

export async function authorizationUrl(state: string, verifier: string): Promise<URL> {
  const params = new URLSearchParams({
    redirect_uri: redirectUri(),
    scope: 'openid email profile roles offline_access',
    code_challenge: await client.calculatePKCECodeChallenge(verifier),
    code_challenge_method: 'S256',
    state,
  });
  // Ask for both resources up front, so the refresh token can later be swapped
  // for an identity-resource token when an admin opens user management.
  params.append('resource', config.resources.api);
  params.append('resource', config.resources.identity);
  return client.buildAuthorizationUrl(await oidc(), params);
}

export async function exchangeCode(callbackUrl: URL, state: string, verifier: string) {
  return client.authorizationCodeGrant(await oidc(), callbackUrl, {
    pkceCodeVerifier: verifier,
    expectedState: state,
  }, { resource: config.resources.api });
}

export async function refresh(refreshToken: string, resource: string) {
  return client.refreshTokenGrant(await oidc(), refreshToken, { resource });
}

export async function logoutUrl(idToken: string): Promise<URL> {
  return client.buildEndSessionUrl(await oidc(), {
    id_token_hint: idToken,
    post_logout_redirect_uri: new URL('/', config.publicUrl).href,
  });
}

export { client };

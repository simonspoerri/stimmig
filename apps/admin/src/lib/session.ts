import type { AstroCookies } from 'astro';
import { base64url, EncryptJWT, jwtDecrypt } from 'jose';
import { config } from './config.ts';

/**
 * The session lives in an encrypted, httpOnly cookie (A256GCM). The browser
 * can't read the tokens inside; the server needs no session store.
 */
export interface Session {
  sub: string;
  email: string;
  name: string;
  roles: string[];
  permissions: string[];
  accessToken: string;
  /** Unix seconds. */
  accessTokenExpiresAt: number;
  refreshToken: string;
  idToken: string;
}

/** Short-lived state of one login attempt (PKCE verifier, state, where to go back to). */
export interface LoginState {
  state: string;
  verifier: string;
  returnTo: string;
}

const SESSION_COOKIE = 'stimmig_session';
const LOGIN_COOKIE = 'stimmig_login';
const SESSION_MAX_AGE = 8 * 60 * 60;

let key: Uint8Array | undefined;
function secret(): Uint8Array {
  key ??= base64url.decode(config.sessionSecret);
  if (key.length < 32) throw new Error('SESSION_SECRET must be at least 32 bytes');
  return key.slice(0, 32);
}

async function seal(payload: object, maxAge: number): Promise<string> {
  return new EncryptJWT({ ...payload })
    .setProtectedHeader({ alg: 'dir', enc: 'A256GCM' })
    .setIssuedAt()
    .setExpirationTime(`${maxAge}s`)
    .encrypt(secret());
}

async function unseal<T>(value: string | undefined): Promise<T | undefined> {
  if (!value) return undefined;
  try {
    const { payload } = await jwtDecrypt(value, secret());
    return payload as T;
  } catch {
    return undefined;
  }
}

const cookieOptions = (maxAge: number) =>
  ({ httpOnly: true, secure: config.secureCookies, sameSite: 'lax', path: '/', maxAge }) as const;

export async function readSession(cookies: AstroCookies): Promise<Session | undefined> {
  return unseal<Session>(cookies.get(SESSION_COOKIE)?.value);
}

export async function writeSession(cookies: AstroCookies, session: Session): Promise<void> {
  cookies.set(SESSION_COOKIE, await seal(session, SESSION_MAX_AGE), cookieOptions(SESSION_MAX_AGE));
}

export function clearSession(cookies: AstroCookies): void {
  cookies.delete(SESSION_COOKIE, { path: '/' });
}

export async function writeLoginState(cookies: AstroCookies, state: LoginState): Promise<void> {
  cookies.set(LOGIN_COOKIE, await seal(state, 600), cookieOptions(600));
}

export async function takeLoginState(cookies: AstroCookies): Promise<LoginState | undefined> {
  const state = await unseal<LoginState>(cookies.get(LOGIN_COOKIE)?.value);
  cookies.delete(LOGIN_COOKIE, { path: '/' });
  return state;
}

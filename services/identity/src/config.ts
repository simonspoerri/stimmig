import { generateKeyPairSync, randomBytes } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import type { ClientMetadata, JWK } from 'oidc-provider';

/**
 * Resource servers that can receive access tokens. A token is always for
 * exactly one of them (its `aud`), so a token for the pipeline API can't be
 * used against user management and vice versa.
 */
export const RESOURCES = {
  api: { indicator: 'urn:stimmig:api', scope: 'api' },
  identity: { indicator: 'urn:stimmig:identity', scope: 'identity:manage' },
} as const;

export const ROLES = ['admin', 'reviewer', 'visualizer'] as const;
export type Role = (typeof ROLES)[number];

export interface Config {
  issuer: string;
  port: number;
  databaseUrl: string;
  production: boolean;
  trustProxy: boolean;
  clients: ClientMetadata[];
  jwks: { keys: JWK[] };
  cookieKeys: string[];
  /** Key for the HMAC of login codes. */
  codeKey: string;
  smtpUrl: string | undefined;
  mailFrom: string;
}

const LOCAL_DIR = join(process.cwd(), '.local');

/** Dev-only: generate a secret once and keep it in .local/ so restarts keep sessions and keys. */
function localSecret<T>(name: string, create: () => T): T {
  const path = join(LOCAL_DIR, name);
  if (existsSync(path)) return JSON.parse(readFileSync(path, 'utf8')) as T;
  const value = create();
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(value), { mode: 0o600 });
  return value;
}

function generateJwks(): { keys: JWK[] } {
  const { privateKey } = generateKeyPairSync('ec', { namedCurve: 'P-256' });
  const jwk = privateKey.export({ format: 'jwk' }) as JWK;
  return { keys: [{ ...jwk, alg: 'ES256', use: 'sig', kid: randomBytes(8).toString('hex') }] };
}

function devClients(): ClientMetadata[] {
  const admin = process.env.ADMIN_URL ?? 'http://localhost:4321';
  return [
    {
      client_id: 'admin',
      client_secret: 'dev-admin-secret',
      client_name: 'Stimmig Admin',
      redirect_uris: [`${admin}/auth/callback`],
      post_logout_redirect_uris: [`${admin}/`],
      grant_types: ['authorization_code', 'refresh_token'],
      response_types: ['code'],
      token_endpoint_auth_method: 'client_secret_basic',
    },
  ];
}

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} must be set in production`);
  return value;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  const production = env.NODE_ENV === 'production';
  const port = Number(env.PORT ?? 4000);
  const json = <T>(name: string): T => JSON.parse(required(name)) as T;

  const config: Config = {
    issuer: env.ISSUER ?? `http://localhost:${port}`,
    port,
    databaseUrl: env.DATABASE_URL ?? 'postgresql://postgres@localhost:5432/stimmig_identity',
    production,
    trustProxy: env.TRUST_PROXY === 'true',
    clients: production ? json<ClientMetadata[]>('IDENTITY_CLIENTS') : (env.IDENTITY_CLIENTS ? JSON.parse(env.IDENTITY_CLIENTS) : devClients()),
    jwks: production ? json<{ keys: JWK[] }>('IDENTITY_JWKS') : localSecret('jwks.json', generateJwks),
    cookieKeys: production
      ? required('COOKIE_KEYS').split(',')
      : localSecret('cookie-keys.json', () => [randomBytes(32).toString('base64url')]),
    codeKey: production ? required('CODE_KEY') : localSecret('code-key.json', () => randomBytes(32).toString('base64url')),
    smtpUrl: env.SMTP_URL,
    mailFrom: env.MAIL_FROM ?? 'Stimmig <no-reply@stimmig.local>',
  };
  if (production && !config.smtpUrl) throw new Error('SMTP_URL must be set in production: login codes are sent by email');
  return config;
}

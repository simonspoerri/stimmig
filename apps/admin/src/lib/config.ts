/** Server-side configuration, read from the environment at runtime. */

function env(name: string, fallback?: string): string {
  const value = process.env[name] ?? fallback;
  if (value === undefined) throw new Error(`${name} must be set`);
  return value;
}

const production = process.env.NODE_ENV === 'production';
const dev = <T extends string>(value: T): T | undefined => (production ? undefined : value);

export const config = {
  /** Public URL of this app; the OIDC redirect URIs are derived from it. */
  publicUrl: env('PUBLIC_URL', dev('http://localhost:4321')),
  issuer: env('OIDC_ISSUER', dev('http://localhost:4000')),
  clientId: env('OIDC_CLIENT_ID', 'admin'),
  clientSecret: env('OIDC_CLIENT_SECRET', dev('dev-admin-secret')),
  pipelineUrl: env('PIPELINE_URL', dev('http://localhost:8000')),
  publicSiteUrl: env('PUBLIC_SITE_URL', dev('http://localhost:4322')),
  /** 32+ random bytes, base64url. Encrypts the session cookie. */
  sessionSecret: env('SESSION_SECRET', dev('ZGV2LW9ubHktc2Vzc2lvbi1zZWNyZXQtMzItYnl0ZXMh')),
  secureCookies: production,
  resources: { api: 'urn:stimmig:api', identity: 'urn:stimmig:identity' },
} as const;

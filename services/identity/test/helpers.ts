import { createHash, randomBytes } from 'node:crypto';
import type { AddressInfo } from 'node:net';
import type { Server } from 'node:http';
import { createProvider } from '../src/app.ts';
import { loadConfig } from '../src/config.ts';
import { createPool, migrate, type Db } from '../src/db.ts';
import type { Mailer } from '../src/mailer.ts';

export const CLIENT = { id: 'admin', secret: 'test-secret', redirect: 'http://admin.test/auth/callback' };

/** Captures login codes instead of sending them. */
export class TestMailer implements Mailer {
  sent: { to: string; code: string }[] = [];
  async sendLoginCode(to: string, code: string) {
    this.sent.push({ to, code });
  }
  last(): string {
    const mail = this.sent.at(-1);
    if (!mail) throw new Error('no mail sent');
    return mail.code;
  }
}

export interface TestServer {
  url: string;
  db: Db;
  mailer: TestMailer;
  close(): Promise<void>;
}

export async function startServer(): Promise<TestServer> {
  process.env.LOG_SILENT = process.env.LOG_SILENT ?? 'true';
  const db = createPool(process.env.TEST_DATABASE_URL ?? 'postgresql://postgres@localhost:5432/stimmig_identity_test');
  await migrate(db);
  await db.query('TRUNCATE users, oidc_payloads, login_codes');

  const mailer = new TestMailer();
  // Port is unknown until listening; the issuer must match, so listen first, then build the provider.
  const { createServer } = await import('node:http');
  const app: { handler?: (req: unknown, res: unknown) => void } = {};
  const server: Server = createServer((req, res) => app.handler?.(req, res));
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  const url = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;

  const config = loadConfig({
    ISSUER: url,
    IDENTITY_CLIENTS: JSON.stringify([
      {
        client_id: CLIENT.id,
        client_secret: CLIENT.secret,
        redirect_uris: [CLIENT.redirect],
        post_logout_redirect_uris: ['http://admin.test/'],
        grant_types: ['authorization_code', 'refresh_token'],
        response_types: ['code'],
      },
    ]),
  });
  app.handler = createProvider(config, { db, mailer }).callback() as typeof app.handler;

  return {
    url,
    db,
    mailer,
    close: async () => {
      await new Promise((resolve) => server.close(resolve));
      await db.end();
    },
  };
}

/** A browser stand-in: keeps cookies per host, never follows redirects on its own. */
export class Browser {
  private cookies = new Map<string, string>();

  async request(url: string, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers(init.headers);
    if (this.cookies.size > 0) headers.set('cookie', [...this.cookies].map(([k, v]) => `${k}=${v}`).join('; '));
    const response = await fetch(url, { ...init, headers, redirect: 'manual' });
    for (const cookie of response.headers.getSetCookie()) {
      const [pair] = cookie.split(';');
      const [name, ...value] = pair!.split('=');
      if (/expires=Thu, 01 Jan 1970/i.test(cookie)) this.cookies.delete(name!);
      else this.cookies.set(name!, value.join('='));
    }
    return response;
  }

  /** Follows redirects on the identity server; stops at the first redirect to another origin. */
  async follow(url: string, init: RequestInit = {}): Promise<Response> {
    let response = await this.request(url, init);
    let current = url;
    while (response.status >= 300 && response.status < 400) {
      const next = new URL(response.headers.get('location')!, current);
      if (next.origin !== new URL(url).origin) return response;
      current = next.href;
      response = await this.request(current);
    }
    return response;
  }

  form(url: string, fields: Record<string, string>): Promise<Response> {
    return this.follow(url, {
      method: 'POST',
      headers: { 'content-type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams(fields).toString(),
    });
  }
}

export function pkce() {
  const verifier = randomBytes(32).toString('base64url');
  return { verifier, challenge: createHash('sha256').update(verifier).digest('base64url') };
}

export function formAction(html: string): string {
  const match = /<form method="post" action="([^"]+)"/.exec(html);
  if (!match) throw new Error(`no form in page:\n${html}`);
  return match[1]!;
}

export function decodeJwt(token: string): Record<string, unknown> {
  return JSON.parse(Buffer.from(token.split('.')[1]!, 'base64url').toString()) as Record<string, unknown>;
}

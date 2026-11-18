import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';
import { RESOURCES } from '../src/config.ts';
import { Users } from '../src/users.ts';
import { Browser, CLIENT, decodeJwt, formAction, pkce, startServer, type TestServer } from './helpers.ts';

let server: TestServer;
let users: Users;

beforeAll(async () => {
  server = await startServer();
  users = new Users(server.db);
  await users.create({ email: 'Admin@Stimmig.test', name: 'Ada Admin', roles: ['admin', 'reviewer'] });
  await users.create({ email: 'visualizer@stimmig.test', name: 'Vera Visualizer', roles: ['visualizer'] });
});

afterAll(async () => {
  await server.close();
});

beforeEach(() => {
  server.mailer.sent = [];
});

/** Runs the authorization code flow up to the login form; returns the form page. */
async function startLogin(browser: Browser, challenge: string): Promise<string> {
  const params = new URLSearchParams({
    client_id: CLIENT.id,
    response_type: 'code',
    redirect_uri: CLIENT.redirect,
    scope: 'openid email profile roles offline_access',
    code_challenge: challenge,
    code_challenge_method: 'S256',
    state: 'state-123',
  });
  params.append('resource', RESOURCES.api.indicator);
  params.append('resource', RESOURCES.identity.indicator);
  const page = await browser.follow(`${server.url}/auth?${params}`);
  expect(page.status).toBe(200);
  return page.text();
}

async function login(email: string): Promise<{ browser: Browser; code: string; verifier: string }> {
  const browser = new Browser();
  const { verifier, challenge } = pkce();
  const emailPage = await startLogin(browser, challenge);
  const codePage = await (await browser.form(`${server.url}${formAction(emailPage)}`, { email })).text();
  const done = await browser.form(`${server.url}${formAction(codePage)}`, { code: server.mailer.last() });
  expect(done.status).toBe(303);
  const callback = new URL(done.headers.get('location')!);
  expect(callback.origin + callback.pathname).toBe(CLIENT.redirect);
  expect(callback.searchParams.get('state')).toBe('state-123');
  return { browser, code: callback.searchParams.get('code')!, verifier };
}

async function token(params: Record<string, string>): Promise<Response> {
  return fetch(`${server.url}/token`, {
    method: 'POST',
    headers: {
      'content-type': 'application/x-www-form-urlencoded',
      authorization: `Basic ${Buffer.from(`${CLIENT.id}:${CLIENT.secret}`).toString('base64')}`,
    },
    body: new URLSearchParams(params).toString(),
  });
}

async function tokensFor(email: string) {
  const { code, verifier } = await login(email);
  const response = await token({ grant_type: 'authorization_code', code, code_verifier: verifier, redirect_uri: CLIENT.redirect });
  expect(response.status).toBe(200);
  return (await response.json()) as { access_token: string; refresh_token: string; id_token: string };
}

async function identityToken(refreshToken: string): Promise<string> {
  const response = await token({ grant_type: 'refresh_token', refresh_token: refreshToken, resource: RESOURCES.identity.indicator });
  expect(response.status).toBe(200);
  return ((await response.json()) as { access_token: string }).access_token;
}

describe('login and tokens', () => {
  it('publishes discovery with the resource-bound JWT setup', async () => {
    const discovery = (await (await fetch(`${server.url}/.well-known/openid-configuration`)).json()) as Record<string, unknown>;
    expect(discovery.issuer).toBe(server.url);
    expect(discovery.code_challenge_methods_supported).toEqual(['S256']);
    expect(discovery.scopes_supported).toEqual(expect.arrayContaining(['roles', 'offline_access']));
  });

  it('logs in with an emailed code and issues an API token with roles', async () => {
    const tokens = await tokensFor('admin@stimmig.test');
    const access = decodeJwt(tokens.access_token);
    expect(access.aud).toBe(RESOURCES.api.indicator);
    expect(access.iss).toBe(server.url);
    expect(access.roles).toEqual(['admin', 'reviewer']);
    expect(access.email).toBe('admin@stimmig.test');
    expect(Number(access.exp) - Number(access.iat)).toBe(600);
    expect(tokens.refresh_token).toBeTruthy();

    const id = decodeJwt(tokens.id_token);
    expect(id.name).toBe('Ada Admin');
    expect(id.roles).toEqual(['admin', 'reviewer']);

    const user = await users.byEmail('admin@stimmig.test');
    expect(user?.last_login_at).toBeInstanceOf(Date);
  });

  it('rejects wrong codes and locks the code after five attempts', async () => {
    const browser = new Browser();
    const emailPage = await startLogin(browser, pkce().challenge);
    const codePage = await (await browser.form(`${server.url}${formAction(emailPage)}`, { email: 'admin@stimmig.test' })).text();
    const action = `${server.url}${formAction(codePage)}`;
    const right = server.mailer.last();
    const wrong = right === '000000' ? '111111' : '000000';

    const first = await browser.form(action, { code: wrong });
    expect(first.status).toBe(400);
    expect(await first.text()).toContain('Der Code stimmt nicht');
    for (let i = 0; i < 4; i++) await browser.form(action, { code: wrong });
    const locked = await browser.form(action, { code: right });
    expect(locked.status).toBe(400);
    expect(await locked.text()).toContain('Zu viele Versuche');
  });

  it('treats unknown and disabled addresses like known ones but sends nothing', async () => {
    const browser = new Browser();
    const emailPage = await startLogin(browser, pkce().challenge);
    const page = await browser.form(`${server.url}${formAction(emailPage)}`, { email: 'nobody@stimmig.test' });
    expect(await page.text()).toContain('Code eingeben');
    expect(server.mailer.sent).toHaveLength(0);
  });

  it('binds a code to the browser that requested it', async () => {
    const browser = new Browser();
    const emailPage = await startLogin(browser, pkce().challenge);
    const codePage = await (await browser.form(`${server.url}${formAction(emailPage)}`, { email: 'admin@stimmig.test' })).text();
    const other = new Browser();
    await startLogin(other, pkce().challenge);
    const response = await other.form(`${server.url}${formAction(codePage)}`, { code: server.mailer.last() });
    expect(response.status).toBe(400);
  });
});

describe('user management', () => {
  it('accepts only identity-resource tokens of admins', async () => {
    const admin = await tokensFor('admin@stimmig.test');
    const manageToken = await identityToken(admin.refresh_token);
    expect(decodeJwt(manageToken).aud).toBe(RESOURCES.identity.indicator);

    const list = await fetch(`${server.url}/manage/users`, { headers: { authorization: `Bearer ${manageToken}` } });
    expect(list.status).toBe(200);
    expect(((await list.json()) as { email: string }[]).map((u) => u.email)).toContain('visualizer@stimmig.test');

    // A pipeline API token is not valid here.
    const wrongAudience = await fetch(`${server.url}/manage/users`, { headers: { authorization: `Bearer ${admin.access_token}` } });
    expect(wrongAudience.status).toBe(401);

    const visualizer = await tokensFor('visualizer@stimmig.test');
    const forbidden = await fetch(`${server.url}/manage/users`, {
      headers: { authorization: `Bearer ${await identityToken(visualizer.refresh_token)}` },
    });
    expect(forbidden.status).toBe(403);
  });

  it('creates users, changes roles, and keeps admins from locking themselves out', async () => {
    const admin = await tokensFor('admin@stimmig.test');
    const headers = { authorization: `Bearer ${await identityToken(admin.refresh_token)}`, 'content-type': 'application/json' };

    const created = await fetch(`${server.url}/manage/users`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ email: 'Rita@Stimmig.test', name: 'Rita Reviewer', roles: ['reviewer'] }),
    });
    expect(created.status).toBe(201);
    const rita = (await created.json()) as { id: string; email: string };
    expect(rita.email).toBe('rita@stimmig.test');

    const badRole = await fetch(`${server.url}/manage/users`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ email: 'x@stimmig.test', name: 'X', roles: ['superuser'] }),
    });
    expect(badRole.status).toBe(422);

    const updated = await fetch(`${server.url}/manage/users/${rita.id}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ roles: ['reviewer', 'visualizer'] }),
    });
    expect(((await updated.json()) as { roles: string[] }).roles).toEqual(['reviewer', 'visualizer']);

    const self = (await users.byEmail('admin@stimmig.test'))!;
    const lockout = await fetch(`${server.url}/manage/users/${self.id}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ roles: ['reviewer'] }),
    });
    expect(lockout.status).toBe(422);
  });

  it('gives a role change effect in the next access token', async () => {
    const before = await tokensFor('visualizer@stimmig.test');
    expect(decodeJwt(before.access_token).roles).toEqual(['visualizer']);
    const vera = (await users.byEmail('visualizer@stimmig.test'))!;
    await users.update(vera.id, { roles: ['visualizer', 'reviewer'] });
    const refreshed = await token({ grant_type: 'refresh_token', refresh_token: before.refresh_token });
    const access = decodeJwt(((await refreshed.json()) as { access_token: string }).access_token);
    expect(access.roles).toEqual(['reviewer', 'visualizer']);
    expect(access.aud).toBe(RESOURCES.api.indicator);
  });
});

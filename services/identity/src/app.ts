import type { JSONWebKeySet } from 'jose';
import Provider, { errors, type Configuration, type KoaContextWithOIDC } from 'oidc-provider';
import { postgresAdapter } from './adapter.ts';
import { LoginCodes } from './codes.ts';
import { type Config, RESOURCES } from './config.ts';
import type { Db } from './db.ts';
import { interactionRoutes } from './interactions.ts';
import { log } from './log.ts';
import type { Mailer } from './mailer.ts';
import { manageRoutes } from './manage.ts';
import { Users } from './users.ts';
import { errorPage, loggedOutPage, logoutPage } from './views.ts';

const RESOURCE_BY_INDICATOR = new Map(Object.values(RESOURCES).map((r) => [r.indicator, r]));
const VERSION = process.env.APP_VERSION ?? 'dev';

const OIDC_SCOPES = 'openid offline_access email profile roles';

function publicJwks(config: Config): JSONWebKeySet {
  return {
    keys: config.jwks.keys.map(({ kty, crv, x, y, n, e, kid, alg, use }) =>
      Object.fromEntries(Object.entries({ kty, crv, x, y, n, e, kid, alg, use }).filter(([, v]) => v !== undefined)),
    ),
  } as JSONWebKeySet;
}

export function createProvider(config: Config, deps: { db: Db; mailer: Mailer }): Provider {
  const users = new Users(deps.db);
  const codes = new LoginCodes(deps.db, config.codeKey);

  const configuration: Configuration = {
    adapter: postgresAdapter(deps.db),
    clients: config.clients,
    // Only an ES256 key exists, so everything is signed with it.
    clientDefaults: { id_token_signed_response_alg: 'ES256', grant_types: ['authorization_code', 'refresh_token'] },
    jwks: config.jwks,
    cookies: { keys: config.cookieKeys, long: { signed: true }, short: { signed: true } },
    pkce: { required: () => true },
    scopes: OIDC_SCOPES.split(' '),
    claims: {
      openid: ['sub'],
      email: ['email', 'email_verified'],
      profile: ['name'],
      roles: ['roles'],
    },
    conformIdTokenClaims: false,

    async findAccount(_ctx, sub) {
      const user = await users.active(sub);
      if (!user) return undefined;
      return {
        accountId: user.id,
        async claims() {
          return { sub: user.id, email: user.email, email_verified: true, name: user.name, roles: user.roles };
        },
      };
    },

    // Access tokens carry the user's current roles and email; the APIs map roles to permissions.
    async extraTokenClaims(_ctx, token) {
      if (token.kind !== 'AccessToken' || !token.accountId) return undefined;
      const user = await users.active(token.accountId);
      return user ? { roles: user.roles, email: user.email } : { roles: [] };
    },

    // All clients are first-party: grant everything they may ask for, no consent screen.
    async loadExistingGrant(ctx) {
      const { client, session } = ctx.oidc;
      if (!client || !session?.accountId) return undefined;
      const grantId = ctx.oidc.result?.consent?.grantId ?? session.grantIdFor(client.clientId);
      const grant = grantId
        ? await ctx.oidc.provider.Grant.find(grantId)
        : new ctx.oidc.provider.Grant({ clientId: client.clientId, accountId: session.accountId });
      if (!grant) return undefined;
      grant.addOIDCScope(OIDC_SCOPES);
      grant.addOIDCClaims(['email', 'email_verified', 'name', 'roles']);
      for (const resource of Object.values(RESOURCES)) grant.addResourceScope(resource.indicator, resource.scope);
      await grant.save();
      return grant;
    },

    issueRefreshToken: async (_ctx, client) => client.grantTypeAllowed('refresh_token'),

    features: {
      devInteractions: { enabled: false },
      revocation: { enabled: true },
      rpInitiatedLogout: {
        enabled: true,
        async logoutSource(ctx, form) {
          ctx.type = 'html';
          ctx.body = logoutPage(form);
        },
        async postLogoutSuccessSource(ctx) {
          ctx.type = 'html';
          ctx.body = loggedOutPage();
        },
      },
      resourceIndicators: {
        enabled: true,
        // Without a resource parameter, tokens are for the pipeline API.
        defaultResource: async () => RESOURCES.api.indicator,
        // A refresh token may be exchanged for a token of any resource in its grant.
        useGrantedResource: async () => true,
        async getResourceServerInfo(_ctx, indicator) {
          const resource = RESOURCE_BY_INDICATOR.get(indicator as (typeof RESOURCES)[keyof typeof RESOURCES]['indicator']);
          if (!resource) throw new errors.InvalidTarget();
          return {
            scope: resource.scope,
            audience: resource.indicator,
            accessTokenTTL: 10 * 60,
            accessTokenFormat: 'jwt',
            jwt: { sign: { alg: 'ES256' } },
          };
        },
      },
    },

    ttl: {
      AccessToken: 10 * 60,
      AuthorizationCode: 60,
      IdToken: 60 * 60,
      Interaction: 15 * 60,
      Session: 8 * 60 * 60,
      Grant: 14 * 24 * 60 * 60,
      RefreshToken: (ctx, token) => (token.isSenderConstrained() ? 14 : 8) * 24 * 60 * 60,
    },

    async renderError(ctx: KoaContextWithOIDC, out) {
      log.warn('oidc error', { error: out.error, description: out.error_description });
      ctx.type = 'html';
      ctx.body = errorPage('Die Anmeldung konnte nicht abgeschlossen werden. Bitte versuchen Sie es erneut.');
    },
  };

  const provider = new Provider(config.issuer, configuration);
  provider.proxy = config.trustProxy;

  provider.use(async (ctx, next) => {
    if (ctx.path === '/healthz') {
      ctx.body = { status: 'ok', version: VERSION };
      return;
    }
    await next();
  });
  const clientOrigins = [
    ...new Set(config.clients.flatMap((c) => (c.redirect_uris ?? []).map((uri) => new URL(uri).origin))),
  ];
  const interactions = interactionRoutes(provider, { users, codes, mailer: deps.mailer, clientOrigins });
  const manage = manageRoutes({ users, issuer: config.issuer, publicJwks: publicJwks(config) });
  provider.use(interactions.routes()).use(interactions.allowedMethods());
  provider.use(manage.routes()).use(manage.allowedMethods());

  provider.on('server_error', (_ctx, error) => log.error('server error', { error: String(error) }));
  return provider;
}

import Router from '@koa/router';
import { createLocalJWKSet, jwtVerify, type JSONWebKeySet } from 'jose';
import { koaBody } from 'koa-body';
import type { Context } from 'koa';
import { RESOURCES, ROLES } from './config.ts';
import { log } from './log.ts';
import { type User, UserError, type Users } from './users.ts';

function publicUser(user: User) {
  return {
    id: user.id,
    email: user.email,
    name: user.name,
    roles: user.roles,
    disabled: user.disabled,
    created_at: user.created_at,
    last_login_at: user.last_login_at,
  };
}

/**
 * User management API, for admins only. Takes access tokens issued for the
 * identity resource (aud = urn:stimmig:identity); tokens for the pipeline API
 * are rejected.
 */
export function manageRoutes(deps: { users: Users; issuer: string; publicJwks: JSONWebKeySet }) {
  const keys = createLocalJWKSet(deps.publicJwks);
  const router = new Router({ prefix: '/manage' });

  router.use(async (ctx, next) => {
    ctx.set('Cache-Control', 'no-store');
    const token = /^Bearer (.+)$/.exec(ctx.get('authorization'))?.[1];
    if (!token) return deny(ctx, 401, 'missing bearer token');
    try {
      const { payload } = await jwtVerify(token, keys, {
        issuer: deps.issuer,
        audience: RESOURCES.identity.indicator,
        algorithms: ['ES256'],
      });
      // Roles are read fresh from the database: a revoked admin loses access at once.
      const actor = typeof payload.sub === 'string' ? await deps.users.active(payload.sub) : undefined;
      if (!actor) return deny(ctx, 401, 'unknown or disabled user');
      if (!actor.roles.includes('admin')) return deny(ctx, 403, 'admin role required');
      ctx.state.actor = actor;
    } catch {
      return deny(ctx, 401, 'invalid access token');
    }
    try {
      await next();
    } catch (error) {
      if (error instanceof UserError) return deny(ctx, 422, error.message);
      throw error;
    }
  });

  const json = koaBody({ json: true, urlencoded: false, multipart: false, jsonLimit: '16kb' });

  router.get('/roles', (ctx) => {
    ctx.body = ROLES;
  });

  router.get('/users', async (ctx) => {
    ctx.body = (await deps.users.list()).map(publicUser);
  });

  router.post('/users', json, async (ctx) => {
    const input = ctx.request.body as { email?: string; name?: string; roles?: string[] };
    const user = await deps.users.create({ email: input.email ?? '', name: input.name ?? '', roles: input.roles ?? [] });
    log.info('user created', { by: (ctx.state.actor as User).id, user: user.id, roles: user.roles });
    ctx.status = 201;
    ctx.body = publicUser(user);
  });

  router.patch('/users/:id', json, async (ctx) => {
    const actor = ctx.state.actor as User;
    const changes = ctx.request.body as { name?: string; roles?: string[]; disabled?: boolean };
    // Guard against locking everyone out: admins can't remove their own admin role or disable themselves.
    if (ctx.params.id === actor.id && (changes.disabled === true || (changes.roles && !changes.roles.includes('admin')))) {
      return deny(ctx, 422, 'you cannot remove your own admin role or disable yourself');
    }
    const user = await deps.users.update(ctx.params.id!, changes);
    log.info('user updated', { by: actor.id, user: user.id, roles: user.roles, disabled: user.disabled });
    ctx.body = publicUser(user);
  });

  return router;
}

function deny(ctx: Context, status: number, detail: string): void {
  ctx.status = status;
  ctx.body = { detail };
  if (status === 401) ctx.set('WWW-Authenticate', 'Bearer error="invalid_token"');
}

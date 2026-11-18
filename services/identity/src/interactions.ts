import Router from '@koa/router';
import { koaBody } from 'koa-body';
import type Provider from 'oidc-provider';
import { errors } from 'oidc-provider';
import type { LoginCodes } from './codes.ts';
import { log } from './log.ts';
import type { Mailer } from './mailer.ts';
import type { Users } from './users.ts';
import { codeForm, emailForm, errorPage } from './views.ts';

const VERIFY_ERRORS = {
  invalid: 'Der Code stimmt nicht. Bitte prüfen Sie ihn und versuchen Sie es erneut.',
  expired: 'Der Code ist abgelaufen. Bitte fordern Sie einen neuen an.',
  locked: 'Zu viele Versuche mit diesem Code. Bitte fordern Sie einen neuen an.',
} as const;

/**
 * The login interaction: email → one-time code → logged in. Consent is not
 * asked: all clients are first-party and get their grant in loadExistingGrant.
 */
export function interactionRoutes(
  provider: Provider,
  deps: { users: Users; codes: LoginCodes; mailer: Mailer; clientOrigins: string[] },
) {
  // Browsers apply form-action to the redirects after a form post, so the clients' origins must be allowed.
  const formAction = ["'self'", ...deps.clientOrigins].join(' ');
  const router = new Router();
  const body = koaBody({ urlencoded: true, json: false, multipart: false, formLimit: '8kb' });

  router.use(async (ctx, next) => {
    ctx.set('Cache-Control', 'no-store');
    ctx.set('X-Frame-Options', 'DENY');
    ctx.set('Content-Security-Policy', `default-src 'none'; style-src 'unsafe-inline'; form-action ${formAction}; frame-ancestors 'none'`);
    try {
      await next();
    } catch (error) {
      if (error instanceof errors.SessionNotFound) {
        ctx.status = 400;
        ctx.type = 'html';
        ctx.body = errorPage('Die Anmeldung ist abgelaufen. Bitte starten Sie sie in der Anwendung neu.');
        return;
      }
      throw error;
    }
  });

  router.get('/interaction/:uid', async (ctx) => {
    const details = await provider.interactionDetails(ctx.req, ctx.res);
    ctx.type = 'html';
    if (details.prompt.name !== 'login') {
      // Every other prompt is resolved without user input; finish it.
      await provider.interactionFinished(ctx.req, ctx.res, {}, { mergeWithLastSubmission: true });
      return;
    }
    ctx.body = emailForm(details.uid);
  });

  router.post('/interaction/:uid/email', body, async (ctx) => {
    const details = await provider.interactionDetails(ctx.req, ctx.res);
    const email = String((ctx.request.body as Record<string, unknown>).email ?? '').trim();
    ctx.type = 'html';
    if (!email) {
      ctx.body = emailForm(details.uid, 'Bitte geben Sie Ihre E-Mail-Adresse ein.');
      return;
    }
    const user = await deps.users.byEmail(email);
    // Same response whether or not the address has an account (no user enumeration).
    if (user && !user.disabled) {
      const code = await deps.codes.issue(details.uid, user.email);
      if (code) await deps.mailer.sendLoginCode(user.email, code);
      else log.warn('login code rate limit reached', { user: user.id });
    }
    ctx.body = codeForm(details.uid, email);
  });

  router.post('/interaction/:uid/code', body, async (ctx) => {
    const details = await provider.interactionDetails(ctx.req, ctx.res);
    const code = String((ctx.request.body as Record<string, unknown>).code ?? '');
    const result = await deps.codes.verify(details.uid, code);
    if (!result.ok) {
      ctx.type = 'html';
      ctx.status = 400;
      ctx.body = codeForm(details.uid, '', VERIFY_ERRORS[result.reason]);
      return;
    }
    const user = await deps.users.byEmail(result.email);
    if (!user || user.disabled) {
      ctx.type = 'html';
      ctx.status = 403;
      ctx.body = errorPage('Dieser Zugang ist nicht aktiv.');
      return;
    }
    await deps.users.recordLogin(user.id);
    log.info('login', { user: user.id });
    await provider.interactionFinished(
      ctx.req,
      ctx.res,
      { login: { accountId: user.id, amr: ['otp', 'email'] } },
      { mergeWithLastSubmission: false },
    );
  });

  return router;
}

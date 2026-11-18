import { config } from './config.ts';
import { refresh } from './oidc.ts';
import type { Session } from './session.ts';

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
    readonly problems: string[] = [],
  ) {
    super(`${status}: ${detail}`);
  }
}

function detailOf(body: unknown): { detail: string; problems: string[] } {
  if (body && typeof body === 'object') {
    const { detail, problems } = body as { detail?: unknown; problems?: unknown };
    const problemList = Array.isArray(problems) ? problems.map(String) : [];
    if (typeof detail === 'string') return { detail, problems: problemList };
    // FastAPI validation errors: a list of {loc, msg}.
    if (Array.isArray(detail)) {
      return {
        detail: detail
          .map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join('.')}: ${d.msg ?? ''}`)
          .join('; '),
        problems: problemList,
      };
    }
  }
  return { detail: 'Unbekannter Fehler', problems: [] };
}

async function call<T>(baseUrl: string, token: string, method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(new URL(path, baseUrl), {
    method,
    headers: {
      authorization: `Bearer ${token}`,
      accept: 'application/json',
      ...(body === undefined ? {} : { 'content-type': 'application/json' }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload: unknown = response.headers.get('content-type')?.includes('json') ? await response.json() : undefined;
  if (!response.ok) {
    const { detail, problems } = detailOf(payload);
    throw new ApiError(response.status, detail, problems);
  }
  return payload as T;
}

export interface PipelineClient {
  get<T>(path: string): Promise<T>;
  post<T>(path: string, body?: unknown): Promise<T>;
  patch<T>(path: string, body: unknown): Promise<T>;
}

/** Calls the pipeline API as the logged-in user. The API decides what they may do. */
export function pipelineClient(session: Session | undefined): PipelineClient {
  const token = () => {
    if (!session) throw new ApiError(401, 'nicht angemeldet');
    return session.accessToken;
  };
  return {
    get: (path) => call(config.pipelineUrl, token(), 'GET', path),
    post: (path, body) => call(config.pipelineUrl, token(), 'POST', path, body ?? {}),
    patch: (path, body) => call(config.pipelineUrl, token(), 'PATCH', path, body),
  };
}

/**
 * Calls the identity service's user management. It needs a token for the
 * identity resource, which the refresh token is swapped for on demand; it is
 * never stored.
 */
export async function identityClient(session: Session): Promise<PipelineClient> {
  const tokens = await refresh(session.refreshToken, config.resources.identity);
  const token = tokens.access_token;
  return {
    get: (path) => call(config.issuer, token, 'GET', path),
    post: (path, body) => call(config.issuer, token, 'POST', path, body ?? {}),
    patch: (path, body) => call(config.issuer, token, 'PATCH', path, body),
  };
}

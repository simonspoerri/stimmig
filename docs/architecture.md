# Architecture

```
                         ┌──────────────────────────┐
   voters ──────────────►│ apps/web  (Astro SSR)    │──── GET /public/v1/* ───┐
                         └──────────────────────────┘                         │
                                                                              ▼
                         ┌──────────────────────────┐   Bearer JWT   ┌──────────────────────┐
 admin / reviewer /  ───►│ apps/admin (Astro SSR)   │──────────────► │ services/pipeline    │
 visualizer              │ OIDC client (code+PKCE)  │  /api/*        │ Python, FastAPI      │
                         └────────────┬─────────────┘                │ Postgres: votes,     │
                                      │ login, tokens                │ claims, charts, audit│
                                      ▼                              │ LLM extraction       │
                         ┌──────────────────────────┐   JWKS         │ evals                │
                         │ services/identity        │◄───────────────┤                      │
                         │ oidc-provider, Postgres  │                └──────────┬───────────┘
                         │ users, roles, sessions   │                           │
                         └──────────────────────────┘                           ▼
                                                                      Anthropic API (Claude)
```

## Components and their boundaries

| Component | Owns | Talks to | Never does |
|---|---|---|---|
| `apps/web` | nothing (stateless) | pipeline public API | log anyone in, call the LLM, show unpublished content |
| `apps/admin` | the user's session (encrypted cookie) | identity (OIDC), pipeline API, identity management API | store data of its own, decide permissions (it only hides buttons; the APIs enforce) |
| `services/identity` | users, roles, login codes, OIDC sessions and grants | its own Postgres database, a mailer | know anything about votes or claims |
| `services/pipeline` | votes, source documents, claims, charts, audit log, extraction runs | its own Postgres database, identity's JWKS, Anthropic API | manage users, trust a role it didn't read from a verified token |

Each service has its **own database**. They never read each other's tables;
the only coupling is OIDC (tokens and JWKS) and HTTP APIs.

## Roles and permissions

Roles are assigned to users in `services/identity` and travel as the
`roles` claim in JWT access tokens. Each API maps roles to permissions
itself, so the mapping lives next to the code that enforces it
([`services/pipeline/src/stimmig_pipeline/auth.py`](../services/pipeline/src/stimmig_pipeline/auth.py)).

| Permission | admin | reviewer | visualizer |
|---|:-:|:-:|:-:|
| read everything in the admin API | ✓ | ✓ | ✓ |
| `votes:write` – create and edit votes | ✓ | | |
| `documents:write` – add source documents | ✓ | | |
| `extraction:run` – run the LLM extraction | ✓ | | |
| `claims:review` – approve, correct, reject claims | | ✓ | |
| `visualizations:write` – create and edit charts | | | ✓ |
| `visualizations:review` – approve or reject charts | | ✓ | |
| `votes:publish` – publish and unpublish votes | ✓ | | |
| `users:manage` – assign roles (identity API) | ✓ | | |

Rules beyond the table, enforced in the pipeline service:

- **Four eyes:** a chart cannot be reviewed by the person who created or last
  edited it, even if that person also holds `reviewer`.
- Charts can only be attached to claims of class `fact` with status
  `approved`.
- A vote can only be published when every approved fact has an approved
  chart or a reason why it is not visualized, and every approved forecast
  says whose estimate it is.

## Login flow

```
admin app                         identity                         pipeline
─────────                         ────────                         ────────
GET /auth/login
 → 302 /auth?client_id=admin&code_challenge=…&resource=urn:stimmig:api
                                  email form → code mailed → code form
 ← 302 /auth/callback?code=…
POST /token (code, verifier, client secret)
 ← access token (JWT, 10 min, aud=urn:stimmig:api, roles=[…])
   + refresh token + id token
session cookie (encrypted)
GET /api/votes  Authorization: Bearer <access token> ─────────────────► verify signature (JWKS,
                                                                        cached), iss, aud, exp;
                                                                        roles → permissions
```

- Login is by **one-time code sent by email**: no passwords to leak or reset.
  Codes are stored as HMACs, expire after 10 minutes and allow five attempts.
  There is no self sign-up; an admin creates users. An unknown email gets the
  same response as a known one, so the form doesn't reveal who has an account.
- Access tokens are short-lived JWTs (ES256) bound to one resource:
  `urn:stimmig:api` for the pipeline, `urn:stimmig:identity` for user
  management. The admin app swaps its refresh token for an identity-resource
  token only when an admin opens user management.
- The public site has no login.

## Data model (pipeline)

```
votes ─┬─< documents ─< extraction_runs
       └─< claims ─< visualizations
audit_events (every write: who, what, when, before/after)
```

| Entity | Key fields | Status |
|---|---|---|
| vote | `id` (`YYYY-MM-DD-short-name`), date, title, kind, official URL, fixed source list | `draft` → `published` |
| document | vote, kind (booklet / parliament / public), side, title, URL, text | – |
| claim | vote, document, verbatim quote, side, class, rationale, estimate by, not-visualized reason | `draft` → `approved` / `rejected` |
| visualization | claim, title, description, Vega-Lite spec with inline data, data sources | `draft` → `in_review` → `approved` / `rejected` |
| extraction run | document, model, prompt hash, accepted and rejected claims | – |

## Pipeline: from text to published chart

1. **Extraction** – the model is called with a forced tool call and returns
   claims with class and rationale. Prompt:
   [`services/pipeline/prompts/extract_claims.md`](../services/pipeline/prompts/extract_claims.md).
2. **Deterministic checks** – a claim whose quote does not appear verbatim in
   the document is dropped (whitespace, typographic quotes and dashes are
   normalized; nothing else). Duplicates are dropped. Results are stored as
   `draft` claims with the extraction run that produced them.
3. **Claim review** – a reviewer approves, corrects (class, rationale,
   estimate by) or rejects. Corrections are kept in the audit log and become
   eval data.
4. **Chart** – a visualizer writes a Vega-Lite spec with inline data from an
   official source. Specs that fetch remote data are rejected.
5. **Chart review** – a different person approves or rejects.
6. **Publication** – an admin publishes the vote after the rules above pass.

## Evals

Evals measure the extraction step against hand-labelled data
([`services/pipeline/evals/`](../services/pipeline/evals)): recall and
precision of found claims, accuracy of the class, and separately the most
harmful error, a forecast or opinion labelled as fact. Datasets are split
into a `dev` part for prompt work and a `test` part that is only scored.
Thresholds in `evals/thresholds.toml` fail the run.

The model is reached through a narrow provider interface with three
implementations: live (Anthropic API), recording (live plus storing every
answer) and replay (stored answers only). CI replays recordings, so it needs
no secret and is reproducible; recordings are keyed by a hash of the full
request, so a changed prompt fails loudly instead of replaying stale
answers. Live runs repeat each item several times and report the spread.

## Repository layout

```
apps/web               public site (Astro SSR)
apps/admin             admin UI (Astro SSR)
services/identity      OIDC provider (Node, TypeScript)
services/pipeline      API, extraction, evals (Python)
packages/api-types     TypeScript types generated from the pipeline's OpenAPI
docs/                  concept, methodology, architecture, decisions (adr/)
scripts/               local development helpers
```

## Decisions

See [docs/adr/](adr):
[0001 components](adr/0001-split-into-components.md),
[0002 Python for the pipeline](adr/0002-python-for-the-pipeline.md),
[0003 own OIDC provider](adr/0003-own-oidc-provider.md),
[0004 recorded model answers for evals](adr/0004-record-replay-evals.md).

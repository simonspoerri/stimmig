# Stimmig

**Data visualizations of the claims made about Swiss federal popular votes.**

Before every federal vote, the official voting booklet
(*Abstimmungsbüchlein*) and the public debate are full of numbers. Stimmig
takes the verifiable factual claims made by **both sides**, puts them next to
official data, and shows the result as a chart with the original wording and
a link to the primary source. No forecasts, no voting recommendation.

Stimmig is also an open example of how to build an LLM-assisted system that
people can audit: extraction bound to its source text, deterministic
rendering, a human review with four-eyes principle, and evals that measure
the model's quality before anything changes.

## Components

| Component | Path | Stack | What it does |
|---|---|---|---|
| Public site | [`apps/web`](apps/web) | Astro (SSR) | Shows published claims and charts to voters, in German |
| Admin | [`apps/admin`](apps/admin) | Astro (SSR) | Votes, claim review, chart editor, users; OIDC login |
| Identity | [`services/identity`](services/identity) | Node, TypeScript, `oidc-provider` | OpenID Connect provider, email-code login, users and roles |
| Pipeline | [`services/pipeline`](services/pipeline) | Python, FastAPI | API and data store, LLM claim extraction, evals |

How they fit together: [docs/architecture.md](docs/architecture.md).
Why Stimmig exists and what it will not do: [docs/concept.md](docs/concept.md).
The rules every claim and chart follows: [docs/methodology.md](docs/methodology.md).

## Run it locally

Requirements: Node.js 22, Python 3.12+ with [uv](https://docs.astral.sh/uv/),
and PostgreSQL 16+ (or Docker for `compose.yaml`).

```sh
docker compose up -d postgres      # or any Postgres on localhost:5432 (user postgres, trust)
npm ci
(cd services/pipeline && uv sync)
scripts/dev.sh                     # starts identity, pipeline, admin and web
```

| URL | |
|---|---|
| http://localhost:4322 | public site |
| http://localhost:4321 | admin (log in with a seeded user, see below) |
| http://localhost:4000 | identity provider (`/.well-known/openid-configuration`) |
| http://localhost:8000/docs | pipeline API |

`scripts/dev.sh` seeds three local users, one per role:
`admin@stimmig.local`, `reviewer@stimmig.local`, `visualizer@stimmig.local`.
Login codes are printed to `.local/logs/identity.log` instead of being mailed.
Without `ANTHROPIC_API_KEY` the pipeline replays recorded model answers, which
exist for the synthetic example documents only.

To click through the whole process – admin, reviewer, visualizer, publication
– in a real browser, run `node scripts/walkthrough.mjs` against a fresh
database (needs Playwright installed on the machine).

## Checks

```sh
npm run check                                  # lint, typecheck, tests of the JS workspaces
(cd services/pipeline && uv run poe check)     # ruff, mypy, pytest
(cd services/pipeline && uv run stimmig-evals) # evals against recorded model answers, no API key
```

## License

Code: [MIT](LICENSE). Published content (claim selection, classification,
chart specs): CC BY 4.0. Quoted claims remain the work of their authors;
data stays under the terms of its source.

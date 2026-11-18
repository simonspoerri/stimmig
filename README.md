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

Requirements: Node.js 22 (`.nvmrc`; with [nvm](https://github.com/nvm-sh/nvm) `make` installs and uses it), [uv](https://docs.astral.sh/uv/)
and Docker (or your own PostgreSQL 16+).

```sh
make setup     # installs uv and dependencies, starts Postgres in Docker, creates the databases
make install   # only install tools and dependencies (also after pulling)
make dev       # starts identity, pipeline, admin and web; Ctrl-C stops all
make logs      # in a second terminal: follow all logs
make           # lists all targets (check, evals, db-reset, ...)
```

If port 5432 is already taken, pick another one: `make setup dev PG_PORT=55432`,
or put `PG_PORT=55432` in `.env`. To use your own Postgres instead of Docker:
`make dev NO_DOCKER=1 PGURL=postgresql://postgres@localhost:5432`.

| URL | |
|---|---|
| http://localhost:4322 | public site |
| http://localhost:4321 | admin (log in with a seeded user, see below) |
| http://localhost:4000 | identity provider (`/.well-known/openid-configuration`) |
| http://localhost:8000/docs | pipeline API |

`make dev` seeds three local users, one per role:
`admin@stimmig.local`, `reviewer@stimmig.local`, `visualizer@stimmig.local`.
Login codes are printed to `.local/logs/identity.log` instead of being mailed.
Without `ANTHROPIC_API_KEY` the pipeline replays recorded model answers, which
exist for the synthetic example documents only.

To click through the whole process – admin, reviewer, visualizer, publication
– in a real browser, run `node scripts/walkthrough.mjs` against a fresh
database (needs Playwright installed on the machine).

## Checks

```sh
make check     # npm run check (lint, typecheck, tests) and the pipeline's ruff, mypy, pytest
make evals     # evals against recorded model answers, no API key
```

## License

Code: [MIT](LICENSE). Published content (claim selection, classification,
chart specs): CC BY 4.0. Quoted claims remain the work of their authors;
data stays under the terms of its source.

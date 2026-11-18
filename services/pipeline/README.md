# Pipeline service

Python service that owns Stimmig's data and does the LLM work.

- **Admin API** (`/api/*`) for `apps/admin`: votes, source documents, claim
  extraction and review, charts and their review, publication, audit log.
  Every route needs a bearer token from `services/identity` and checks a
  permission ([`auth.py`](src/stimmig_pipeline/auth.py)).
- **Public API** (`/public/v1/*`) for `apps/web`: approved content of
  published votes only, with cache headers.
- **Extraction** ([`extraction.py`](src/stimmig_pipeline/extraction.py)): one
  forced tool call with the prompt in [`prompts/`](prompts), then a verbatim
  check of every quote.
- **Evals** ([`evals/`](evals)): see its README.

## Develop

```sh
uv sync
uv run poe check        # ruff, mypy (strict), pytest
uv run poe serve        # migrations, then the API on :8000 with reload
uv run stimmig-evals    # evals against recorded answers
```

Tests need a Postgres database (default
`postgresql+psycopg://postgres@localhost:5432/stimmig_pipeline_test`, or set
`TEST_DATABASE_URL`); they create the schema and empty the tables after
each test.

## Configuration

| Variable | Default | |
|---|---|---|
| `STIMMIG_DATABASE_URL` | `postgresql+psycopg://postgres@localhost:5432/stimmig_pipeline` | |
| `STIMMIG_OIDC_ISSUER` | `http://localhost:4000` | must match the tokens' `iss` |
| `STIMMIG_API_AUDIENCE` | `urn:stimmig:api` | must match the tokens' `aud` |
| `STIMMIG_LLM_MODE` | `live` | `live`, `record` or `replay` |
| `STIMMIG_MODEL` | `claude-sonnet-5-5` | |
| `ANTHROPIC_API_KEY` | – | for `live` and `record` |
| `APP_VERSION` | `dev` | reported by `/healthz` |

## Database changes

Change [`models.py`](src/stimmig_pipeline/models.py), then generate a
migration and review it before committing:

```sh
uv run alembic -c migrations.ini revision --autogenerate -m "what changed"
```

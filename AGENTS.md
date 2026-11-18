# AGENTS.md

Guidance for coding agents (and people) working in this repository.

- Read [docs/concept.md](docs/concept.md), [docs/methodology.md](docs/methodology.md)
  and [docs/architecture.md](docs/architecture.md) first. Every change to
  prompts, classification, review rules or charts must fit the methodology.
  If you change the methodology itself, do it in the same commit, explain why
  in the commit message, and update the German version in
  `apps/web/src/content/methodik.md`.
- **Language:** code, comments, docs and commit messages in English.
  User-facing text in `apps/web` and `apps/admin` in German (Swiss spelling,
  no ß), kept in one place per app so French and Italian can follow.
- **Never produce forecasts** – not in data, charts or texts.
- **This repository is public.** No secrets, real API keys, personal data or
  unreviewed claims in commits. Local secrets go in `.env` files (ignored).
- **Boundaries:** each service owns its database; components only talk over
  OIDC and HTTP APIs. Permissions are enforced in the APIs (the admin UI only
  hides what a user may not do). See the permission table in the
  architecture doc and keep it in sync with
  `services/pipeline/src/stimmig_pipeline/auth.py`.
- **Prompts** live in `services/pipeline/prompts/`. Changing one invalidates
  the recordings under `services/pipeline/evals/recordings/`: re-record with a
  live run and commit the new report, or CI fails.
- **API changes** in the pipeline: run `npm run gen:api-types` and commit
  `packages/api-types`; CI fails on drift.
- Before committing: `npm run check` and `(cd services/pipeline && uv run poe check)`.

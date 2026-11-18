# 0001 – Split into four components

Status: accepted, 2026-11-18

## Context

Stimmig has very different jobs: a public site read by many anonymous
visitors, an internal tool used by a handful of people, authentication, and
an LLM pipeline whose quality must be measured. A single app would mix
anonymous and privileged traffic, and tie the pipeline's language to the UI's.

## Decision

Four components with their own boundaries: `apps/web`, `apps/admin`,
`services/identity`, `services/pipeline`. Each service owns its database.
Components only talk over OIDC and HTTP APIs. All live in one repository.

## Consequences

- The public site can't leak unpublished content: it only has the public,
  read-only API, and holds no credentials.
- Permissions are enforced by the APIs, not the admin UI.
- More moving parts locally; `scripts/dev.sh` starts all of them.
- One repository keeps changes across components in one reviewable commit.

# 0002 – Python for the pipeline service

Status: accepted, 2026-11-18

## Context

The pipeline extracts claims from PDFs and text, will import data from
official statistics (PxWeb/STAT-TAB, CSV, SDMX), calls an LLM with structured
outputs, and is the component measured with evals. The frontends use Astro
(TypeScript).

## Decision

Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 with Alembic migrations,
managed with uv. Ruff and mypy (strict) for linting and types, pytest for
tests.

## Consequences

- Best available tooling for PDF and statistical data, and for data analysis
  of eval results.
- Pydantic models give one source of truth for validation, the OpenAPI
  schema and the LLM tool schema.
- Two languages in the repo. TypeScript types for the frontends are
  generated from the pipeline's OpenAPI schema (`packages/api-types`), and CI
  fails if they drift.

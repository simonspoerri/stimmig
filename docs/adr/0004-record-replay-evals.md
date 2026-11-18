# 0004 – Recorded model answers for evals and tests

Status: accepted, 2026-11-18

## Context

Evals and tests that call the model need an API key, cost money and give
different answers each run. A public repository's CI should run without
secrets, also for pull requests from forks.

## Decision

The pipeline reaches the model through a `LlmProvider` interface with live,
recording and replay implementations. Recordings are stored in the repository
under `services/pipeline/evals/recordings/`, keyed by a hash of the full
request (model, prompt, input, tool schema). CI always replays. Live runs
(with a key) record new answers, repeat items to measure spread, and write
the report that is committed with the recordings.

## Consequences

- CI is free, deterministic and secret-free.
- Changing a prompt without re-recording fails CI with a clear message.
- Replay only proves the pipeline code handles the recorded answers
  correctly; model quality is what the committed live report says.

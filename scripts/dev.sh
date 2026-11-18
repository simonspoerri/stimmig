#!/usr/bin/env bash
# Starts all four components for local development and seeds one user per role.
# Logs go to .local/logs/<component>.log; login codes appear in identity.log.
set -euo pipefail
cd "$(dirname "$0")/.."

PG="${PGURL:-postgresql://postgres@localhost:5432}"
mkdir -p .local/logs

# Without an API key the pipeline replays recorded model answers, which only
# exist for the synthetic example documents (see services/pipeline/evals).
if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then llm_mode=live; else llm_mode=replay; fi

(cd services/pipeline && uv run python - "$PG" <<'PY'
import sys, psycopg
with psycopg.connect(f"{sys.argv[1]}/postgres", autocommit=True) as c:
    for db in ("stimmig_pipeline", "stimmig_identity"):
        if not c.execute("select 1 from pg_database where datname = %s", (db,)).fetchone():
            c.execute(f'create database "{db}"')
PY
)

export DATABASE_URL="$PG/stimmig_identity"
for user in admin reviewer visualizer; do
  npm run --silent users -w @stimmig/identity -- add --email "$user@stimmig.local" \
    --name "${user^} (lokal)" --roles "$user" 2>/dev/null || true
done

pids=()
start() { # name, command...
  local name=$1; shift
  ("$@" >".local/logs/$name.log" 2>&1) &
  pids+=($!)
  echo "started $name (log: .local/logs/$name.log)"
}
trap 'kill "${pids[@]}" 2>/dev/null; wait' EXIT INT TERM

start identity env DATABASE_URL="$PG/stimmig_identity" npm run dev -w @stimmig/identity
start pipeline env -C services/pipeline STIMMIG_DATABASE_URL="postgresql+psycopg://${PG#postgresql://}/stimmig_pipeline" \
  STIMMIG_LLM_MODE="$llm_mode" uv run stimmig-pipeline serve --port 8000 --reload
start admin npm run dev -w @stimmig/admin
start web npm run dev -w @stimmig/web

echo
echo "public site  http://localhost:4322"
echo "admin        http://localhost:4321   (users: admin|reviewer|visualizer@stimmig.local)"
echo "identity     http://localhost:4000"
echo "pipeline     http://localhost:8000/docs   (LLM mode: $llm_mode)"
echo "login codes: tail -f .local/logs/identity.log"
wait

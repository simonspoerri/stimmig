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

scripts/create-databases.sh

export DATABASE_URL="$PG/stimmig_identity"
for user in admin reviewer visualizer; do
  name="$(tr '[:lower:]' '[:upper:]' <<<"${user:0:1}")${user:1}" # bash 3.2 (macOS) has no ${user^}
  # Only "already exists" is fine; anything else means logins would silently get no code.
  if ! out=$(npm run --silent users -w @stimmig/identity -- add --email "$user@stimmig.local" \
      --name "$name (lokal)" --roles "$user" 2>&1) && [[ $out != *"already exists"* ]]; then
    echo "seeding $user@stimmig.local failed (try: make install):" >&2
    echo "$out" >&2
    exit 1
  fi
done

pids=()
start() { # name, command...
  local name=$1; shift
  ("$@" >".local/logs/$name.log" 2>&1) &
  pids+=($!)
  echo "started $name (log: .local/logs/$name.log)"
}
# Stopping must reach the whole tree (npm -> astro/tsx/uvicorn): the tools
# start their own process groups, and killing just npm leaves them holding
# the ports. So collect every descendant first, TERM them, KILL stragglers.
descendants() { local c; for c in $(pgrep -P "$1"); do descendants "$c"; echo "$c"; done; }
stop() {
  trap - EXIT INT TERM
  local all; all=$(descendants $$)
  [[ -z $all ]] && return
  kill -TERM $all 2>/dev/null || true
  local pid alive
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    alive=; for pid in $all; do kill -0 "$pid" 2>/dev/null && alive+=" $pid"; done
    [[ -z $alive ]] && return 0
    sleep 0.5
  done
  kill -KILL $alive 2>/dev/null || true
}
trap stop EXIT INT TERM

start identity env DATABASE_URL="$PG/stimmig_identity" npm run dev -w @stimmig/identity
start pipeline env -C services/pipeline STIMMIG_DATABASE_URL="postgresql+psycopg://${PG#postgresql://}/stimmig_pipeline" \
  STIMMIG_LLM_MODE="$llm_mode" uv run stimmig-pipeline serve --port 8000 --reload
# --ignore-lock keeps astro in the foreground: when it detects an AI agent it
# otherwise detaches into a background server that this script cannot stop.
start admin npm run dev -w @stimmig/admin -- --ignore-lock
start web npm run dev -w @stimmig/web -- --ignore-lock

echo
echo "public site  http://localhost:4322"
echo "admin        http://localhost:4321   (users: admin|reviewer|visualizer@stimmig.local)"
echo "identity     http://localhost:4000"
echo "pipeline     http://localhost:8000/docs   (LLM mode: $llm_mode)"
echo "login codes: tail -f .local/logs/identity.log"
wait

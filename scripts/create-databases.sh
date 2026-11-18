#!/usr/bin/env bash
# Creates the local databases (dev and test, one per service) if missing.
# Uses the pipeline's psycopg so no psql client is needed on the machine.
set -euo pipefail
cd "$(dirname "$0")/.."

PG="${PGURL:-postgresql://postgres@localhost:5432}"

(cd services/pipeline && uv run --quiet python - "$PG" <<'PY'
import sys, psycopg
dbs = ("stimmig_pipeline", "stimmig_identity", "stimmig_pipeline_test", "stimmig_identity_test")
with psycopg.connect(f"{sys.argv[1]}/postgres", autocommit=True) as c:
    for db in dbs:
        if not c.execute("select 1 from pg_database where datname = %s", (db,)).fetchone():
            c.execute(f'create database "{db}"')
            print(f"created database {db}")
PY
)

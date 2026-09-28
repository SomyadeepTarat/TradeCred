#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
if [[ "${CONFIRM:-}" != "" && "${CONFIRM}" != RESET-DEMO ]]; then
  echo "CONFIRM must be RESET-DEMO or omitted for preview." >&2
  exit 2
fi
if [[ "${CONFIRM:-}" == RESET-DEMO ]]; then
  # The container uses the same database configuration as the API being reset.
  # Stop API writes first; keep it stopped until make demo rebuilds fixtures.
  docker compose run --rm --no-deps -T api .venv/bin/python -m app.cli.reset_demo
  docker compose stop api
  docker compose run --rm --no-deps -T api .venv/bin/python -m app.cli.reset_demo --confirm RESET-DEMO
  echo "Run make demo to restart the API and reseed fixtures."
else
  docker compose run --rm --no-deps -T api .venv/bin/python -m app.cli.reset_demo
fi

#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
make keys
SIMULATOR_ENABLED=true docker compose --profile demo up --build --wait
make seed
make seed-fixtures
echo "Demo ready at http://localhost:3000. Follow docs/demo-script.md."

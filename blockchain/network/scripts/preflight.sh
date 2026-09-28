#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$root"
docker compose --profile drunix run --rm --no-deps drunix-gateway --check-config

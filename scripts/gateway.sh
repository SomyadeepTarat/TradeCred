#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
module="$root/services/drunix-gateway"
if command -v go >/dev/null 2>&1; then
  cd "$module"
  exec "$@"
fi
exec docker run --rm \
  --mount "type=bind,source=$module,target=/chaincode" \
  --mount type=volume,source=tradecred_go_modules,target=/go/pkg/mod \
  --mount type=volume,source=tradecred_go_build,target=/root/.cache/go-build \
  -w /chaincode golang:1.26@sha256:6c2a5538f964f1c82f97ad14988bf05de100d922d159d0e398b54c7b0ca0c6c9 "$@"

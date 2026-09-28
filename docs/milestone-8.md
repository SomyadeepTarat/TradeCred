# Milestone 8 — Drunix Gateway

Implemented after reading the complete PRD and inspecting the existing repository.
Milestone 9 has not been started. The application now switches adapters by environment.
Live Drunix deployment remains unverified because no provisioned network or credentials
were supplied. Local tests use explicitly identified transport doubles; no fake integration
is used in application flows.

## Delivered

- DrunixLedgerClient with authenticated HTTP bridge to the official Fabric Gateway SDK,
  peer TLS, mapped organization identities, explicit endorsers and allowlisted operations.
- VALID commit required before returning a successful mutation. No automatic mock fallback.
  `LEDGER_BACKEND=mock` explicitly selects the existing PostgreSQL MockLedgerClient.
- Atomic chaincode operation receipts and durable private-input journaling for recovery
  from lost commit responses or failed local database commits, retaining original terms.
- Backend/network binding, backend-aware API/UI/audits, and 64-character Fabric transaction
  ID storage. Registration retries cannot rewind a more advanced ledger state.
- Version 0006 migration, API version 0.8.0, optional gateway Compose profile, credential
  template, real peer CLI lifecycle scripts and offline configuration preflight.
- Unit, HTTP-boundary, PostgreSQL and recovery tests; Go race tests, builds and CI checks.

## Commands

```sh
make dev                         # Existing explicit mock stack
make migrate
make seed
make test
make test-integration
make lint
make test-e2e
make build-chaincode build-gateway
docker compose --profile drunix build drunix-gateway
```

For live deployment follow the [network guide](../blockchain/network/README.md), including
identity issuance, peer CLI environment, packaging, organization approvals and configuration.
`make drunix-preflight` requires those private files. Preflight only parses files; it is not
a connectivity or commit check. It correctly exits nonzero when credentials are absent.

## Validation

- API unit suite: 335 tests.
- PostgreSQL integration suite: 78 tests, including four Drunix transport-double tests.
- Web unit suite: 20 tests; production-build Playwright suite: three scenarios.
- Chaincode: 13 top-level tests with race detection, 80.0% statement coverage.
- Gateway: four top-level tests with race detection, 47.9% statement coverage. Untested
  SDK network paths require a provisioned network; coverage does not imply live validation.
- Ruff lint/format, mypy, ESLint, TypeScript, Prettier, gofmt and go vet passed.
- Both Go executable builds, optional gateway Docker image, API/web Docker rebuild,
  migration upgrade, shell syntax checks and Compose validation passed.
- Default local API/web/PostgreSQL containers are healthy. No Drunix network was started.

## Remaining issues and boundaries

- Live Drunix compatibility, enrollment, endorsement policies, PDC dissemination, MVCC and
  ordering/commit behavior require a provisioned Fabric-compatible network and live tests.
- The bridge currently supports server-authenticated peer TLS, not peer mutual TLS.
- Internal bearer access controls organization signing identities; deploy on a private
  network and use HTTPS for remote relay access. Private journal data needs protected backups.
- Database and ledger are separate commit domains. Recovery requires repeating the same
  action; there is no background repair worker. Preserve pending journal records. Changing
  channel/chaincode/network deployment requires a new network ID and fresh assets.
- Migration downgrade intentionally retains the widened payment transaction-ID column to
  avoid truncating already committed Fabric receipts.
- Disbursement remains the explicit mock payment adapter; no funds move. Settlement
  retains timestamp/signature/replay checks. No automatic realization/e-BRC/closure UX
  or Milestone 9 demo features have been introduced.

## Files created

- apps/api/app/integrations/ledger/drunix.py
- apps/api/app/models/drunix.py
- apps/api/app/services/ledger_mode.py
- apps/api/migrations/versions/0006_durable_drunix_inputs_and_backend_binding.py
- apps/api/tests/test_drunix.py
- blockchain/chaincode/tradecred/operations.go
- blockchain/network/config/gateway.example.json
- blockchain/network/scripts/lifecycle.sh
- blockchain/network/scripts/package.sh
- blockchain/network/scripts/preflight.sh
- docs/milestone-8.md
- scripts/gateway.sh
- services/drunix-gateway/.dockerignore
- services/drunix-gateway/Dockerfile
- services/drunix-gateway/go.mod
- services/drunix-gateway/go.sum
- services/drunix-gateway/main.go
- services/drunix-gateway/main_test.go

## Files modified

- .env.example
- .github/workflows/ci.yml
- .gitignore
- Makefile
- README.md
- apps/api/app/core/config.py
- apps/api/app/integrations/ledger/base.py
- apps/api/app/integrations/ledger/factory.py
- apps/api/app/integrations/ledger/mock.py
- apps/api/app/main.py
- apps/api/app/models/domain.py
- apps/api/app/models/settlement.py
- apps/api/app/schemas/financing.py
- apps/api/app/schemas/ledger.py
- apps/api/app/schemas/settlement.py
- apps/api/app/services/financing_service.py
- apps/api/app/services/ledger_service.py
- apps/api/app/services/receivable_queries.py
- apps/api/app/services/settlement_service.py
- apps/api/migrations/env.py
- apps/api/pyproject.toml
- apps/api/tests/test_config.py
- apps/api/uv.lock
- apps/web/components/receivable-detail.tsx
- blockchain/chaincode/tradecred/contract.go
- blockchain/chaincode/tradecred/contract_test.go
- blockchain/chaincode/tradecred/models.go
- blockchain/network/README.md
- docker-compose.yml
- docs/api.md
- docs/architecture.md
- docs/threat-model.md

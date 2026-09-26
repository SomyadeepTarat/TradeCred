# Milestone 3 — Mock Ledger

Completed against `tradecred_prd_codex.md`. Milestone 4 has not been started.

## Delivered

- Typed, asynchronous LedgerClient protocol with all seven PRD operations and an explicit
  PostgreSQL-backed MockLedgerClient. Mock receipts identify `backend: mock` and use
  `MOCK-` transaction IDs. Selecting Drunix fails closed with 503; it never falls back.
- Authenticated submit, admin verify, register, open-for-financing, registry and history APIs.
  Registration is idempotent by stable asset ID and immutable registration inputs. Retries
  preserve the current state and return the original registration transaction ID.
- Shared PRD state matrix; invalid transitions return 409. Row/advisory locks and unique
  constraints prevent concurrent fingerprint registration and multiple lock owners.
- Sanitized ledger projections and a separate private table for exact amounts/references.
  No invoice PDF, buyer ID, filename or storage key is included in ledger projections.
- Audit events for new invoice creation, lifecycle changes, registry checks and duplicate
  rejection, with server-generated request correlation IDs. Admin audit listing and owner/
  admin history are available. Migration 0003 creates the four new tables.
- Transactional mock updates: ledger state, application projection and success audit commit
  together. Injected ledger failure rolls back; no false success response is returned.

Internal ledger lock/payment operations exist to implement the protocol and enforce its
invariants. They are not exposed through financing or settlement APIs in this milestone.
Future settlement ingestion must authenticate signed events before calling the adapter.

## Files created

- `apps/api/app/integrations/ledger/base.py` — interface and typed inputs/receipts/projections.
- `apps/api/app/integrations/ledger/mock.py` — persisted simulation and ledger guards.
- `apps/api/app/integrations/ledger/factory.py` — explicit backend selection.
- `apps/api/app/models/ledger.py` — mock global/private state, transactions and audit models.
- `apps/api/app/schemas/ledger.py` — lifecycle, registry and history API contracts.
- `apps/api/app/services/state_machine.py` — PRD transition matrix.
- `apps/api/app/services/audit_service.py` — allowlisted audit metadata.
- `apps/api/app/services/ledger_service.py` — lifecycle orchestration and transaction boundary.
- `apps/api/app/api/routes/ledger.py` — authenticated lifecycle/registry/history/admin audit routes.
- `apps/api/app/core/request_id.py` — request correlation middleware.
- `apps/api/migrations/versions/0003_mock_ledger_and_audit_history.py` — schema migration.
- `apps/api/tests/test_state_machine.py` — exhaustive transition and value-bucket tests.
- `apps/api/tests/test_mock_ledger.py` — adapter, concurrency, ownership and payment guards.
- `apps/api/tests/test_ledger_api.py` — end-to-end lifecycle, privacy, duplicates and failure tests.
- `docs/milestone-3.md` — this report.

## Files modified

- `apps/api/app/main.py` — routes, middleware and API version.
- `apps/api/app/core/errors.py` — structured duplicate-conflict details.
- `apps/api/app/api/routes/receivables.py` and
  `apps/api/app/services/receivable_service.py` — request-correlated upload/duplicate audits.
- `apps/api/migrations/env.py` — include ledger metadata in migration checks.
- `apps/api/pyproject.toml` and `apps/api/uv.lock` — API version/description; no new dependencies.
- `apps/web/app/page.tsx` and `apps/web/tests/page.test.tsx` — accurate Milestone 3 status copy.
- `Makefile` — correct scope message for unavailable later-milestone targets.
- `README.md`, `docs/api.md`, `docs/architecture.md` — setup, endpoints, transaction semantics,
  privacy boundaries and remaining limitations.

## Commands to run

```sh
make install
make dev              # Docker build, migrations, services, health checks
make seed             # Explicit, idempotent demo identity seed
make test
make test-integration # Requires running PostgreSQL; isolated generated schemas
make lint
make build
```

For host development, use `make db`, `make migrate`, `make seed`, then `make api` and
`make web` in separate terminals. Host and Docker document stores differ; preserve the
matching files when switching modes. Use `/docs` at http://localhost:8000/docs for the
role-based workflow documented in `docs/api.md`.

## Verification performed

- `make format`: passed.
- `make test`: 323 API unit tests and 1 frontend render test passed.
- `make test-integration`: 30 PostgreSQL tests passed, including migration
  upgrade/downgrade/upgrade and metadata alignment. Total: **354 passing tests**.
- `make lint`: Ruff checks/format, strict mypy, ESLint, TypeScript and Prettier passed.
- `make build`: production Next.js build passed.
- `docker compose up --build --wait`: API/web images rebuilt; all three services healthy;
  startup successfully applied migration 0003 to the development database.
- Running-container HTTP smoke check: readiness, API 0.4.0 routes, authenticated mock
  fingerprint lookup, persisted request-correlated audit and Milestone 3 page passed.
  The synthetic absent-fingerprint lookup leaves its normal audit record, no invoice/file.
- `git diff --check`: passed.

Tests exercise all 225 state pairs, idempotent registration after subsequent advancement,
local and ledger-level duplicate rejection, concurrent registrations and locks, private
projection fields, role restrictions, audit history, tampered PDF rejection, Drunix 503,
rollback after a partially flushed mock write, lock ownership, agreement validation,
payment amount/currency mismatch, payment replay and terminal-state protection.

## Remaining issues and boundaries

No Milestone 3 test failures or implementation blockers remain. Docker was initially
paused; the user resumed it and all database/container checks subsequently passed.

This is a local simulation, not Drunix consensus or immutable blockchain history. A DB
administrator can read the private table and alter records. Exact amounts are separated
from public projections but do not yet use Fabric private collections. Existing pre-M3
records receive no fabricated audit history. Verification checks integrity and records
an admin decision; it does not establish commercial authenticity.

The receivables UI is Milestone 4. Financing workflows, signed settlement ingestion,
chaincode and the real Drunix gateway remain their scheduled milestones. No funds move
and no regulatory certificate is issued. Existing login-rate-limit/security-audit hardening
and document-storage crash reconciliation limitations remain documented in README.

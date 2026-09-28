# Milestone 9 — Demo UX

Implemented only Milestone 9 after rereading the complete PRD and inspecting the repository.
All three required financial demo scenarios can now be demonstrated through the UI without
manual database edits. Milestone 10 reset/hardening work has not been started.

## Delivered

- Standalone registry checker with normalized invoice identity, explicit ledger backend,
  fingerprint, existing asset/status, and duplicate-financing warning. No private terms
  are returned; a clear result is not credit approval or an off-network fraud guarantee.
- Settlement-role simulator: sanitized asset selection, amount/currency/reference,
  valid signature, invalid signature and exact replay controls with verification outcomes.
- Separate opt-in Ed25519 signer service. The private key never mounts into the API or
  browser. All events pass through the existing signature, timestamp, nonce, amount,
  currency, bank identity, state and replay checks. Unknown outcomes remain unknown.
- Persisted simulator event bytes/signatures scoped to their submitting user. Browser
  responses never expose either. Failed signing never submits a payment event.
- Admin-only audit/security dashboard with paginated activity and independent scrolling
  feeds for duplicate attempts, successful transitions and rejected settlement events.
- Responsive navigation and a recorded-status journey through closure. Administrator
  actions expose the existing REALIZED → EBRC_ELIGIBLE → CLOSED ledger transitions.
  Eligibility records SELF_CERTIFICATION_PENDING and never claims certificate issuance.
- API-driven fixture seeding: flagship EXP-2026-1042, clean verified, finance-available,
  financed and realized examples, plus a duplicate upload PDF/metadata fixture. Seeding
  preserves advanced records and refuses conflicting existing invoice terms.
- `make demo`, optional Compose profile, idempotent key/token setup, version 0007 migration,
  API version 0.9.0, updated walkthrough, and complete demo browser coverage.

## Commands

```sh
make install                # First setup, after configuring .env
make demo                   # Build/start sandbox and seed via real API workflows
make seed-fixtures          # Resume fixture setup; preserve existing state
make test
make test-integration
make lint
make test-e2e
```

Open http://localhost:3000 and follow [the walkthrough](demo-script.md). Use the existing
DEMO_PASSWORD for each seeded account. `make seed` still creates identities only. Demo PDFs,
metadata and receivable IDs are written under ignored `data/demo/`. Asset IDs come from the
normal registration workflow, not a fabricated fixed ledger ID.

## Verification performed

- 335 API unit tests passed.
- 83 PostgreSQL integration tests passed, including five new demo tests with real
  Ed25519 signing, role restrictions, audit privacy, exact replay, terminal closure,
  signer outage, uncertain-outcome retry and idempotent API seeding.
- Existing Drunix transport-double workflow extended through closure, including loss of
  the realization response, retry recovery and exactly one realization audit event.
- 20 web unit tests passed.
- All three production-build Playwright scenarios passed. The financing scenario now
  covers registry duplicate warning, fake/valid settlement, replay, closure and admin
  security results. Mobile overflow and asset-selector labeling defects found during
  testing were fixed. Desktop/mobile screenshots were inspected.
- Chaincode and gateway Go race suites passed (13 and four top-level tests respectively).
- Ruff lint/format, mypy, ESLint, TypeScript, Prettier, gofmt and go vet passed.
- Next production build, Docker API/web/signer builds, automatic migration 0007,
  Compose profile validation, shell syntax and `git diff --check` passed.
- `make demo` succeeded twice with the same four fixture IDs; API, web, PostgreSQL and
  signer containers are healthy. Existing users, passwords and keys were preserved.

Total: 441 application/browser tests, plus both Go suites. Tests use isolated schemas,
PDF storage and temporary signing keys. No live Drunix transaction is claimed.

## Remaining issues and scope boundaries

- Live Drunix validation still requires provisioned infrastructure and credentials.
- Payments remain sandbox simulations. TradeCred does not move FX, issue regulatory
  certificates, or make a token state a legal assignment.
- The simulator is disabled by default; `make demo` enables it for that Compose invocation.
  Its token and signing key are private local-demo credentials, not a production bank.
- Replay controls retain the most recent simulator ID in the current page. Keep the page
  open during recovery. Exact events still obey the timestamp window; old replays may
  be rejected as stale. No background recovery worker is introduced.
- The asset selector displays the latest 100 eligible/post-settlement records. Audit feeds
  paginate 50 events at a time. Full scale operational reporting remains outside this demo.
- `make reset` remains intentionally unavailable until Milestone 10. Upload a new invoice
  number to demonstrate another cycle without deleting existing records.

## Files created

- .dockerignore
- apps/api/app/api/routes/demo.py
- apps/api/app/models/simulator.py
- apps/api/app/schemas/demo.py
- apps/api/app/services/audit_queries.py
- apps/api/app/services/simulator_service.py
- apps/api/migrations/versions/0007_simulator_events.py
- apps/api/tests/test_demo.py
- apps/web/app/receivables/audit/page.tsx
- apps/web/app/receivables/registry/page.tsx
- apps/web/app/receivables/settlement/page.tsx
- apps/web/components/audit-dashboard.tsx
- apps/web/components/lifecycle-timeline.tsx
- apps/web/components/registry-checker.tsx
- apps/web/components/settlement-simulator.tsx
- docs/milestone-9.md
- scripts/run_demo.sh
- scripts/seed_fixtures.py
- services/bank-simulator/Dockerfile
- services/bank-simulator/server.py

## Files modified

- .env.example
- Makefile
- README.md
- apps/api/app/api/routes/ledger.py
- apps/api/app/core/config.py
- apps/api/app/main.py
- apps/api/app/services/ledger_service.py
- apps/api/app/services/receivable_queries.py
- apps/api/migrations/env.py
- apps/api/pyproject.toml
- apps/api/tests/test_drunix.py
- apps/api/tests/test_signatures.py
- apps/api/uv.lock
- apps/web/app/globals.css
- apps/web/components/dashboard.tsx
- apps/web/components/receivable-detail.tsx
- apps/web/components/workspace.tsx
- apps/web/lib/gateway.ts
- apps/web/tests/e2e/financing.spec.ts
- apps/web/tests/e2e/receivables.spec.ts
- apps/web/tests/gateway.test.ts
- docker-compose.yml
- docs/api.md
- docs/architecture.md
- docs/demo-script.md
- docs/threat-model.md
- scripts/generate_keys.py
- scripts/test_ui.py
- services/bank-simulator/README.md

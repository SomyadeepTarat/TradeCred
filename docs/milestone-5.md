# Milestone 5 — Financing

Implemented after inspecting the repository and reading the full PRD. Milestone 6 has not
been started.

## Delivered

- Financier dashboard with available assets, own offers and assigned receivables.
- Private offers with exact decimal amounts, basis-point rates, tenor and expiry; exporter
  review, acceptance and rejection. Offers require a registered FINANCE_AVAILABLE asset,
  use the invoice currency and cannot exceed its face value. No FX conversion is implied.
- Canonical TC-AGR-1 agreement and SHA-256 hash; acceptance locks the asset to one financier.
  Only the exporter and winning institution can read the agreement. Other institutions see
  sanitized asset data and their own offers, never another institution's terms or raw PDF.
- Explicit MockLedgerClient and persisted MockNPCIPaymentAdapter disbursement, labeled
  “NPCI Payment Adapter — Sandbox Simulation”. Only the winning financier can record it.
  Successful simulation transitions LOCKED to FINANCED and records MOCK/MOCKPAY identifiers.
- Receivable row locks serialize acceptance and payout. Ledger simulation, projection,
  agreement, payment and audit writes share a PostgreSQL transaction. Acceptance and payout
  retries return existing receipts; competing financing is rejected. Failures roll back.
- Migration 0004 and an additional seeded institution, nbfc@tradecred.demo; existing
  identities and passwords are preserved.

## Files created

- `apps/api/app/api/routes/financing.py`
- `apps/api/app/integrations/payments/base.py`
- `apps/api/app/integrations/payments/mock_npci.py`
- `apps/api/app/models/financing.py`
- `apps/api/app/schemas/financing.py`
- `apps/api/app/services/agreement_service.py`
- `apps/api/app/services/financing_service.py`
- `apps/api/app/services/receivable_access.py`
- `apps/api/migrations/versions/0004_financing_offers_agreements_and_disbursements.py`
- `apps/api/tests/test_agreement.py`
- `apps/api/tests/test_financing.py`
- `apps/web/components/financier-dashboard.tsx`
- `apps/web/components/financing-panel.tsx`
- `apps/web/lib/financing.ts`
- `apps/web/tests/e2e/financing.spec.ts`
- `apps/web/tests/financing.test.tsx`
- `docs/milestone-5.md`

## Files modified

- `Makefile`
- `README.md`
- `apps/api/app/api/routes/receivables.py`
- `apps/api/app/main.py`
- `apps/api/app/schemas/receivable_views.py`
- `apps/api/app/services/audit_service.py`
- `apps/api/app/services/ledger_service.py`
- `apps/api/app/services/receivable_queries.py`
- `apps/api/app/services/seed_service.py`
- `apps/api/migrations/env.py`
- `apps/api/pyproject.toml`
- `apps/api/tests/test_ledger_api.py`
- `apps/api/tests/test_receivable_views.py`
- `apps/api/uv.lock`
- `apps/web/app/globals.css`
- `apps/web/components/dashboard.tsx`
- `apps/web/components/login.tsx`
- `apps/web/components/receivable-detail.tsx`
- `apps/web/components/workspace.tsx`
- `apps/web/lib/api.ts`
- `apps/web/lib/gateway.ts`
- `apps/web/tests/e2e/receivables.spec.ts`
- `apps/web/tests/page.test.tsx`
- `docs/api.md`
- `docs/architecture.md`
- `docs/threat-model.md`

## Commands

```sh
make install
make dev
make seed
# Open http://localhost:3000 and use the demo identities from README.md.
make test
make test-integration
make lint
make build
# Once per machine:
cd apps/web && npx playwright install chromium && cd ../..
make test-e2e
```

`make dev` applies database migrations when the API container starts. For host development,
run `make db`, `make migrate`, then `make api` and `make web` in separate terminals.
Browser tests require PostgreSQL and free ports 8001/3001, create an isolated schema and
remove their temporary records/files. Screenshots are ignored under apps/web/test-results.

## Verification

- **399 tests passed:** 324 API unit, 52 PostgreSQL integration, 20 frontend/gateway and
  3 Chromium acceptance tests.
- Integration checks cover competing and repeated concurrent acceptance/payout, rejected
  competitor financing, role/organization privacy, expiry, input validation, canonical hash
  integrity, tampering, migration alignment/roundtrip and rollback after payment insertion.
  Drunix unavailability fails closed rather than reporting a successful payment.
- Real-browser flow: two institutions offer, exporter reviews/accepts one, other offer is
  rejected, winning institution simulates financing, reload preserves state and competing
  institution cannot disburse. No browser JavaScript errors or mobile horizontal overflow.
- Desktop accepted-offer and mobile financed screenshots inspected.
- Production Next.js build, Ruff lint/format, strict mypy, ESLint, TypeScript and Prettier pass.
- Docker rebuild/start passed; PostgreSQL, API and web are healthy. Live smoke check verified
  API 0.6.0, financing routes, second financier login, HttpOnly session, scoped no-store list,
  logout and subsequent unauthorized access.
- Working-tree and staged whitespace checks passed. Existing staging was preserved.

## Remaining boundaries

No outstanding Milestone 5 test failures. Drunix and NPCI infrastructure are unavailable:
ledger and payment operations remain explicit local simulations and no funds move. Agreement
hashes and financing state do not confer legal ownership. Signed settlement is Milestone 6.

Expiry is reflected immediately on reads and persisted during financing mutations; there is
no background expiry worker. External payment reconciliation, production session hardening,
rate limiting and broader operational security remain later work documented in the threat
model. The mock adapter's atomic database transaction does not imply external bank finality.

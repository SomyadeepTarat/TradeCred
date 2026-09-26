# Milestone 4 — Receivables UI

Implemented from the PRD after inspecting Milestone 3. Milestone 5 has not been started.

## Delivered

- Responsive exporter dashboard with actual organization-scoped totals, status filtering,
  pagination, recent recorded activity and empty/error/loading states.
- Sign-in, session expiry and sign-out through a same-origin Next.js gateway. JWTs remain
  in HttpOnly, SameSite=Strict cookies; browser JavaScript receives no bearer token.
- Create-receivable form for all PRD invoice fields and PDF upload. Amounts stay decimal
  strings; duplicate errors preserve the entered form.
- Detail view with full document hash/fingerprint, real registry lookup, PDF integrity and
  download, lifecycle actions, audit timeline and mock ledger transaction IDs.
- Administrator verification workspace. Per PRD RBAC, exporters submit/register and an
  administrator verifies. Admin reads hide buyer, invoice number, exact value and PDF access.
- New list/detail API query service with ownership checks, sanitized admin projections,
  exact decimal amounts and server-derived action availability. Existing mutation services
  independently enforce all permissions and state transitions.
- Real-browser acceptance tests against temporary API/web servers, PostgreSQL schema and
  private document storage. CI runs the same workflow.

There are no fabricated receivables, completed timeline steps or registry successes. Mock
ledger state remains explicitly labeled. Financing/settlement screens and controls have
not been implemented ahead of their milestones. No database migration was required.

## Files created

Backend:
- `apps/api/app/schemas/receivable_views.py`
- `apps/api/app/services/receivable_queries.py`
- `apps/api/tests/test_receivable_views.py`

Frontend routes:
- `apps/web/app/api/backend/[...path]/route.ts`
- `apps/web/app/login/page.tsx`
- `apps/web/app/receivables/layout.tsx`
- `apps/web/app/receivables/page.tsx`
- `apps/web/app/receivables/new/page.tsx`
- `apps/web/app/receivables/[id]/page.tsx`

Frontend components/libraries:
- `apps/web/components/workspace.tsx`
- `apps/web/components/login.tsx`
- `apps/web/components/dashboard.tsx`
- `apps/web/components/create-receivable.tsx`
- `apps/web/components/receivable-detail.tsx`
- `apps/web/lib/api.ts`
- `apps/web/lib/gateway.ts`

Verification/documentation:
- `apps/web/tests/gateway.test.ts`
- `apps/web/tests/e2e/receivables.spec.ts`
- `apps/web/playwright.config.ts`
- `scripts/test_ui.py`
- `docs/milestone-4.md`

## Files modified

- `apps/api/app/api/routes/receivables.py` — protected list/detail routes.
- `apps/api/app/main.py`, `apps/api/pyproject.toml`, `apps/api/uv.lock` — API 0.5.0 metadata.
- `apps/web/app/page.tsx`, `apps/web/app/globals.css` — workspace entry and responsive styling.
- `apps/web/package.json`, `apps/web/package-lock.json` — Playwright development dependency.
- `apps/web/tests/page.test.tsx`, `apps/web/vitest.config.mts` — component tests and test separation.
- `apps/web/eslint.config.mjs`, `apps/web/.prettierignore`, `.gitignore` — generated test artifacts.
- `docker-compose.yml`, `.env.example` — server-side API origin configuration.
- `Makefile`, `.github/workflows/ci.yml` — browser acceptance target, CI and runner linting.
- `README.md`, `docs/api.md`, `docs/architecture.md`, `docs/threat-model.md` — UI walkthrough,
  read API contracts, session/privacy boundaries, infrastructure and test instructions.

## Commands

```sh
make install
make dev
make seed
# Open http://localhost:3000; use the seeded exporter/admin identities.
make test
make test-integration
make lint
make build
# Once per machine, install the test browser:
cd apps/web && npx playwright install chromium && cd ../..
make test-e2e
```

`make test-e2e` builds the production UI and requires PostgreSQL plus free ports 8001/3001.
It creates/removes only its generated schema and temporary files, preserving developer
receivables. Screenshots go to ignored `apps/web/test-results/`. The runtime API origin
is `API_INTERNAL_URL`; Docker uses `http://api:8000`, host development defaults to
`http://127.0.0.1:8000`. Custom host values must be exported or placed in `apps/web/.env.local`.

## Verification

- 323 API unit tests passed.
- 32 PostgreSQL integration tests passed, including new ownership, sanitization,
  pagination, totals, exact 64-bit values and role/state-specific action tests.
- 14 frontend/gateway tests passed: login, dashboard/filter, upload payload, error handling,
  exact amounts, hashes, unknown registry state, HttpOnly cookie handling, expired sessions,
  origin protection and endpoint allowlisting.
- 2 Chromium acceptance tests passed against the real API/database and production web app.
  Verified create → submit → admin verify → exporter register/open, PDF integrity/download,
  full hashes, persisted history after reload, duplicate rejection, session expiry and
  unsupported roles. Total: **371 passing tests**.
- Desktop dashboard/detail and 390px mobile detail screenshots inspected; no horizontal
  document overflow. The browser test reports no page JavaScript errors.
- Production Next.js build, Ruff checks/format, strict mypy, ESLint, TypeScript and Prettier passed.
- `docker compose up --build --wait` passed; PostgreSQL, API and web are healthy.
- Running-container smoke check passed: API 0.5.0, web login, HttpOnly session cookie,
  authenticated scoped list with no-store, logout and subsequent 401.
- `git diff --check` passed.

Initial browser attempts exposed ambiguous test selectors, which were corrected. The
Chromium installation also had to finish before the first browser launch. Final checks pass.

## Remaining boundaries

MockLedgerClient remains the only working ledger implementation; Drunix operations fail
closed. The prototype does not move funds, issue e-BRC certificates or confer legal ownership.
Verification means an authorized decision plus integrity checks, not commercial verification.
Admin privacy restrictions remain enforced throughout the UI.

Financing is Milestone 5; signed settlement is Milestone 6. No fake controls or fabricated
payment results are supplied. Browser sessions have no refresh-token or revocation system;
logout clears the local cookie. HTTPS/proxy hardening, rate limiting, security-audit expansion
and filesystem/DB crash reconciliation remain the documented later work.

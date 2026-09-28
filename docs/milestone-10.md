# Milestone 10 — Hardening

## Scope

Implemented the final PRD milestone after inspecting the repository and reading the full
PRD. No later features or real bank integrations were added.

- Consistent API and browser-gateway error envelopes, request IDs, safe validation output
  and generic unexpected-error responses.
- JSON request logs with allowlisted request, authenticated actor, organization, asset,
  ledger transaction and verified event context; no raw payloads or exception text.
- Preview-first, explicitly confirmed reset for four fixed mock fixtures. Transactional
  deletion preserves unrelated data, credentials, keys, audit/security evidence and PDFs.
  Drunix mode, real bindings, changed terms and durable recovery inputs fail closed.
- Integration coverage for reset, rollback, preservation, repeatability and refusal;
  browser coverage for correlated gateway/API errors alongside complete demo scenarios.
- Fresh-setup acceptance and CI job covering install, startup, preview, reset, reseeding
  and idempotence in a disposable source copy and isolated Compose project.
- Consolidated setup, operation, architecture, error, demo and boundary documentation.

## Created files

- `apps/api/app/core/logging.py`
- `apps/api/app/cli/__init__.py`, `apps/api/app/cli/reset_demo.py`
- `apps/api/app/services/reset_service.py`
- `apps/api/tests/test_hardening.py`, `apps/api/tests/test_reset.py`
- `apps/web/tests/e2e/errors.spec.ts`
- `scripts/reset_demo.sh`, `scripts/test_setup.py`
- `docs/milestone-10.md`

## Modified files

- API core: `errors.py`, `request_id.py`, `upload_limits.py`, `main.py`.
- API authentication/context: `security/rbac.py`, `services/auth_service.py`,
  `services/audit_service.py`, `services/settlement_service.py`.
- API metadata: `pyproject.toml`, `uv.lock`; regression assertions:
  `tests/test_domain_integration.py`.
- Web: `apps/web/lib/gateway.ts`.
- Configuration/automation: `.env.example`, `docker-compose.yml`, `Makefile`,
  `.github/workflows/ci.yml`.
- Documentation: `README.md`, `docs/api.md`, `docs/architecture.md`,
  `docs/demo-script.md`, `docs/regulatory-boundaries.md`, `docs/threat-model.md`,
  `blockchain/network/README.md`.

## Commands

First setup: `cp .env.example .env`, `make install`, `make demo`.
Existing setup: `make demo`. Open http://localhost:3000.

Preview fixture reset: `make reset`. To intentionally apply it:
`make reset CONFIRM=RESET-DEMO`, then `make demo`.
This leaves stored PDFs as private evidence and is not a general database wipe.

Verification: `make test`, `make test-integration`, `make lint`, `make test-e2e`,
`make test-setup`, `make build-chaincode build-gateway`.

## Validation

- API unit suite: **340 passed**.
- PostgreSQL integration suite: **85 passed**, including reset transaction rollback,
  unrelated-data preservation, reseeding and real-ledger refusal.
- Web unit suite: **20 passed**.
- Production-build Playwright suite: **4 passed**, including error correlation/privacy.
- Chaincode and gateway race/coverage suites passed (80.0% and 47.9% statement coverage).
- Ruff lint/format, mypy (75 source files), ESLint, TypeScript, Prettier, gofmt and go vet passed.
- Next.js production build and both Go binary builds passed.
- Fresh-copy acceptance passed: install, demo, preview without mutation, confirmed reset,
  replacement fixture IDs and idempotent reseeding. Disposable resources were removed.
- Compose configuration, reset shell syntax and `git diff --check` passed.
- Existing demo rebuilt successfully with all services healthy; credentials and existing
  fixture IDs were preserved. No confirmed reset ran against the user's working database.

The first regression run exposed an old whole-response equality assertion that now differs
only by per-request IDs; it was updated to verify identical public authentication errors
and header/body ID correlation. The final integration and browser reruns passed.

## Remaining boundaries

Live Drunix infrastructure was unavailable. Mock mode remains explicitly labeled and real
ledger failures never fall back to fabricated success. Real endorsement, private-data
isolation and network compatibility still require validation on a provisioned network.
No real funds, FX or regulatory certificate issuance is implemented. Production deployment
still requires TLS, rate limiting, custody, external reconciliation and retention policies.
Reset retains PDFs and security/audit evidence, so repeated resets consume storage.

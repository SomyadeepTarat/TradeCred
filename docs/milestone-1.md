# Milestone 1 — Domain and Auth

Implemented after inspecting the Milestone 0 repository and its configuration/tests.
PRD remains unchanged. No later milestone business workflow was implemented.

## Result

- SQLAlchemy organization, user and receivable models, with the full PRD role/status enums.
- Alembic migration 0001: tables, foreign keys, unique constraints, dates, amount/hash checks.
- Argon2id password hashing; HS256 JWTs with required secret, issuer/audience and expiry.
- JSON login, authenticated identity, real admin-only organization listing, reusable RBAC.
- Current database role/active status checked on every authenticated request.
- Transactional, repeatable seed creates six fictional organizations and four demo users.
- Docker applies migrations before starting the API; seeding stays explicit.
- Milestone status page and documentation updated; no frontend login form yet.

Asset IDs, document hashes and fingerprints are nullable for drafts. This milestone
creates schema only; state transitions, fingerprint generation, uploads, financing and
ledger operations are deferred. No ledger success is simulated.

## Created files

```text
apps/api/alembic.ini
apps/api/migrations/env.py
apps/api/migrations/script.py.mako
apps/api/migrations/versions/0001_organizations_users_and_receivables.py
apps/api/app/models/domain.py
apps/api/app/core/errors.py
apps/api/app/api/dependencies.py
apps/api/app/api/routes/auth.py
apps/api/app/api/routes/organizations.py
apps/api/app/repositories/users.py
apps/api/app/schemas/auth.py
apps/api/app/security/passwords.py
apps/api/app/security/tokens.py
apps/api/app/security/rbac.py
apps/api/app/services/auth_service.py
apps/api/app/services/seed_service.py
apps/api/tests/conftest.py
apps/api/tests/test_auth_api.py
apps/api/tests/test_security.py
apps/api/tests/test_domain_integration.py
scripts/seed_demo.py
docs/milestone-1.md
```

## Modified files

```text
.env.example
.github/workflows/ci.yml
Makefile
README.md
docker-compose.yml
apps/api/Dockerfile
apps/api/pyproject.toml
apps/api/uv.lock
apps/api/app/main.py
apps/api/app/core/config.py
apps/api/tests/test_config.py
apps/web/app/page.tsx
apps/web/tests/page.test.tsx
docs/api.md
docs/architecture.md
docs/demo-script.md
docs/threat-model.md
docs/regulatory-boundaries.md
```

A local ignored `.env` was created with a random JWT signing key and local demo password.
No generated signing secret is included in tracked files or this report.

## Commands

First setup only: copy `.env.example` to `.env` and configure credentials; do not overwrite
an existing `.env`. Existing Milestone 0 environments need a JWT_SECRET of at least 32
characters and a DEMO_PASSWORD of at least 12 characters.

```sh
make install
make dev
make seed
make test
make lint
make test-integration
make build
```

For host development: `make db`, `make migrate`, `make seed`, then `make api` and
`make web` in separate terminals. Use `http://localhost:8000/docs` to log in and authorize
with the returned bearer token. See README for all four accounts and the demo password.
`make seed` does not reset existing passwords, roles or active flags.

## Verification

- 37 API unit tests passed: password hashing, JWT validity/expiry/signature/algorithm/
  claims, complete role matrix, anonymous denial, overposting, config and health.
- 14 PostgreSQL integration tests passed: all demo logins, current-role enforcement,
  deactivation, bad credentials, repeatable seed, constraints, migration roundtrip,
  metadata alignment and real database readiness.
- 1 frontend rendering test passed; Next.js production build passed.
- Ruff, formatting, mypy, ESLint, TypeScript and Prettier checks passed.
- Initial migration applied and actual demo identities seeded successfully.
- Docker build/start with migration command succeeded; all three services healthy.
- Live HTTP smoke: all four roles login and identity lookup 200; organizations 200 for
  ADMIN and 403 for other roles; anonymous identity lookup 401. No tokens/passwords logged.
- `git diff --check` passed.

Integration tests create unique temporary PostgreSQL schemas and remove only those
schemas afterward. Downgrade tests never operate on the application's demo schema.

## Remaining issues / limits

No Milestone 1 acceptance blocker remains. Login throttling, security audit events,
password recovery, refresh tokens and individual-token revocation are not implemented;
keep this prototype private. Disabling an account invalidates its access immediately.
The existing Next.js/ESLint 9 support warning remains documented in README. No live
Drunix, ledger, payment, document or receivable lifecycle flow is claimed.

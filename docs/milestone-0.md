# Milestone 0 delivery report

Scope: bootstrap only, per PRD section 48. The PRD was read in full before changes
and remains unchanged. The initial repository contained a one-line README and the PRD.

## Changes

- FastAPI application with lifespan-managed SQLAlchemy/psycopg PostgreSQL engine,
  validated settings, liveness and database readiness endpoints.
- Next.js/TypeScript frontend with explicit bootstrap scope and regulatory boundaries.
- PostgreSQL 16 Compose service; API/web Dockerfiles and health checks.
- Reproducible Python and npm lockfiles; Make targets; GitHub Actions checks.
- API unit tests, real PostgreSQL integration test, frontend rendering test.
- Setup, architecture, API, demo scope, threat model, regulatory documentation.
- Empty directory markers reserve later milestone locations without executable stubs.

Modified: `README.md`.

Created files (excluding this report):

```text
.env.example
.github/workflows/ci.yml
.gitignore
Makefile
apps/api/.dockerignore
apps/api/Dockerfile
apps/api/app/__init__.py
apps/api/app/api/__init__.py
apps/api/app/api/routes/__init__.py
apps/api/app/api/routes/health.py
apps/api/app/core/__init__.py
apps/api/app/core/config.py
apps/api/app/core/database.py
apps/api/app/integrations/__init__.py
apps/api/app/integrations/ledger/__init__.py
apps/api/app/integrations/payments/__init__.py
apps/api/app/integrations/storage/__init__.py
apps/api/app/main.py
apps/api/app/models/__init__.py
apps/api/app/repositories/__init__.py
apps/api/app/schemas/__init__.py
apps/api/app/security/__init__.py
apps/api/app/services/__init__.py
apps/api/pyproject.toml
apps/api/tests/test_config.py
apps/api/tests/test_database.py
apps/api/tests/test_health.py
apps/api/uv.lock
apps/web/.dockerignore
apps/web/.prettierignore
apps/web/Dockerfile
apps/web/app/globals.css
apps/web/app/layout.tsx
apps/web/app/page.tsx
apps/web/components/.gitkeep
apps/web/eslint.config.mjs
apps/web/lib/.gitkeep
apps/web/next-env.d.ts
apps/web/next.config.ts
apps/web/package-lock.json
apps/web/package.json
apps/web/public/.gitkeep
apps/web/scripts/prepare-standalone.mjs
apps/web/tests/page.test.tsx
apps/web/tests/setup.ts
apps/web/tsconfig.json
apps/web/vitest.config.mts
blockchain/chaincode/tradecred/.gitkeep
blockchain/mock-ledger/.gitkeep
blockchain/network/README.md
blockchain/network/config/.gitkeep
blockchain/network/scripts/.gitkeep
docker-compose.yml
docs/api.md
docs/architecture.md
docs/demo-script.md
docs/regulatory-boundaries.md
docs/threat-model.md
scripts/.gitkeep
services/bank-simulator/.gitkeep
tests/e2e/.gitkeep
```

## Run commands

```sh
cp .env.example .env
make install
make dev
make test
make lint
make test-integration
make build
```

For hot reload, use `make db` then `make api` and `make web` in separate terminals.
Stop the stack without deleting data using `docker compose down`.

## Verification

- `make install`: frozen Python install and clean npm install passed.
- `make test`: 5 API unit tests and 1 frontend rendering test passed.
- `make test-integration`: 1 test passed against real PostgreSQL 16.
- `make lint`: Ruff, Python formatting, mypy, ESLint, TypeScript and Prettier passed.
- `make build`: Next.js production/standalone build passed.
- `docker compose config --quiet`: passed.
- `docker compose up --build --wait`: passed; API, web and PostgreSQL all healthy.
- Live HTTP requests to both API health endpoints: 200, including database `ok`.
- Container-served frontend at `http://localhost:3000`: verified in browser.
- Browser smoke check: page loaded and layout inspected.
- npm audit via clean install: zero known vulnerabilities.
- `git diff --check`: passed.

## Remaining scope and tooling note

No later milestone is implemented. MockLedgerClient is Milestone 3; no ledger writes
or fake integration success exist in this milestone. Seed/demo/reset/chaincode targets
fail explicitly until their real implementations arrive.

Next.js's current lint plugins require ESLint 9. Its upstream support warning remains;
ESLint 10 was tested and is incompatible with their current React rules/peer versions.
The compatible locked dependency tree has zero audit advisories.

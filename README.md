# TradeCred

Receivable trust infrastructure for MSME trade finance, targeting NPCI Drunix.
[The PRD](tradecred_prd_codex.md) is the source of truth. **Milestones 0, 1 and 2 are implemented.**

Fragmented institutional records create duplicate-financing and reconciliation risk.
The planned solution combines deterministic fingerprints, a shared registry, financing
locks, agreement hashes and authenticated settlement records. Financing and settlement workflows are not implemented yet. Exporters can now create
drafts by uploading PDFs with deterministic invoice fingerprints and integrity hashes.

## Implemented architecture

```text
Browser --> Next.js :3000 (milestone status page)
API client --> FastAPI :8000 --> PostgreSQL 16 :5432
                  | JWT / Argon2 / role checks
                  | organizations / users / receivable schema
```

Implemented: liveness/readiness, organization/user/receivable/document SQL models, Alembic migrations,
seeded demo identities, JWT login, authenticated identity lookup, admin-only organization
listing, reusable role dependencies, private PDF storage, upload/download/integrity APIs,
tests, linting, CI, and Docker Compose.
No frontend login/upload form or financial workflows exist yet; use Swagger or an API client.

## Setup

Requirements: Node.js 22+, npm, Python 3.12+, uv, Docker with Compose v2.

```sh
cp .env.example .env  # First setup only; preserve an existing .env
make install
make dev
make seed
```

`make dev` starts PostgreSQL, applies migrations before starting the API, and builds the
web service. Seeding is explicit; it never happens during API startup. Open
http://localhost:3000 and http://localhost:8000/docs. `make seed` uses your host Python
installation and the root `.env`; no passwords are printed.

For local hot reload:

```sh
make db
make migrate
make seed
make api
# In another terminal:
make web
```

The root `.env` is loaded regardless of working directory; environment variables take
precedence. `JWT_SECRET` is required and must contain at least 32 characters. The example
signing key and password are local-demo credentials only. Generate a private signing key
before using a shared environment, for example `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`,
and place it in your ignored `.env`. Never commit secrets. JWTs expire in 30 minutes by
default (`JWT_ACCESS_TOKEN_MINUTES`, allowed range 1–60).

`POSTGRES_*` configure Compose. `DATABASE_URL` configures host-side API/migration/seed
commands; use `postgresql+psycopg://`. Compose overrides the API's database host to
`postgres`. Existing volumes retain their original PostgreSQL credentials.
Future Drunix, document, and bank settings remain reserved in `.env.example`.

## Demo identities and authentication

| Email | Role | Organization |
| --- | --- | --- |
| exporter@tradecred.demo | EXPORTER | ORG_EXPORTER_ALPHA |
| bank@tradecred.demo | FINANCIER | ORG_BANK_CITI_DEMO |
| settlement@tradecred.demo | SETTLEMENT_OPERATOR | ORG_SETTLEMENT_BANK |
| admin@tradecred.demo | ADMIN | ORG_CONSORTIUM_ADMIN |

All new demo users receive `DEMO_PASSWORD` (minimum 12 characters); the example value is
`TradeCred-Demo-2026!`. Seed also creates exporter Beta and a second financier organization.
Names are fictional. Rerunning seed creates missing identities but preserves existing
passwords, roles, and active flags. Changing `DEMO_PASSWORD` does not reset existing users.

Use `/docs` to call `POST /api/v1/auth/login` with JSON `email` and `password`, copy the
returned access token into **Authorize**, then call `GET /api/v1/auth/me`.
`GET /api/v1/organizations` returns actual organizations for ADMIN only; other roles
receive 403 and anonymous requests receive 401. No roles supplied by a client are trusted.
See [API documentation](docs/api.md) for examples and security details.

## Migrations, checks, and stopping

```sh
make migrate          # Alembic upgrade head; does not seed users
make seed             # Organizations/users only, no receivables
make test             # API unit tests and frontend render test; no DB required
make test-integration # Real PostgreSQL; creates/drops isolated test schemas
make lint             # Ruff, mypy, ESLint, TypeScript, Prettier
make build
make format
```

Integration tests require a database role with schema-creation permission. They verify
migration upgrade/downgrade/upgrade, metadata alignment, constraints, seed idempotency,
all role logins, role changes, and account deactivation without altering demo tables.
Never run migration downgrades against data you want to keep. Tests only downgrade their
own generated schemas. The migration creates tables and enums; API startup never uses
`create_all`. CI runs tests, checks, migrations, seeding, and the frontend build.

`docker compose down` stops services and retains database data. Published ports bind to
localhost. Both API and web containers run without root. Health endpoints:
`/api/v1/health` (liveness) and `/api/v1/health/ready` (real `SELECT 1`, 503 on failure).

## Boundaries and limitations

- The upload API saves DRAFT receivables with both hashes and no asset ID. It does not
  submit, verify or register on a ledger. Existing unpopulated drafts remain valid.
- `LEDGER_BACKEND=mock` selects the future explicit MockLedgerClient (Milestone 3).
  No ledger transactions are attempted or reported as successful now.
- `LEDGER_BACKEND=drunix` reserves the future gateway configuration. Chaincode is
  Milestone 7 and the gateway is Milestone 8; there is no silent fallback.
- `make demo`, `make reset`, and `make test-chaincode` deliberately exit nonzero until
  their real implementations arrive. No payments or settlements exist yet.
- Authentication has no registration, password-reset, refresh-token, or logout-revocation
  flow. Login rate limiting and security audit logging remain hardening work. Keep the
  development stack private. Deactivated users lose access immediately.
- Next.js's current lint plugins require ESLint 9, which emits an upstream support warning;
  ESLint 10 is incompatible with their current React rules. The locked npm audit is clean.

TradeCred is a prototype, not production-ready or regulator-approved. It does not replace
TReDS, guarantee prevention of off-network fraud, move FX, issue e-BRC certificates, or
make token state a legal assignment. Read [regulatory boundaries](docs/regulatory-boundaries.md).

[Architecture](docs/architecture.md) · [Threat model](docs/threat-model.md) ·
[Milestone 0 report](docs/milestone-0.md) · [Milestone 1 report](docs/milestone-1.md) · [Milestone 2 report](docs/milestone-2.md)

## Uploading and verifying invoices (Milestone 2)

After login in `/docs`, authorize as the exporter and call `POST /api/v1/receivables`
with multipart fields `metadata` (JSON text) and `document` (a PDF). Example metadata:

```json
{"buyerId":"BUYER-DE-001","invoiceNumber":"EXP-2026-1042","invoiceDate":"2026-09-21","currency":"EUR","amount":"10800.00","dueDate":"2026-11-25"}
```

The exporter organization comes from authentication, not the request. A 201 response
contains draft/document IDs, `document_hash`, `invoice_fingerprint`, currency and integer
minor units. Amounts must be decimal **strings**, never JSON floating-point values.
A duplicate canonical invoice returns 409 based on the local database unique constraint;
this is not a consortium registry lookup or a claim of financing eligibility.

Using the returned draft ID, call `/api/v1/receivables/{id}/document/integrity` or download
`/api/v1/receivables/{id}/document`. Both require an exporter in the owning organization.
Admins, financiers, settlement operators and other exporters cannot read raw PDFs.
Downloads verify the hash first and return the unchanged bytes as an attachment.

Host storage uses `DOCUMENT_STORAGE_PATH` (default `./data/documents`, relative to the
repository root). Docker uses `/data/documents` on the persistent `document_data` volume.
Keep database and document storage together: host and Docker modes use different stores;
copy the corresponding document files if switching modes against the same database.
No storage directory is publicly served or written to any ledger.

`MAX_UPLOAD_BYTES` defaults to 10 MiB. Complete request bodies are limited to that plus
64 KiB of multipart overhead, including chunked transfers. Only one PDF and one metadata
field are accepted; metadata is limited to 16 KiB. PDFs must parse strictly, contain
1–100 pages, and be unencrypted. Validation does not establish invoice authenticity or
provide malware scanning, OCR, antivirus, or commercial verification.

Read [TC-FP-1](docs/fingerprinting.md) for normalization and the fixed test vector.
Filesystem writes and PostgreSQL commits cannot be atomic. Handled storage failures
roll back the draft; an uncertain commit returns 503 and retains the file. A crash or
uncertain commit can leave an orphan requiring manual reconciliation; no cleanup job
or idempotent registration workflow is claimed in this milestone.

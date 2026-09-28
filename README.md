# TradeCred

Receivable trust infrastructure for MSME trade finance, targeting NPCI Drunix.
[The PRD](tradecred_prd_codex.md) is the project source of truth. Milestones 0–10 are implemented.

Fragmented institutional records create duplicate-financing and reconciliation risk.
TradeCred combines deterministic invoice fingerprints, a shared registry, financing locks,
agreement hashes and authenticated settlement events. It demonstrates a consortium workflow
from invoice upload to closure, with confidential documents kept off the ledger.

## Architecture and features

```text
Browser → Next.js :3000 → FastAPI :8000 → PostgreSQL :5432
           session cookie    JWT/RBAC        metadata, audits, replay protection
                               ├─ private PDF storage
                               ├─ MockLedgerClient (explicit local simulation)
                               ├─ DrunixLedgerClient → Fabric Gateway → provisioned network
                               └─ sandbox signer :8090 (optional; private key stays here)
```

- Exporter dashboard, PDF upload/integrity checks and canonical business fingerprinting.
- Sanitized financier workspace, competing offers, single acceptance, lock and agreement hash.
- Explicit mock disbursement; no funds move.
- Registry checker for duplicate/financing status across participating organizations.
- Ed25519 settlement validation, timestamp window, amount/currency checks and replay protection.
- Administrator verification, realization, e-BRC eligibility and closure; recorded lifecycle timeline.
- Admin audit/security feeds; consistent errors and redacted JSON request logs.
- Go chaincode, authenticated Fabric Gateway bridge and explicit mock mode without silent fallback.
- API-driven demo fixtures, scoped reset, unit/integration/browser tests and fresh-setup acceptance.

## First setup and working demo

Requirements: Node.js 22+, npm, Python 3.12+, `uv`, Docker Desktop running, Docker Compose
v2.17+ (service build contexts). Go 1.26+ is optional; Go checks use a pinned Docker toolchain
when Go is unavailable locally. Initial installation/build needs network access.

```sh
cp .env.example .env             # First setup only; preserve an existing .env
make install
make demo
```

Open [TradeCred](http://localhost:3000) or [API docs](http://localhost:8000/docs).
`make demo` generates missing signing keys/token, builds API/web/signer, starts PostgreSQL,
applies migrations, seeds users, and creates four demo receivables through authenticated APIs.
No manual database edits are required. Follow [the three demo scenarios](docs/demo-script.md).

The example credentials are **local-demo credentials only**. Set a private `JWT_SECRET`
(minimum 32 characters) and `DEMO_PASSWORD` (minimum 12 characters) before sharing an
installation. Keep `.env`, `data/`, private keys and generated demo files out of Git.
`make keys` preserves existing complete keypairs and creates the internal simulator token
if missing; it never prints private keys or tokens. Incomplete keypairs fail without overwriting.

| Identity | Role | Organization |
| --- | --- | --- |
| exporter@tradecred.demo | EXPORTER | Alpha Looms Demo |
| bank@tradecred.demo | FINANCIER | Cedar Finance Demo |
| nbfc@tradecred.demo | FINANCIER | Maple Credit Demo |
| settlement@tradecred.demo | SETTLEMENT_OPERATOR | Harbor Settlement Demo |
| admin@tradecred.demo | ADMIN | TradeCred Demo Consortium |

New accounts use `DEMO_PASSWORD`; existing passwords, roles and active flags are preserved.
Changing the environment password does not reset accounts. All company/customer data is fictional.

Fixtures: EXP-2026-1042 (flagship, available), DEMO-VERIFIED-01, DEMO-FINANCED-01 and
DEMO-REALIZED-01. Each is EUR 10,800; the mock financing advance is EUR 9,750, with no FX
conversion. Generated PDF/JSON examples and IDs are in `data/demo/`. `make seed-fixtures`
resumes interrupted setup without rewinding advanced records. `make seed` creates users only.

## Configuration and development

The root `.env` is loaded independently of the working directory. Environment variables
have precedence. JWT lifetime defaults to 30 minutes (configurable from 1–60).

- `DATABASE_URL`: host-side PostgreSQL URL (`postgresql+psycopg://`).
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`: Compose database credentials.
  The API container always uses the Compose database; existing volumes retain their credentials.
- `LEDGER_BACKEND=mock`: explicit PostgreSQL simulation with `MOCK-` transaction IDs.
- `SIMULATOR_ENABLED=false`: default. `make demo` enables the optional signer for its
  Compose invocation; ordinary `make dev` leaves the simulator API disabled unless explicitly enabled.
- `DOCUMENT_STORAGE_PATH`: host PDF directory; Docker uses a private named volume.
- `BANK_TRUSTED_KEYS`: public-key registry for host API. Docker mounts the demo public key only.
- `POSTGRES_PORT`, `API_PORT`, `WEB_PORT`, `SIMULATOR_PORT`: optional loopback port overrides.
  When changing ports, update host `DATABASE_URL` and `DEMO_API_URL` consistently.

For hot reload:

```sh
make db
make migrate
make seed
make api                       # Terminal 1, localhost:8000
make web                       # Terminal 2, localhost:3000
```

For the browser settlement simulator, use `make demo`, or follow the
[signer service guide](services/bank-simulator/README.md) for host configuration.
For signed command-line events:

```sh
make bank-event ARGS="--asset-id TC-REPLACE --amount-minor 1080000 --currency EUR --reference IRM-DEMO-938291 --save data/payment-event.json"
make bank-event ARGS="--replay data/payment-event.json"
```

Use a FINANCED asset and replace TC-REPLACE with its actual ID. Replay of a consumed event
is rejected; after five minutes it may be rejected as stale instead.

## Drunix mode

Set `LEDGER_BACKEND=drunix` only after configuring a compatible provisioned network,
identities, TLS roots and the authenticated gateway. See [network setup](blockchain/network/README.md)
and [chaincode requirements](blockchain/chaincode/tradecred/README.md).

The official Fabric SDK waits for VALID commit. Missing configuration, unavailable peers
or unconfirmed outcomes fail closed; they never manufacture success or switch to mock.
Durable private inputs and chaincode receipts allow exact-operation retries after lost
responses or local projection failures. Assets remain bound to their original backend/network.
Explicit fallback is `LEDGER_BACKEND=mock` with fresh assets; it does not migrate real assets.
Live Drunix compatibility/endorsement/private-data behavior remains unverified without infrastructure.

## Reset and repeat the demo

```sh
make reset                     # Read-only preview of the four named fixture targets
make reset CONFIRM=RESET-DEMO   # Apply the scoped reset and leave API stopped
make demo                      # Restart and rebuild fixtures through the APIs
```

Reset removes only the four named Alpha mock fixtures and their offers, agreements,
mock payouts, payment records and mock ledger rows. It verifies fixed invoice terms and
refuses Drunix mode, real-ledger bindings or any durable Drunix recovery inputs in the database.
Conflicting data causes the transaction to roll back. Stop host API processes before using
reset; the script stops the Compose API after its read-only preflight.

Accounts, passwords, unrelated receivables, signing keys, security events, signed simulator
attempts and audit evidence are retained. Old audit detail links are retired. Stored PDFs
are retained as private evidence rather than risking file deletion after an ambiguous commit;
repeated resets consume some document storage. Reset is not a production data-retention tool
and never alters a real network. It does not run automatically during startup or deployment.

## Tests and acceptance

```sh
make test                      # API/web units and both Go race suites
make test-integration          # Isolated PostgreSQL schemas; running local DB required
make lint                      # Ruff, mypy, ESLint, TypeScript, Prettier, gofmt, vet
make test-e2e                  # Production web build + isolated browser demo scenarios
make test-setup                # Fresh copy → install → demo → preview/reset → reseed
make build-chaincode build-gateway
```

Browser tests use dedicated ports 8001, 3001 and 8091, temporary PDFs/keys and an isolated
schema. Fresh-setup acceptance uses a temporary source copy, generated secrets, random
loopback ports and a unique Docker Compose project. Its cleanup removes only its own
containers/volumes; your existing stack and data are untouched. CI runs both the regular
suites and fresh demo acceptance. No test doubles are used in production integrations.

API startup applies Alembic migrations in Compose; host execution uses `make migrate`.
No startup `create_all` shortcut exists. Integration tests check migration round trips and
metadata alignment. Stop services while retaining volumes with:

```sh
docker compose --profile demo down
```

## Errors, logs and troubleshooting

Every API error has `error.code`, `message`, `details`, `requestId`, and an `X-Request-ID`
header. Validation responses never echo raw inputs. Unexpected failures return a generic
500. Logs use JSON with server-generated request IDs, route templates, status and duration,
plus authenticated user/org and asset/transaction/event references when known. They exclude
JWTs, passwords, signatures, request bodies, document contents and raw exception/SQL text.
Ledger references in completion logs describe the attempted request; persisted audit/ledger
records establish committed business outcomes. Uvicorn raw access logging is disabled in
the documented API commands so query parameters are not logged.

- Docker paused/unavailable: resume Docker Desktop, then rerun the command.
- Login fails after changing DEMO_PASSWORD: existing passwords are intentionally preserved.
- Signature verification/signing fails: check `make keys`, trusted public registry and signer
  configuration; never replace existing private keys merely to clear an error.
- Port in use: stop the conflicting service or configure the documented port overrides.
- Unknown ledger result: restore availability and repeat the exact action/event. Do not
  create a replacement operation. Simulator replay uses the last event in the open page.
- Readiness: `/api/v1/health` is liveness; `/api/v1/health/ready` performs a real database query.
  Database readiness does not prove gateway connectivity.

## Boundaries and documentation

TradeCred is a prototype, not production-ready or regulator-approved. It does not replace
TReDS, prevent off-network fraud, move FX, issue e-BRC certificates, or make token state a
legal assignment. AD banks/remittance providers remain regulated intermediaries. e-BRC
eligibility is SELF_CERTIFICATION_PENDING, not issuance. Real bank/TReDS/DGFT/RBI/NPCI
production integrations, HSM custody and live-network certification remain outside scope.
Login rate limiting, password recovery and token revocation remain production hardening work.

[Architecture](docs/architecture.md) · [API](docs/api.md) · [Demo](docs/demo-script.md) ·
[Threat model](docs/threat-model.md) · [Regulatory boundaries](docs/regulatory-boundaries.md) ·
[Milestone 10 report](docs/milestone-10.md)

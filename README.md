# TradeCred

Receivable trust infrastructure for MSME trade finance, targeting NPCI Drunix.
[The PRD](tradecred_prd_codex.md) is the source of truth. **Only Milestone 0 is implemented.**

Fragmented institutional records create duplicate-financing and reconciliation risk.
The planned solution is a permissioned registry with deterministic invoice fingerprints,
financing locks, agreement hashes, and authenticated settlement confirmation.
These business flows are not available in this bootstrap.

## Implemented architecture

```text
Browser --> Next.js :3000
Health client --> FastAPI :8000 --> PostgreSQL 16 :5432
```

The frontend currently displays project scope; it does not query the API or report
runtime database/ledger status. Future ledger and bank integrations are described in
[architecture](docs/architecture.md), not simulated by this milestone.

## Requirements and setup

- Node.js 22+, npm
- Python 3.12+, uv (lock generated with uv 0.7.22)
- Docker Desktop / Docker Engine with Compose v2

```sh
cp .env.example .env
make install
make dev
```

`make dev` builds and starts PostgreSQL, API, and web containers and waits for their
health checks. Open http://localhost:3000 and http://localhost:8000/docs.
Compose uses named persistent database storage and binds ports to localhost.
No bank simulator is started: its implementation belongs to Milestone 6.

For local hot reload, start PostgreSQL and run the API and web in separate terminals:

```sh
make db
make api
# Another terminal:
make web
```

The API reads the root `.env` regardless of the working directory; process environment
variables override it. The web needs no environment variables yet. `.env.example`
contains the future integration settings required by the PRD; only `DATABASE_URL`
and `LEDGER_BACKEND` are parsed by the bootstrap API. `POSTGRES_*` configure Compose.
Use a `postgresql+psycopg://` database URL. If changing database credentials, update
both the URL and `POSTGRES_*`; existing database volumes retain their original credentials.
Never commit secrets. The sample database password is for local development only.

## Health and verification

```sh
curl --fail http://localhost:8000/api/v1/health
curl --fail http://localhost:8000/api/v1/health/ready
make test
make lint
make test-integration  # Requires make db; queries real PostgreSQL
make build
```

`/health` reports process liveness. `/health/ready` executes `SELECT 1` and returns
503 when PostgreSQL is unavailable, without exposing connection details.
`make test` runs API unit tests and frontend rendering tests without infrastructure.
The separate integration test is mandatory for Milestone 0 acceptance; CI runs both.
`make format` applies Python and frontend formatting. Dependency locks are included;
`make install` uses frozen/clean installs. CI also validates Compose and builds Next.js.

Stop containers with `docker compose down`. This retains database data. A fresh build
can be launched again with `make dev`.

## Milestone boundaries

- **Demo roles / authentication:** EXPORTER, FINANCIER, SETTLEMENT_OPERATOR, ADMIN
  are planned; no login or demo accounts exist yet (Milestone 1).
- **Migrations / seed:** application tables and Alembic begin in Milestone 1.
  Bootstrap PostgreSQL contains no domain tables. `make seed` deliberately exits
  nonzero until a real seed implementation exists.
- **Mock ledger:** `LEDGER_BACKEND=mock` reserves the explicit configuration choice.
  `LedgerClient` and `MockLedgerClient` arrive in Milestone 3. No ledger transactions
  are attempted or reported as successful now.
- **Drunix:** `LEDGER_BACKEND=drunix` is a recognized future configuration value,
  not a connection. Chaincode is Milestone 7, gateway is Milestone 8. There is no
  silent fallback and no live Drunix integration in this milestone.
- **Demo / reset / chaincode:** `make demo`, `make reset`, and `make test-chaincode`
  exit nonzero with the scope explanation. See [demo script](docs/demo-script.md).
- **Limitations:** no receivable, financing, document, settlement, ledger, or auth flows
  have been implemented. Do not expose this development stack publicly.

## Regulatory boundary

TradeCred is a prototype, not production-ready or regulator-approved. It does not
replace TReDS, guarantee prevention of off-network fraud, move foreign currency,
issue e-BRC certificates, or make a token a legal assignment. Actual remittance stays
with regulated banking channels. Read [regulatory boundaries](docs/regulatory-boundaries.md).

## Repository

- `apps/api`: FastAPI, configuration, PostgreSQL connectivity, API tests.
- `apps/web`: Next.js App Router, TypeScript, linting, rendering tests.
- `blockchain`, `services/bank-simulator`, `scripts`, `tests/e2e`: reserved locations
  for subsequent milestones; no executable integration stubs.
- `docs`: architecture, API, milestone walkthrough, threat model, regulatory boundaries.

The current Next.js lint plugins require ESLint 9; npm reports its upstream end-of-support warning. ESLint 10 currently conflicts with their peer requirements. The locked dependency audit has no known vulnerabilities.

# Milestone 7 — Drunix Chaincode

Implemented after reading the full PRD and inspecting the repository. Existing Milestone 6
changes were preserved. Milestone 8 gateway/network work has not been started.

## Delivered

- Executable Go TradeCredContract using the official Fabric contract API, with all 15
  PRD methods: verification, registration, reads, fingerprint lookup, opening, locking,
  financing, release, payment confirmation, realization, e-BRC eligibility, closure,
  disputes, overdue marking and history.
- Sanitized world state and immutable fingerprint reservation. A verifier attests VERIFIED
  before exporter registration. Matching registration/acceptance retries retain original
  transaction IDs and never rewind state; conflicting retries and payment replay fail.
- Central state matrix, with CLOSED and the PRD's other states without outgoing edges
  treated as terminal. Method-specific MSP, role and ownership checks apply independently.
- Settlement-service certificate attribute requirement, expected private invoice value/
  currency validation and global payment-event uniqueness. No signature-check bypass is
  exposed to general settlement users or administrators.
- Transient-only sensitive inputs, salted invoice/payment commitments, exporter implicit
  private storage and four isolated exporter/financier collections. The selected pair gets
  the agreement and invoice; other banks do not become private-collection members.
- Deterministic proposal timestamps and integer currency arithmetic. Cross-language tests
  detect drift from Python's lifecycle matrix and ISO-4217 exponents.
- Native Go or pinned Docker toolchain runner, executable build, race tests, coverage,
  formatting/vet targets and CI integration. No network is started and no gateway is faked.

## Files created

- apps/api/tests/test_chaincode_contract.py
- blockchain/chaincode/tradecred/README.md
- blockchain/chaincode/tradecred/collections_config.json
- blockchain/chaincode/tradecred/contract.go
- blockchain/chaincode/tradecred/contract_test.go
- blockchain/chaincode/tradecred/currency_exponents.json
- blockchain/chaincode/tradecred/go.mod
- blockchain/chaincode/tradecred/go.sum
- blockchain/chaincode/tradecred/main.go
- blockchain/chaincode/tradecred/models.go
- blockchain/chaincode/tradecred/state_transitions.json
- blockchain/chaincode/tradecred/validation.go
- scripts/chaincode.sh
- docs/milestone-7.md

## Files modified

- .github/workflows/ci.yml — pinned Go setup and executable build; existing test/lint steps
  now include chaincode.
- .gitignore — generated chaincode build directory.
- Makefile — working chaincode test/lint/format/build targets and aggregate integration.
- README.md — scope, commands and milestone report link.
- blockchain/network/README.md — separates implemented contract from pending network/gateway.
- docs/architecture.md and docs/threat-model.md — identity, privacy and trust boundaries.

The existing application API/runtime and database schema were not changed in this milestone.
The generated ignored build/tradecred executable is a local build artifact.

## Commands

```sh
make test-chaincode
make lint-chaincode
make build-chaincode
make format-chaincode
make test
make test-integration
make lint
make test-e2e
```

Use local Go 1.26+ or running Docker Desktop. When Go is absent, the runner uses a
content-addressed Go 1.26.8 container and persistent named caches; the first run downloads
dependencies. Locked module metadata is checked in. make test and make lint include the
chaincode; make build-chaincode creates the ignored executable. There is no Drunix startup
or chaincode deployment command in Milestone 7.

## Verification

- 12 Go top-level tests, including 51 named subtests and all 225 state-pair assertions,
  passed with race detection. Statement coverage: **84.0%**.
- Contract construction and real Fabric contract-API dispatch tested; internal transition
  helpers are not invocable as public transactions.
- Tested full verification-to-closure lifecycle, sanitized history, duplicate fingerprints,
  same-asset conflicts, retry behavior, lock ownership, second-bank rejection, missing/
  spoofed attributes, settlement-service gating, amount/currency/proof mismatch, payment
  replay across assets, release/dispute/overdue behavior and terminal CLOSED state.
- Input tests cover malformed identifiers/hashes/currencies/dates, private amounts/salts,
  unknown/duplicate fields, trailing/oversized/missing JSON, expired offers, agreement
  mismatch, future acceptance times, invalid tenor/rate and unknown financiers.
- Storage failure injection verifies that failures propagate and the harness rolls back
  simulated writes. Collection policies are checked against the exact participant pairs.
- **428 application tests passed:** 331 API unit (including two new parity checks),
  74 PostgreSQL integration, 20 frontend/gateway and 3 Chromium acceptance tests.
- gofmt, go vet, Ruff lint/format, strict mypy, ESLint, TypeScript and Prettier passed.
- Chaincode executable and production Next.js builds passed.
- Working-tree whitespace check passed.

An initial matrix comparison detected only ordering differences in the set of permitted
FINANCED successors; the representation was aligned and all final checks pass.

## Remaining boundaries

No outstanding Milestone 7 contract test failures. Tests use an explicit in-memory Fabric
stub; they do not prove real endorsement, ordering, MVCC commit behavior, private-data
availability/gossip or Drunix compatibility. The pinned SDK and demo MSP/collection profile
must be validated against the provided Drunix network in Milestone 8.

The future gateway must provision certified attributes, restrict transient proposal recipients,
preserve original salted private bytes, supply private inputs, and verify transaction commit
status. Proposal endorsement alone is not transaction success. Existing FastAPI routes still
use explicit MockLedgerClient; Drunix configuration returns 503 without fallback.

Chaincode realization/eligibility/closure methods do not add application orchestration or UI
controls. Settlement remains PAYMENT_CONFIRMED in the running app. e-BRC is never issued,
no funds move and token state does not confer legal ownership. Compromised trusted CAs,
verifiers or settlement backend identities remain explicit trust risks.

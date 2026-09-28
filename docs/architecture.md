# Architecture and implementation status

Milestones 0–10 provide Next.js, FastAPI and PostgreSQL 16. The frontend provides
exporter, financier, settlement and administrator workspaces.

FastAPI creates an async SQLAlchemy engine during lifespan and disposes it on shutdown.
Requests receive scoped sessions. Routes delegate authentication to AuthService and user
queries to UserRepository. Reusable role dependencies return 401/403 before protected
resource queries. Argon2 work runs in a worker thread; JWT subjects identify users whose
current role, organization and active flag are read from the database on every request.

Alembic migration 0001 creates organizations, users and receivables, PostgreSQL enums,
foreign keys, canonical-email/unique constraints, positive amounts, dates and hash checks.
Asset IDs and hashes are nullable for drafts. A shared Python transition matrix enforces
the PRD lifecycle, with row locks around mutations.
The upload service validates ISO-4217 codes and exact currency minor units.

Compose applies migrations before API startup. Seed runs separately in one transaction
under a PostgreSQL advisory lock; it preserves existing user credentials and roles.
Six fictional organizations include the PRD's five participant IDs and a separate
consortium administration organization. Five users cover all four roles, including two financing institutions.

PostgreSQL persists in a named volume. API/web containers run without root and published
ports are loopback-only. JWT secrets come from configuration, never generated per worker.

Milestone 3 adds LedgerClient and a PostgreSQL-backed MockLedgerClient. Milestone 8 adds DrunixLedgerClient and an authenticated official Fabric Gateway SDK bridge.
Signed bank event ingestion is implemented. Drunix requires configured identities and a
compatible provisioned network; unavailable or unconfirmed operations return 503 without fallback.


Milestone 2 adds multipart upload -> canonical identity / PDF validation -> DRAFT and
Document metadata in PostgreSQL -> private filesystem bytes -> confirmed DB commit.
Document storage is behind a typed DocumentStorage protocol. Object keys are generated
UUIDs; caller filenames are never paths. Files are created exclusively with mode 0600,
symlinks are not followed, and handled partial writes are removed. FastAPI's scoped
multipart context closes uploaded temporary files, including rejected requests.

Ownership is checked through the receivable before storage reads. Downloads rehash the
same bounded bytes they return (no separate unchecked file streaming). The local unique
fingerprint constraint handles concurrent duplicates; no ledger lookup is performed.
The document_data Docker volume persists across container recreation.

Storage and DB are not one atomic system. Flush/constraint failure writes no file;
handled storage failure rolls back the DB transaction. Uncertain commit preserves bytes
and returns an error, allowing manual reconciliation instead of deleting possibly
referenced data. Process crashes can leave orphans. This milestone has no cleanup worker.


Milestone 3 adds migration 0003: mock_ledger_assets, mock_ledger_private,
ledger_transactions and audit_events. The global DTO omits exact invoice values; private
values are stored separately to validate internal payment operations. This is application
separation within the same PostgreSQL database, not cryptographic or consortium isolation.

The caller owns the unit of work. MockLedgerClient flushes but never commits. LedgerService
commits ledger changes, the receivable projection and audit event together before returning
a receipt. Database/ledger failure rolls back and never reports success. A lost commit
acknowledgement can still mean the transaction committed; retry registration with the same
receivable ID to reconcile it. Stable asset IDs and immutable registration inputs make that
retry idempotent even after the asset advances.

Registration acquires transaction-scoped advisory locks on asset ID and fingerprint, backed
by unique constraints. Lifecycle changes use SELECT FOR UPDATE. Internal payment IDs are
serialized and unique to reject replay. History is ordered by asset revision. Production
chaincode independently enforces the same state matrix in Milestone 7.

Audits include generated request IDs (also returned as X-Request-ID), actors, action,
receivable/asset references and allowlisted metadata. Invoice upload, lifecycle changes,
registry checks and duplicate rejections are recorded. Successful changes share their
transaction with their audit; rejected duplicates are recorded after rollback. Existing
pre-Milestone-3 records are not backfilled with invented history.
Application routes do not expose audit updates or deletes;
a database administrator can still alter the mock tables.


Milestone 4 adds paginated, organization-scoped query services without changing the database
schema. The API owns amount formatting, summary aggregation and role/state-aware action
availability. Exact private values remain available only to the owning exporter. Existing
mutation services remain the authority for transitions.

The browser uses a same-origin Next.js route handler. A narrow route allowlist forwards
requests to runtime API_INTERNAL_URL. An HttpOnly, SameSite=Strict cookie holds the JWT;
browser code receives no bearer token. Mutation origins are checked, upstream errors keep
their status, expired tokens clear the cookie and all gateway responses disable caching.
Multipart bytes retain their original content type/boundary; request bodies are bounded at
50 MiB plus 64 KiB before forwarding, and the API enforces its configured PDF limit.

The interface fetches persisted data, refreshes after successful actions, and represents
loading, empty, unauthorized and unavailable states explicitly. History entries come from
audit records/ledger revisions, not inferred completion of a preset timeline. Browser
acceptance tests run against real temporary API, PostgreSQL and production Next.js servers.


Milestone 5 introduces financing_offers, financing_agreements and mock_disbursements via
migration 0004. FinancingService always locks the receivable before reading/mutating
its offers, serializing acceptance, rejection, offer creation and disbursement. A partial
unique index independently permits only one ACCEPTED offer per receivable. Agreements
and mock payouts are unique per receivable/agreement. LedgerClient remains authoritative
for lock/state transitions; registry state is compared with the application projection.

Acceptance hashes sorted compact UTF-8 TC-AGR-1 JSON and stores the private payload off
ledger. Before payout, payload, hash, offer terms, owner and ledger projection are checked.
The PaymentAdapter protocol is implemented by MockNPCIPaymentAdapter, which persists a
simulation receipt without external requests. It shares the transaction with MockLedgerClient;
external payment integrations would require a separate reconciliation design in a future scope.

The frontend adds a sanitized financier register and private offers panel to existing
detail views. It shows acceptance terms before confirmation and labels every payout as
sandbox simulation. The gateway allowlist includes only the added financing routes.

## Settlement authentication and atomicity (Milestone 6)

The CLI bank simulator holds an Ed25519 private key. The API receives only public keys
through a registry binding each key ID to a bank ID and settlement organization. A valid
signature authorizes only this bank's payment event. The organization must have an active
settlement operator. Receipt reads still require JWT and organization authorization.

The signature covers a protocol prefix and exact request bytes. Advisory transaction locks
serialize event IDs/nonces across all assets. The service then locks the receivable,
checks the ledger projection and calls MockLedgerClient.confirm_payment, which independently
checks state, private invoice value, currency, role and event uniqueness. Database unique
constraints backstop the locks. Receipt, private settlement reference, ledger history,
projection and success audit commit together. Failure rolls back; a separate transaction
records sanitized rejection. Storage/audit failure returns 503, never success.

No private key is mounted in the API. Raw payment payloads are not persisted: payment_events
stores their digest and receipt metadata; security_events stores rejections without trusting
claimed actor/asset IDs. The security dashboard is Milestone 9. Public deployment requires
later TLS, rate limits and retention controls; this prototype binds to loopback.

## Go chaincode (Milestone 7)

TradeCredContract now implements the PRD functions using the official Fabric Go contract
API. It independently enforces MSP/role attributes, verifier attestation, fingerprint
reservation, owner-only financing, state transitions and settlement-service authority.
Private amounts enter via transient data and are committed in an exporter implicit
collection, then copied into an isolated exporter/winning-bank collection at lock. Salted
hash checks let authorized settlement endorsers validate expected amounts without public
plaintext values. History/events contain sanitized asset state only.

All timestamps come from proposals, all value arithmetic uses integers, and all endorsers
use the same checked-in participant/collection profile. Tests check parity with Python's
state matrix and currency units. Endorsement, actual MSP enrollment and Fabric MVCC commit
behavior still need real-network verification. Application routes select their ledger by
environment; automatic realization/closure has not been added.

See [contract interface and deployment requirements](../blockchain/chaincode/tradecred/README.md).

## Gateway durability (Milestone 8)

The Go sidecar waits for VALID commit through the official SDK. `Execute` atomically
stores a request hash and sanitized receipt with the chaincode mutation. PostgreSQL
`ledger_artifacts` separately commits stable private inputs before submission so retries
survive local projection rollback. Exact receipt/current-state matching permits recovery;
changed requests fail. Existing assets bind to backend/network and cannot silently move
between mock and Drunix. See [network guide](../blockchain/network/README.md).

## Demo screens and sandbox signing (Milestone 9)

The browser gateway exposes authenticated registry checking, admin audit and settlement
simulator routes. A separate local signer holds the sandbox private key; the API retains
only its public verifier registry and internal signer token. Exact signed events are stored
in `simulator_events` for replay, scoped to their submitting user. Simulator execution uses
SettlementService, so all existing signature, timestamp, replay and ledger checks apply.
Administrator review exposes the final three existing ledger transitions. Seed fixtures
run through public application APIs, generating genuine mock ledger history, agreements,
disbursement records and signature-verified settlement rather than editing status columns.

## Hardening (Milestone 10)

ASGI middleware generates request IDs, normalizes unexpected failures and emits JSON
completion logs with route templates and allowlisted context. Authentication, audits and
verified settlement processing bind known actor/asset/transaction/event IDs. Exceptions,
query strings and input values are excluded. Logs describe requests; committed database
audits remain the business outcome record. Next.js generates equivalent errors for local
proxy failures and preserves upstream error request IDs.

The reset CLI previews four named fixtures by default. Explicit confirmation stops the
Compose API and removes only matching mock fixtures in a locked database transaction.
It refuses real-ledger bindings/recovery inputs and retains accounts, private files and
audit/security evidence. Fresh-setup acceptance exercises install, startup, preview, reset
and idempotent API reseeding in a disposable Compose project, independently of unit,
PostgreSQL integration and production-build browser suites.

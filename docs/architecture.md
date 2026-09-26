# Architecture and implementation status

Milestones 0–4 provide Next.js, FastAPI and PostgreSQL 16. The frontend provides an
exporter workspace and a sanitized administrator verification view.

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
consortium administration organization. Four users cover all four roles.

PostgreSQL persists in a named volume. API/web containers run without root and published
ports are loopback-only. JWT secrets come from configuration, never generated per worker.

Milestone 3 adds LedgerClient and a PostgreSQL-backed MockLedgerClient. DrunixLedgerClient,
Fabric private collections and authenticated external settlement events remain future work.
Selecting Drunix returns 503 for ledger operations, without a mock fallback.


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
chaincode must independently enforce these same rules in its later milestone.

Audits include generated request IDs (also returned as X-Request-ID), actors, action,
receivable/asset references and allowlisted metadata. Invoice upload, lifecycle changes,
registry checks and duplicate rejections are recorded. Successful changes share their
transaction with their audit; rejected duplicates are recorded after rollback. Existing
pre-Milestone-3 records are not backfilled with invented history. Authentication/security
hardening remains future work. Application routes do not expose audit updates or deletes;
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

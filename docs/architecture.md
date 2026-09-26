# Architecture and implementation status

Milestones 0, 1 and 2 provide Next.js, FastAPI and PostgreSQL 16. The frontend displays
milestone scope; authentication is currently available through the API and Swagger UI.

FastAPI creates an async SQLAlchemy engine during lifespan and disposes it on shutdown.
Requests receive scoped sessions. Routes delegate authentication to AuthService and user
queries to UserRepository. Reusable role dependencies return 401/403 before protected
resource queries. Argon2 work runs in a worker thread; JWT subjects identify users whose
current role, organization and active flag are read from the database on every request.

Alembic migration 0001 creates organizations, users and receivables, PostgreSQL enums,
foreign keys, canonical-email/unique constraints, positive amounts, dates and hash checks.
Asset IDs and hashes are nullable for drafts. SQL constraints do not yet implement a
lifecycle transition matrix: only draft creation exists in this milestone.
The upload service validates ISO-4217 codes and exact currency minor units.

Compose applies migrations before API startup. Seed runs separately in one transaction
under a PostgreSQL advisory lock; it preserves existing user credentials and roles.
Six fictional organizations include the PRD's five participant IDs and a separate
consortium administration organization. Four users cover all four roles.

PostgreSQL persists in a named volume. API/web containers run without root and published
ports are loopback-only. JWT secrets come from configuration, never generated per worker.

Future milestones add the explicit MockLedgerClient and DrunixLedgerClient,
private ledger collections and sanitized global state,
and authenticated external settlement events. No ledger writes or fallback behavior are
implemented here. Reserved directories are not executable integration stubs.


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

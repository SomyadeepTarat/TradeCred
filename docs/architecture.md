# Architecture and implementation status

Milestone 0 provides independent Next.js and FastAPI services plus PostgreSQL 16.
The API creates its async SQLAlchemy engine during application lifespan and disposes
it on shutdown. The readiness endpoint performs a database query. Liveness remains
available during database outages. No domain data or ledger writes exist yet.

Next.js renders a static bootstrap page. It does not claim a successful API, payment,
or ledger connection. Docker containers run API and web under unprivileged users.
PostgreSQL persists in a named volume. Published ports are loopback-only.

The PRD's future architecture adds application metadata in PostgreSQL, off-chain PDF
storage, a LedgerClient abstraction (MockLedgerClient then DrunixLedgerClient), private
commercial data, sanitized global state, and authenticated external payment events.
The API must never pretend a ledger write succeeded or silently switch backend.
Business logic belongs in services, not routes. Implement these in milestone order.

Reserved directories are intentionally empty; they are not fake implementations.

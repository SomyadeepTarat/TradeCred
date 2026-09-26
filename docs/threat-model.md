# Threat model

Milestones 0–4 provide authentication, document integrity, mock ledger state enforcement
and the receivables UI. The controls below distinguish implemented behavior from future protections.

| Threat | Required mitigation and implementation milestone |
| --- | --- |
| Duplicate financing | Implemented deterministic fingerprint and local uniqueness (2); consortium registry and state validation (3), exclusive financing lock (5). Off-network institutions remain a residual risk. |
| Document modification | Implemented off-chain SHA-256 verification and download rejection on mismatch (2). |
| Fake settlement | Asymmetric signatures, trusted public-key registry, amount/currency validation (6). |
| Replay | Unique event ID and nonce, timestamp TTL (6). |
| Unauthorized transition | Implemented database-backed RBAC (1), centralized transition matrix (3), chaincode authorization (7). |
| Sensitive data leakage | Implemented owner-only raw document access and private off-chain storage (2); sanitized ledger state (3), private data collections (7). |
| Ledger unavailable | No false success; explicit mock abstraction (3), idempotency/transaction tracking, retry and gateway errors (8–10). |

Current controls: localhost-only Compose ports, ignored environment files, non-root
API/web containers, readiness failure without credential disclosure, and real database
connectivity tests. JWT authentication and admin-only organization access are implemented. Authenticated users are reloaded from PostgreSQL so disabled accounts and removed roles cannot retain access. Login throttling, security audit logging, password recovery and token revocation beyond account deactivation are not implemented yet. Local
sample database credentials are not production credentials. Do not expose this stack
as a production service. Future logs must exclude tokens, keys, accounts and document bytes.


Uploads have total request and file limits, one-file/one-field limits, strict PDF parsing,
and unencrypted/page-count requirements. Filename/path traversal is avoided using UUID
keys; storage rejects arbitrary keys and symlinks. These controls are not malware scanning
or a sandboxed PDF parser. Host/storage administrators can still read local bytes; at-rest
encryption and hardened parser isolation are not implemented. Filesystem/DB crash windows
can leave orphan files requiring reconciliation; uncertain commits never report success.


## Browser session boundary (Milestone 4)

JWTs are held in HttpOnly, SameSite=Strict cookies by the same-origin Next.js gateway.
Cookie-authenticated POSTs require a matching Origin/Host and only an explicit endpoint
allowlist is proxied. Browser-supplied Authorization headers are ignored. Server responses
for private data disable caching; PDF integrity failures retain their non-success status.
Cookies become Secure for HTTPS requests. Local development binds to loopback; production
TLS/proxy policy, CSP hardening, rate limiting and session revocation remain future work.
Role/organization checks happen at FastAPI on every request. Client-visible action hints
are not authorization. UI reads omit private fields for admins and reject non-owner exporters.

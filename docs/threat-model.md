# Threat model

Milestones 0–10 provide authentication, document integrity, mock ledger state enforcement
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
connectivity tests. JWT authentication and admin-only organization access are implemented. Authenticated users are reloaded from PostgreSQL so disabled accounts and removed roles cannot retain access. Login throttling, broader security audit logging, password recovery and token revocation beyond account deactivation are not implemented yet. Local
sample database credentials are not production credentials. Do not expose this stack
as a production service. Request logs exclude tokens, keys, bank accounts and document bytes.


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


## Financing controls (Milestone 5)

Receivable row locks serialize competing acceptances and payouts. Database constraints
backstop single acceptance/agreement/disbursement. Only the exporter can accept; only the
winning institution can simulate payout. Registry state is checked before financial mutations;
failed ledger or payment operations roll back together. Agreement payload hashes and
recorded terms are revalidated before payout. Replays return existing receipts.

Offer terms are filtered by institution; only the owner exporter can compare all offers.
Financier history omits private application audit records, and raw PDF access stays exporter-only.
Duplicate financing attempts on visible locked/financed assets are audited after rollback.
These are local simulation guarantees, not real payment finality, legal assignment or
prevention of off-network fraud. Signed buyer-settlement validation is implemented in Milestone 6.

## Settlement controls (Milestone 6)

Implemented Ed25519 verification over domain-separated exact bytes, explicit trusted
key/bank/organization mapping, active identity checks, strict schema, bounded body,
timestamp freshness, nonce/event uniqueness, full-invoice amount/currency matching and
FINANCED-only transitions. JWTs cannot substitute for bank signatures. Database locks
serialize concurrent replays; rejected attempts leave financial state unchanged.

Receipt reads are scoped to exporter, assigned financier, submitting bank or admin and
omit private payment fields. Rejections record only a digest, request ID, server-selected
reason/type and timestamp. Missing keys fail closed. API containers mount public keys
only; ignored simulator private keys use mode 0600.

Residual risks: a compromised trusted signer can falsely attest payment; signatures prove
source, not actual settlement. Host/database admins remain trusted. No HSM, automatic key
rotation, webhook rate limiting, external reconciliation, retention policy or production
TLS is supplied. Key registry changes require API restart. Untrusted traffic can generate
audit rows; public exposure requires hardening.

## Chaincode controls (Milestone 7)

The contract cross-checks certified role/org attributes with an explicit MSP allowlist;
ordinary arguments cannot spoof organizations. Verification is admin-only; registration
and acceptance require the matching exporter. Only the assigned financier can record
financing/release. Payment confirmation requires the settlement backend attribute and
independently checks state, exact private amount, currency and global event uniqueness.

Sensitive payloads travel through transient data, never ordinary arguments. Salted private
amount commitments resist guessing; exporter-private storage and four distinct pair
collections prevent losing banks from being collection members. Public state/history/events
stay sanitized. Salts must be generated securely off-chain. Proposal recipients see transient
plaintext, so the gateway explicitly selects actor or exporter/winning-financier endorsers.

Tests verify contract logic and rollback semantics in an explicit in-memory harness. They
do not validate live endorsement, gossip, MVCC, CA provisioning or Drunix compatibility.
Those still require validation on a provisioned network. A compromised trusted verifier/settlement backend,
misissued certificate attributes or incorrect network endorsement policies remain risks.

## Gateway trust boundary (Milestone 8)

The internal relay bearer token grants access to mapped signing identities and must remain
private. Peer TLS validates root and hostname. Remote relay HTTP is rejected by API
configuration. SDK errors are reduced to allowlisted codes; no fallback manufactures
success. Private journal inputs survive rollback and require restricted database access,
backups and retention. This journal is application-private storage, not a blockchain PDC.
No live-network privacy or commit guarantees have been validated locally.

## Sandbox simulator boundary (Milestone 9)

The sandbox signer is opt-in and separate from the API. Its token authorizes signing and
must remain private. The API requires a settlement-role session before contacting it;
public webhook requests still need a valid asymmetric signature. Invalid/replayed demo
events exercise the same verification service as external events. Exact event bytes are
stored privately, and replay is scoped to the submitting user. Audit/security feeds require
admin access and do not expose raw event bodies, signatures or private invoice amounts.
The signer is not a production bank authority; disable it outside private demonstrations.

## Error, logging and reset boundaries (Milestone 10)

Validation and unexpected errors omit raw input and exception text. Generated request IDs
correlate sanitized errors and JSON request logs. Logs contain route templates, never raw
query strings; standard API commands disable Uvicorn access logs. Authenticated identifiers
remain operational metadata requiring restricted access and a deployment retention policy.

Reset is a local mock-fixture maintenance operation, never a real-ledger rollback. It
requires an explicit confirmation, rejects altered fixture terms and Drunix recovery data,
and uses table locks and a single transaction. PDFs and audit/security evidence are retained;
operators must define production retention separately. The fresh-setup test uses its own
randomly named Compose project and deletes only that project's volumes.

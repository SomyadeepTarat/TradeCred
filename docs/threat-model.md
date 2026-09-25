# Threat model

Only bootstrap services exist. The controls below distinguish current behavior from
required future protections; none of the planned business controls is claimed as implemented.

| Threat | Required mitigation and implementation milestone |
| --- | --- |
| Duplicate financing | Deterministic fingerprint (2), registry and state validation (3), exclusive financing lock (5). Off-network institutions remain a residual risk. |
| Document modification | Off-chain SHA-256 integrity verification (2). |
| Fake settlement | Asymmetric signatures, trusted public-key registry, amount/currency validation (6). |
| Replay | Unique event ID and nonce, timestamp TTL (6). |
| Unauthorized transition | RBAC (1), centralized transition matrix (3), chaincode authorization (7). |
| Sensitive data leakage | Off-chain raw documents (2), sanitized ledger state (3), private data collections (7). |
| Ledger unavailable | No false success; explicit mock abstraction (3), idempotency/transaction tracking, retry and gateway errors (8–10). |

Current controls: localhost-only Compose ports, ignored environment files, non-root
API/web containers, readiness failure without credential disclosure, and real database
connectivity tests. The application has no protected business endpoints yet. Local
sample database credentials are not production credentials. Do not expose this stack
as a production service. Future logs must exclude tokens, keys, accounts and document bytes.

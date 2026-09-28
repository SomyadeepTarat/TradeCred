# API — Milestone 6

Base path: `/api/v1`. Interactive OpenAPI: `http://localhost:8000/docs`.

| Method | Path | Access / behavior |
| --- | --- | --- |
| GET | `/health` | Public liveness, 200 |
| GET | `/health/ready` | Public real PostgreSQL query, 200 or 503 |
| POST | `/auth/login` | Public JSON login, 200 with JWT or 401 |
| GET | `/auth/me` | Any active authenticated user; safe user projection |
| GET | `/organizations` | ADMIN only; actual organization records |
| POST | `/receivables` | EXPORTER only; multipart draft + private PDF, 201 |
| GET | `/receivables/{id}/document` | Owning exporter organization only; verified PDF attachment |
| GET | `/receivables/{id}/document/integrity` | Owning exporter organization only; rehash stored bytes |

Login body (example credentials are for local development only):

```json
{"email":"exporter@tradecred.demo","password":"TradeCred-Demo-2026!"}
```

Response fields: `access_token`, `token_type` (`bearer`), `expires_in` (seconds).
Email is trimmed and lowercased. Extra request fields such as `role` are rejected (422).
Use `Authorization: Bearer <access_token>` for protected routes. `/auth/me` returns
`id`, `email`, `display_name`, `role`, and `organization_id`, never the password hash.
Login and identity responses set `Cache-Control: no-store`.

JWT uses HS256 only, a required minimum 32-character secret, fixed issuer/audience,
required subject, issue/not-before/expiry times, token type and unique token ID. Default
expiry is 30 minutes. Role and organization are loaded from PostgreSQL on every request;
a token cannot retain a removed role or bypass account deactivation.

Authentication failures use the same message for unknown users, wrong passwords and
inactive accounts. Password verification uses Argon2id and runs outside the event loop.
Unknown users also pass through password verification using a dummy hash.

```json
{"error":{"code":"UNAUTHORIZED_ROLE","message":"Your role cannot access this resource.","details":{}}}
```

Codes: `AUTHENTICATION_REQUIRED` (401), `INVALID_TOKEN` (401),
`INVALID_CREDENTIALS` (401), `UNAUTHORIZED_ROLE` (403). Authentication errors include
`WWW-Authenticate: Bearer`. Request validation retains FastAPI's 422 format for now.

The mock lifecycle, registry, financing and signed settlement endpoints below are available; ledger responses identify the configured backend. Live Drunix operation requires a provisioned network; payment disbursement remains simulated.

## Invoice documents

Upload exactly one `metadata` JSON text field and one `document` file field using
`multipart/form-data`. Metadata requires `buyerId`, `invoiceNumber`, `invoiceDate`,
`currency`, `amount` (decimal string), `dueDate`. Extra fields, including an exporter ID,
are rejected. See README for the complete example. `application/pdf` is required, and
actual PDF content is validated. Caller filenames are discarded; storage keys are UUIDs.

A 201 response contains `id`, `status` (DRAFT), `document_id`, `document_hash`,
`invoice_fingerprint`, `fingerprint_version` (TC-FP-1), `currency`, `face_value_minor`.
No storage path, ledger ID or eligibility flag is returned.

Integrity returns `document_id`, `expected_hash`, `actual_hash`, and `verified`. A changed
file returns 200 with `verified: false`; downloads fail with 409 instead of returning
corrupted bytes. Missing/unreadable storage returns 503, never integrity success. A stored
file over the configured maximum returns 409. Unknown and other-organization draft IDs
both return 404. Non-exporter roles receive 403, including admins.

Additional error codes: `INVALID_UPLOAD` / `INVALID_INVOICE_METADATA` / `INVALID_PDF` (422),
`UNSUPPORTED_DOCUMENT_TYPE` (415), `UPLOAD_TOO_LARGE` (413), `DUPLICATE_RECEIVABLE` (409),
`DOCUMENT_NOT_FOUND` (404), `DOCUMENT_INTEGRITY_FAILED` (409),
`DOCUMENT_STORAGE_UNAVAILABLE` / `DATABASE_UNAVAILABLE` (503). Malformed multipart bodies
and excess form parts use the framework's 400 response. The request limit applies before
multipart spooling; the PDF limit is also checked independently.

Upload duplicates refer to the local database. Registration additionally checks the
selected ledger registry, rejecting fingerprints already registered to another asset.


## Mock ledger, registry and audit

All routes below require authentication. `LEDGER_BACKEND=mock` is the implemented adapter.
`drunix` returns `LEDGER_UNAVAILABLE` (503) for ledger-dependent operations. Every request
gets a server-generated `X-Request-ID`; clients cannot choose audit correlation IDs.

| Method | Path | Access / behavior |
| --- | --- | --- |
| POST | `/receivables/{id}/submit` | Owner exporter; DRAFT → SUBMITTED |
| POST | `/receivables/{id}/verify` | ADMIN; SUBMITTED → VERIFIED |
| POST | `/receivables/{id}/register` | Owner exporter or ADMIN; VERIFIED → REGISTERED, idempotent retry |
| POST | `/receivables/{id}/open-financing` | Owner exporter; REGISTERED → FINANCE_AVAILABLE |
| GET | `/receivables/{id}/history` | Owner exporter or ADMIN; application audit and ledger revisions |
| POST | `/registry/check` | Any participant; normalized business inputs |
| GET | `/registry/fingerprint/{fingerprint}` | Any participant; 64 lowercase hex SHA-256 |
| GET | `/audit/events?limit=100&offset=0` | ADMIN; newest first, limit 1–500, offset 0–10000 |

Lifecycle POSTs have no body. Submission, verification and first registration rehash the
stored document and invoice identity. Verification is an explicit administrator action
plus integrity checks, not external commercial verification. This permission does not
grant the administrator raw-PDF download access.

Lifecycle response fields: `id`, `status`, `asset_id`, `transaction_id`, `backend`, `replayed`.
Submit/verify have no ledger receipt (`transaction_id` and `backend` are null). Registration
and opening return `backend: "mock"`, a stable `TC-…` asset ID, and `MOCK-…` transaction ID
only after commit. Retrying registration returns the original registration transaction ID
with `replayed: true` and the **current** ledger status; it adds no extra transaction/audit.
Other invalid or repeated transitions return `INVALID_STATE_TRANSITION` (409).

Registry request example:

```json
{"exporterId":"ORG_EXPORTER_ALPHA","buyerId":"BUYER-DE-001","invoiceNumber":"EXP-2026-1042","currency":"EUR","amountMinor":1080000,"invoiceDate":"2026-09-21"}
```

Uses the same TC-FP-1 normalization as upload. Floats, extra fields, malformed dates and
invalid currencies are rejected. Response keys: `fingerprint`, `exists`, `eligible`,
`locked`, `financed`, `backend`, and, when present, `assetId`, `status`, `reason`.
Absent fingerprints return `exists: false, eligible: true`: no registered asset was found,
not proof that there is no local draft or off-network financing. Existing assets are
eligible only at FINANCE_AVAILABLE. Locked/financed assets are ineligible. No response
includes the exact amount, buyer ID, filename, storage key, PDF or private settlement reference.

Duplicate registration returns 409 `DUPLICATE_RECEIVABLE` with the existing `assetId` and
`status` in `error.details`. Conflicting reuse of an asset ID returns 409
`REGISTRATION_CONFLICT`. Storage/integrity or transaction failures never return success.

History contains `events` (event type, actor user/org, receivable/asset IDs, request ID,
allowlisted metadata, timestamp) and `ledger` (mock transaction ID, asset, revision,
from/to status, actor org, timestamp, backend). Ledger revisions begin at registration;
local creation/submission/verification appear in audit events. No invented history is
created for older records. Audit log and mock history are PostgreSQL records, not a claim
of blockchain immutability. Financing and signed settlement endpoints are documented below.


## Receivables UI read APIs

`GET /receivables?status=SUBMITTED&limit=20&offset=0` and `GET /receivables/{id}` require
EXPORTER or ADMIN. Exporters can only read their own organization. Admins can review all
records, but `buyer_id`, `invoice_number` and `face_value` are null; PDFs remain inaccessible.
Financiers receive scoped sanitized access as described below; settlement roles receive 403. Other-organization and unknown exporter IDs both
return 404. Responses set `Cache-Control: no-store`.

List returns `items`, filtered `total`, organization-scoped `summary` and up to five recent
receivable audit events. `limit` is 1–100, `offset` 0–100000. Summary counts are independent
of the filter: total, available (FINANCE_AVAILABLE), financed (FINANCED/OVERDUE/DISPUTED),
settled (PAYMENT_CONFIRMED/REALIZED/EBRC_ELIGIBLE/CLOSED). Ordering is newest creation then ID.
Exact `face_value` is a decimal string, never a JavaScript floating-point conversion.

Detail additionally returns `document_available` (download permission and metadata presence),
`available_actions` (role/state-aware submit, verify, register, open-financing) and
`ledger_backend`. Available actions are hints; mutation routes independently enforce all
permissions, integrity checks and transitions. File existence/integrity is confirmed by the
existing document endpoints, not by `document_available`. Storage keys, document contents
and private settlement references are never included in these projections.

The Next.js `/api/backend/...` gateway exposes only the route allowlist needed by this UI.
Its `auth/login` sets an HttpOnly cookie and returns `{ "signedIn": true }`, not a JWT.
`auth/logout` deletes that cookie. Requests use same-origin cookies, with Origin/Host
validation for POSTs. The underlying FastAPI login API continues returning JWTs to API clients.


## Financing APIs (Milestone 5)

All paths use `/api/v1`. Private financing responses are no-store.

| Method | Path | Access |
| --- | --- | --- |
| POST | `/receivables/{id}/offers` | FINANCIER; registered FINANCE_AVAILABLE asset |
| GET | `/receivables/{id}/offers` | Owner exporter sees all offers; financier sees its own; admin sees no terms |
| POST | `/offers/{id}/accept` | Owner EXPORTER only; idempotent for the accepted offer |
| POST | `/offers/{id}/reject` | Owner EXPORTER only; accepted offers cannot be rejected |
| POST | `/receivables/{id}/disbursement/mock` | Winning FINANCIER only; idempotent sandbox payout |

Offer body:

```json
{"advanceAmount":"9750.00","currency":"EUR","discountRateBps":250,"tenorDays":60,"expiresAt":"2099-01-01T12:00:00Z"}
```

Use a future timezone-aware expiry. The example is illustrative. `advanceAmount` must be
positive exact decimal text, no greater than face value, in the invoice currency.
`discountRateBps` is an integer 0–10000; `tenorDays` is an integer 1–3650. Extra fields and
client-supplied institution IDs are rejected. Rate and tenor are recorded terms; the
advance is supplied explicitly, with no implicit FX/discount calculation.

GET offers returns `offers`, authorized `agreement`, `payment`, `can_offer`, `can_accept`,
`can_disburse`, and `backend`. Monetary offer values are decimal strings. The canonical
agreement is supplied as text to preserve exact integer values in JavaScript. Only its
hash is committed to sanitized ledger state. The agreement contains version, asset,
exporter, institution, exact minor-unit advance, currency, rate, tenor, UTC acceptance time,
terms version and consortium financing-lock representation. Canonical JSON uses sorted
keys, compact separators, UTF-8, and SHA-256.

Acceptance locks the receivable, marks one offer ACCEPTED, rejects competing live offers,
persists the agreement and audits atomically. An expired acceptance returns 409 after
recording expiry. Repeated accepted-offer requests return `replayed: true`, the original
lock transaction and current asset status, without rewinding state.

Disbursement returns `payment.status: SIMULATED_SUCCEEDED`, `backend: mock`, a MOCKPAY-
transaction ID and a MOCK- ledger reference. Simulation, ledger transition, projection and
audit share one transaction. Failure reports no success; retries reconcile a lost response.
This does not confirm buyer settlement. Drunix mode records financing through the configured gateway; unknown commits return 503 without fallback.

Financier GET `/receivables` supports `view=available|offers|assigned|all`; pagination and
status filtering remain available. Only open assets, assigned assets or assets with that
institution's previous offers are visible. Exact value, buyer, invoice number and invoice
date are null; `face_value_bucket` supplies a range. PDFs remain inaccessible. Financier
history contains sanitized ledger revisions and an empty application-audit list.

409 errors include OFFER_EXPIRED, OFFER_NOT_AVAILABLE, RECEIVABLE_ALREADY_LOCKED,
RECEIVABLE_ALREADY_FINANCED, AGREEMENT_INTEGRITY_FAILED and INVALID_STATE_TRANSITION.
Ledger/projection disagreement returns 503 LEDGER_STATE_MISMATCH. Payment/DB failures
never return success. Rejected duplicate-financing attempts receive audit records.

## Signed settlement (Milestone 6)

POST /api/v1/settlement/events authenticates with Ed25519, independently of JWTs.
Send X-TradeCred-Key-Id and X-TradeCred-Signature (standard base64). Sign the protocol
prefix `TradeCred-settlement-v1\n` followed by the exact HTTP body bytes. The API does
not canonicalize or reserialize before verification.

JSON fields: eventId, assetId, bankId, bankReference, amountMinor, currency, timestamp,
nonce (PRD section 18). amountMinor is a positive 64-bit integer equal to the FULL invoice
value; currency is the exact uppercase invoice currency. No partial payment, advance
repayment or FX conversion is inferred. timestamp must be timezone-aware and within
±300 seconds (configurable downwards). nonce is 16–160 ASCII letters/digits/underscore/
hyphen. IDs and references are bounded. Duplicate JSON fields, unknown fields, malformed
bodies and bodies over 8192 bytes fail.

200 response: event_id, asset_id, verification_status=VERIFIED, status=PAYMENT_CONFIRMED,
transaction_id, received_at, backend=mock. The receipt describes the recorded transition,
not future asset state. Receipt, private remittance reference, receivable projection,
ledger transition and success audit commit atomically. No realization/e-BRC is implied.

Errors: INVALID_PAYMENT_SIGNATURE (401), UNTRUSTED_BANK (403), INVALID_PAYMENT_EVENT
(422; 413 for size), PAYMENT_TIMESTAMP_EXPIRED / PAYMENT_EVENT_REPLAY /
PAYMENT_AMOUNT_MISMATCH / PAYMENT_CURRENCY_MISMATCH / INVALID_STATE_TRANSITION (409),
ASSET_NOT_FOUND (404), LEDGER_UNAVAILABLE / SETTLEMENT_UNAVAILABLE (503).
Rejected attempts create security_events with request ID, reason and payload hash only.
No raw body, signature, key, reference or untrusted claimed identity is stored in this audit.
Invalid events do not consume identifiers or mutate ledger state. Committed replays fail;
query the receipt after an uncertain response before retrying.

GET /api/v1/settlement/events/{event_id} requires JWT. Only the exporter, assigned
financier, submitting settlement organization and admin can read its sanitized receipt.
Other organizations receive 404. Responses are no-store and omit amounts, nonce and
remittance reference. The Next.js gateway does not proxy the signed webhook. The bank
simulator runs outside the browser with its private key.

See [simulator commands](../services/bank-simulator/README.md).

## Gateway failures (Milestone 8)

Ledger responses use `backend: mock` or `backend: drunix`; mock payment receipts remain
`backend: mock` in both modes. `LEDGER_UNAVAILABLE` (503) includes unknown remote outcomes.
Retry the same action after recovery; do not create replacement offers/events. Exact
operation receipts permit projection repair without a second business transition.
`LEDGER_BACKEND_MISMATCH` (503) rejects assets from another backend/network.
`OPERATION_CONFLICT` (409) rejects changed durable inputs. Gateway credentials are
internal and never accepted from public API callers.

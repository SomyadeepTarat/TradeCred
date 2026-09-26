# API — Milestone 2

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

Receivable lifecycle, financing, settlement and registry endpoints are not implemented. No endpoint
claims a ledger write, payment or regulatory workflow succeeded.

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

A duplicate response only means the invoice already exists in the local database.
The consortium registry, ledger state and financing eligibility are Milestone 3+.

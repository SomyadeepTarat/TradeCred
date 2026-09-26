# Milestone 2 walkthrough

1. On first setup, copy `.env.example` to `.env`. Preserve existing environment settings.
2. Run `make install`, `make dev`, and `make seed`.
3. Open `http://localhost:3000` to see current scope.
4. Open `http://localhost:8000/docs`. Log in as `exporter@tradecred.demo` using
   `DEMO_PASSWORD` (example: `TradeCred-Demo-2026!`).
5. Copy `access_token` into Authorize and call `/api/v1/auth/me`; verify EXPORTER.
6. Call `/api/v1/organizations`; verify 403.
7. Log in as `admin@tradecred.demo`, replace the bearer token, and repeat the organization
   request; verify six real organization records.
8. Remove authorization and call `/api/v1/auth/me`; verify 401.
9. Run `make test`, `make lint`, `make test-integration`, and `make build`.

No business-demo receivables are seeded yet. The three PRD financial scenarios remain
scheduled for later milestones. Stop services without deleting data with `docker compose down`.


## Document walkthrough

1. Authorize as the exporter, select `POST /api/v1/receivables` in Swagger, and upload
   a real PDF with the README's metadata JSON. Observe DRAFT, document hash and fingerprint.
2. Use the returned ID to call the document integrity endpoint; verify `verified: true`.
3. Download the PDF and compare its SHA-256 with `document_hash`; the bytes are unchanged.
4. Re-upload with case/whitespace variants and a different PDF. The local duplicate
   constraint returns 409; it does not claim a ledger registration or financing state.
5. Authorize as a financier/admin; document access returns 403. Raw commercial PDFs stay private.

Uploads are user-created drafts only. No submission, verification, registry or financing
workflow is available in Milestone 2. Keep the ledger explicitly unconnected.

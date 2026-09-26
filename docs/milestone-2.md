# Milestone 2 — Fingerprinting and Documents

Implemented after inspecting the existing Milestone 1 application, migrations, tests,
configuration and PRD requirements. The PRD and prior milestone changes were preserved.
No Milestone 3 ledger/registry/state-machine implementation was added.

## Delivered behavior

- Exporter-only multipart PDF upload creates a DRAFT receivable and document metadata.
- Document SHA-256 hashes the original bytes, without rewriting the PDF.
- TC-FP-1 hashes canonical business metadata, independently of document content.
- Precise currency minor units use decimal text and ISO-4217 exponents, with no rounding.
- IDs and invoice case/whitespace normalize deterministically. Potentially meaningful
  invoice punctuation is preserved; unsupported characters are rejected.
- Local private filesystem storage uses UUID keys, exclusive writes, 0600 permissions,
  no caller filenames/paths, and no symlink reads. Docker uses a persistent private volume.
- Owner-organization exporters can download or recheck integrity; other roles and
  organizations cannot access raw PDFs. Downloads reject mismatched stored bytes.
- Uploads reject bad PDFs/MIME types, encrypted PDFs, unsupported metadata, oversize
  files/requests (including chunked requests), and local duplicate fingerprints.
- File/DB failures never return a successful upload. No ledger success is simulated.

## Created files

```text
apps/api/app/api/routes/receivables.py
apps/api/app/core/upload_limits.py
apps/api/app/integrations/storage/base.py
apps/api/app/integrations/storage/local.py
apps/api/app/repositories/receivables.py
apps/api/app/schemas/receivables.py
apps/api/app/services/document_service.py
apps/api/app/services/fingerprint_service.py
apps/api/app/services/receivable_service.py
apps/api/migrations/versions/0002_private_invoice_documents.py
apps/api/tests/__init__.py
apps/api/tests/helpers.py
apps/api/tests/test_document_integration.py
apps/api/tests/test_documents.py
apps/api/tests/test_fingerprinting.py
docs/fingerprinting.md
docs/milestone-2.md
```

## Modified files in this milestone

```text
.env.example
README.md
docker-compose.yml
apps/api/Dockerfile
apps/api/pyproject.toml
apps/api/uv.lock
apps/api/app/core/config.py
apps/api/app/main.py
apps/api/app/models/domain.py
apps/api/tests/conftest.py
apps/api/tests/test_domain_integration.py
apps/web/app/page.tsx
apps/web/tests/page.test.tsx
docs/api.md
docs/architecture.md
docs/demo-script.md
docs/threat-model.md
```

Integration setup was extracted into shared helpers/fixtures so both milestones use
isolated PostgreSQL schemas. Existing tests and domain/auth behavior remain covered.
The Git working tree already contained prior milestone changes; they were not reverted.

## Commands

Preserve your existing `.env`; add `MAX_UPLOAD_BYTES` only if overriding the 10 MiB default.

```sh
make install
make dev          # Builds containers; applies migrations 0001 and 0002
make seed         # Creates missing demo users; preserves existing credentials
make test
make lint
make test-integration
make build
```

For host development: `make db`, `make migrate`, `make seed`, then `make api` and
`make web` in separate terminals. Host and Docker document stores are distinct; keep
PDF objects with their corresponding DB records when switching modes.

Use `http://localhost:8000/docs` to log in as the exporter and authorize. Upload a PDF to
`POST /api/v1/receivables` with the README's JSON metadata example; then use the returned
ID for `GET /api/v1/receivables/{id}/document/integrity` or `/document`.
The frontend reports scope; the exporter upload form is scheduled for Milestone 4.

## Verification performed

- `make test`: 93 API unit tests and 1 frontend rendering test passed.
- `make test-integration`: 21 real PostgreSQL tests passed (115 total tests).
- Tests cover the fixed canonical hash vector, required case/whitespace equivalence,
  changed amount/date/identity, PDF independence, minor-unit precision, malformed files,
  immutability, traversal/symlinks, partial-write cleanup, uncertain commit, ownership,
  tampering/missing files, duplicates without extra objects, size limits, and rollback.
- Existing authentication, seed, migration downgrade/upgrade and metadata checks passed.
- `make lint`: Ruff, formatting, mypy, ESLint, TypeScript and Prettier passed.
- `make build`: Next.js production/standalone build passed.
- Docker build/start succeeded; migration 0002 applied and all services became healthy.
- Live Docker smoke: upload returned 201; downloaded bytes exactly matched the original;
  SHA-256 and integrity checks passed before and after API restart. The test's own draft,
  metadata and file were removed afterward; no demo data was deleted.
- Browser confirmed the Milestone 2 status page.
- `git diff --check` passed; no TODO/FIXME markers were added to core flows.

## Remaining limitations

No Milestone 2 acceptance blocker remains. There is no atomic transaction spanning
PostgreSQL and the filesystem: a process crash or uncertain commit may leave an orphan.
On an uncertain commit the file is retained and the API returns 503. Manual reconciliation
is required; no cleanup worker is claimed. Back up both database and object storage.

PDF parsing is structural validation, not antivirus, sandboxing, OCR or business invoice
verification. PDFs are returned only as attachments after ownership and integrity checks.
At-rest encryption and production parser isolation are deferred. The existing auth
hardening and ESLint 9 support limitations remain documented in README.

Duplicate rejection currently uses local DB uniqueness only. Consortium eligibility,
registration, state transitions, audit history and MockLedgerClient belong to Milestone 3.

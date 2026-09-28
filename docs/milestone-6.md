# Milestone 6 — Settlement Security

Implemented after reading the complete PRD and inspecting the completed Milestone 5
repository. Milestone 7 has not been started.

## Delivered

- Ed25519 key generation with private file permissions, ignored local key storage and
  refusal to overwrite keys. Docker mounts only a separate public-key directory read-only.
- A CLI bank simulator sending actual signed HTTP requests, with invalid-signature and
  replay modes. It moves no funds and does not imply live NPCI connectivity.
- Signed webhook authenticated against an explicit key-ID / bank-ID / organization registry;
  the organization must have an active SETTLEMENT_OPERATOR identity. JWTs alone cannot
  authorize payment confirmation. Domain-separated signatures cover exact body bytes.
- Strict input validation, bounded payloads, duplicate-field rejection, ±5-minute timestamp
  tolerance, global event-ID and nonce uniqueness, full-invoice amount/currency matching,
  FINANCED-only state validation and independent MockLedgerClient validation.
- Transaction locks and unique constraints protect concurrent processing. Successful
  receipt, ledger transition, private remittance reference, local state and audit commit
  atomically. Invalid events leave financial state and replay identifiers unchanged.
  Failed attempts record a sanitized security event in a separate transaction.
- Protected, sanitized receipt lookup for the exporter, assigned financier, submitting
  bank organization and administrator. Other organizations receive 404.
- Migration 0005 creates payment_events and security_events. API version is 0.7.0.
- Existing receivable UI shows PAYMENT_CONFIRMED and the recorded ledger history; it
  continues to state that no funds move and TradeCred does not issue e-BRC.

## Files created

- `apps/api/app/api/routes/settlement.py`
- `apps/api/app/models/settlement.py`
- `apps/api/app/schemas/settlement.py`
- `apps/api/app/security/signatures.py`
- `apps/api/app/services/settlement_service.py`
- `apps/api/migrations/versions/0005_settlement_payment_and_security_events.py`
- `apps/api/tests/test_settlement.py`
- `apps/api/tests/test_signatures.py`
- `scripts/generate_keys.py`
- `services/bank-simulator/README.md`
- `services/bank-simulator/app.py`
- `services/bank-simulator/requirements.txt`
- `services/bank-simulator/signing.py`
- `docs/milestone-6.md`

## Files modified

- `.env.example`
- `Makefile`
- `README.md`
- `apps/api/app/core/config.py`
- `apps/api/app/integrations/ledger/mock.py`
- `apps/api/app/main.py`
- `apps/api/app/services/audit_service.py`
- `apps/api/migrations/env.py`
- `apps/api/pyproject.toml`
- `apps/api/uv.lock`
- `apps/web/components/receivable-detail.tsx`
- `apps/web/components/workspace.tsx`
- `docker-compose.yml`
- `docs/api.md`
- `docs/architecture.md`
- `docs/threat-model.md`

## Commands

```sh
make install
make keys                 # Once; refuses to overwrite existing keys.
make dev                  # Applies migration 0005 during API startup.
make seed                 # Preserves existing credentials and receivables.
make test
make test-integration
make lint
make test-e2e             # Production build plus Chromium regression tests.
```

For host development: copy the public-only BANK_TRUSTED_KEYS line printed by make keys
into .env, then use make db, make migrate and separate make api / make web terminals.
Docker has its own explicit registry configuration. The simulator CLI runs from the host;
a separate always-on bank service is unnecessary for this milestone.

After financing an invoice, use its asset ID and full value in original-currency minor units:

```sh
make bank-event ARGS="--asset-id TC-REPLACE --amount-minor 1080000 --currency EUR --reference IRM-DEMO-938291 --invalid-signature"
make bank-event ARGS="--asset-id TC-REPLACE --amount-minor 1080000 --currency EUR --reference IRM-DEMO-938291 --save data/payment-event.json"
make bank-event ARGS="--replay data/payment-event.json"
```

Expected: 401, then 200 PAYMENT_CONFIRMED, then 409 replay (within five minutes).
Use a fresh save filename for subsequent events. See the bank-simulator README for
key configuration, protocol, receipt lookup, revocation and retry semantics.

## Verification

**426 tests passed:** 329 API unit, 74 PostgreSQL integration, 20 frontend/gateway and
3 Chromium acceptance tests. This includes 27 new settlement/signature/simulator tests.

- Key generation, private file mode, overwrite refusal, signing interoperability, wrong
  keys/domain, malformed signatures and unavailable key failures.
- Valid settlement, scoped receipt reads, bad/tampered/missing signatures, unknown keys,
  wrong bank, stale/future timestamps, wrong amount/currency, non-financed assets, malformed
  values, naive timestamps, bad reference, duplicate fields, oversized bodies and disabled
  settlement identities. Rejections are audited and never change ledger state.
- Event-ID and nonce replay protection, concurrent identical requests (one transition),
  failed-event identifier reuse, ledger rollback/retry and Drunix fail-closed behavior.
- Simulator subprocess over HTTP: invalid signature rejected, valid event accepted,
  saved event replay rejected. Test databases and keys are isolated and removed afterward.
- Database migration upgrade/downgrade and metadata alignment passed in the regression suite.
- Ruff lint/format, strict mypy (63 modules), ESLint, TypeScript and Prettier passed.
- Production Next.js build and all existing browser workflows passed.
- Docker build/start passed with healthy PostgreSQL, API and web. Running-container smoke
  verified API 0.7.0, web login, bad-signature rejection and simulator/public-key
  interoperability against a nonexistent asset, without changing developer receivables.
- git diff whitespace checks passed.

## Remaining boundaries

No outstanding Milestone 6 test failures. Settlement stops at PAYMENT_CONFIRMED; downstream
realization/e-BRC/closure orchestration and the browser simulator remain later work.
Milestone 7 chaincode and Milestone 8 gateway are not implemented ahead of schedule.
Drunix configuration still returns 503 without mock fallback. MockLedgerClient is explicit.

Signatures authenticate the bank simulator, not real banking finality. A compromised trusted
signer remains a risk. Private keys are local demo files, not HSM-managed. Key changes need
API restart. Production TLS, webhook rate limiting, audit retention and external reconciliation
remain documented hardening work. Unavailable audit/database storage returns 503, never success.

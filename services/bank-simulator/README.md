# Authorized bank simulator — Milestone 6

This CLI signs real HTTP requests to simulate trusted bank settlement confirmation. It does
not transfer funds, perform FX, issue e-BRC or connect to NPCI banking APIs. The browser
simulator is reserved for Milestone 9.

From the repository root:

```sh
make install
make keys
make dev
make seed
```

Keys: data/bank-keys/bank-private.pem (PKCS8 Ed25519, mode 0600) and
 data/bank-public/bank-public.pem. Both are ignored by Git. Generation refuses to overwrite
either file. The API container mounts only the separate public directory read-only.
Never copy private keys into the browser, environment files or API container.

Docker trusts key ID demo-bank-1 for BANK_SETTLEMENT_01, organization ORG_SETTLEMENT_BANK.
This organization must have an active settlement operator. For a host API, copy the
BANK_TRUSTED_KEYS line printed by make keys into .env, then restart make api.
An empty registry denies every event; missing/malformed public keys return 503.
Additional keys/banks may be added to this JSON mapping. Revocation removes the key entry
and restarts the API. Rotation uses new key IDs and separately generated files. Production
key custody and dynamic rotation are outside this milestone.

Create/register an invoice, accept an offer and simulate disbursement in the UI. Copy its
asset ID (TC-...). For a EUR 10,800 invoice use its FULL value in minor units, not the advance:

```sh
make bank-event ARGS="--asset-id TC-REPLACE --amount-minor 1080000 --currency EUR --reference IRM-DEMO-938291 --invalid-signature"
make bank-event ARGS="--asset-id TC-REPLACE --amount-minor 1080000 --currency EUR --reference IRM-DEMO-938291 --save data/settlement-event.json"
make bank-event ARGS="--replay data/settlement-event.json"
```

Expected: 401 INVALID_PAYMENT_SIGNATURE, 200 PAYMENT_CONFIRMED with MOCK- transaction ID,
then 409 PAYMENT_EVENT_REPLAY. Replay within five minutes; older events fail freshness first.
Rejected requests exit nonzero. Saved events are private local files, created exclusively;
use a new filename for each new event. Refresh the asset UI to view actual status/history.

A valid event passes signature, key/bank binding, active identity, timestamp, event ID,
nonce, invoice amount/currency and FINANCED state checks. Only successful events consume
identifiers. Retry the exact signed bytes after a transient 503 while still fresh. After
an uncertain response, inspect the protected receipt; committed replays return 409.

Signing: standard base64 Ed25519 signature over the protocol prefix
`TradeCred-settlement-v1\n` (ending in one newline byte), followed by the exact UTF-8 JSON
HTTP body. Do not reserialize after signing. Headers are X-TradeCred-Key-Id and
X-TradeCred-Signature. The webhook authenticates by signature, not JWT.
GET /api/v1/settlement/events/{event_id} requires JWT and limits access to the exporter,
winning financier, submitting bank organization or administrator.

Milestone 6 stops at PAYMENT_CONFIRMED. Realization, eligibility/closure orchestration
and the browser simulator are not silently performed.

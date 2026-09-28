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

## Browser sandbox (Milestone 9)

`make demo` starts the optional `demo` Compose profile. The signing service mounts only
`data/bank-keys` read-only. The API mounts public keys only. `make keys` is now idempotent:
existing complete keypairs are preserved and a random `SIMULATOR_TOKEN` is added to the
private `.env` only when missing. An incomplete pair still fails without overwriting files.

The browser uses session-authenticated, settlement-role-only `/simulator` APIs. The API
asks the internal `/sign` service to sign exact event bytes, persists those bytes, then
passes them through the same signature/nonce/timestamp/amount/state validation service
used by the public webhook. Invalid-signature mode corrupts the actual signature;
replay uses the original stored signature and body. No alternate payment-confirmation
path bypasses verification. Unknown outcomes remain explicitly unknown and can be retried
using the returned simulator ID. Payloads and signatures never return to the browser.

The signer listens on loopback port 8090 and the private Compose network; its bearer token
must remain secret. It is an explicitly enabled local sandbox authority, not a real bank.
`SIMULATOR_ENABLED` defaults false. `make demo` enables it only for that Compose invocation.
For host development, start the signer from `apps/api` with `PYTHONPATH` including both
`apps/api` and `services/bank-simulator`, set `BANK_PRIVATE_KEY_PATH`, `SIMULATOR_TOKEN`,
then run `uv run uvicorn server:app --host 127.0.0.1 --port 8090`. Configure the API's
public key registry, `SIMULATOR_ENABLED=true` and `SIMULATOR_URL=http://127.0.0.1:8090`.
Remote signer URLs require HTTPS. No private key is needed in the browser or API process.

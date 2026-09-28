# TradeCredContract — Milestone 7

Deployable Go chaincode built with the official Hyperledger Fabric contract API v2.2.2.
This milestone supplies and tests the contract; it does not deploy a Drunix network or
connect FastAPI to it. The application still uses explicit MockLedgerClient. Selecting
Drunix continues to fail closed until the Milestone 8 gateway is implemented and verified.

## Build and test

From the repository root:

```sh
make test-chaincode
make lint-chaincode
make build-chaincode
make format-chaincode
```

Go 1.26+ is required by this module. If Go is absent, scripts/chaincode.sh uses a pinned
Go 1.26.8 Docker image, mounts only this module, and caches modules/builds in named Docker
volumes. Docker Desktop must be running; the first invocation downloads the toolchain and
locked dependencies. No network or ledger is started. If Go is installed it is used locally.
The executable is generated under ignored build/tradecred (Linux when built with Docker).
Go module versions/checksums are committed; tests/builds use -mod=readonly.

make test includes Go race/coverage tests; make lint includes gofmt checking and go vet.
CI installs Go and executes the same tests plus the executable build. The in-memory test
stub explicitly models commit/rollback and private storage. It does not emulate Fabric
endorsement, private-data dissemination, ordering, commit validation or real Drunix peers.

## Public methods and lifecycle

| Method | Caller | Result |
| --- | --- | --- |
| VerifyReceivable(registrationJSON) | ADMIN | Records verifier attestation, reserves fingerprint, creates VERIFIED |
| RegisterReceivable(registrationJSON) | Matching EXPORTER | VERIFIED → REGISTERED; stores exporter-private invoice |
| GetReceivable(assetId) | Any recognized participant | Sanitized asset |
| GetReceivableByFingerprint(fingerprint) | Any recognized participant | Sanitized asset; ASSET_NOT_FOUND if absent |
| OpenForFinancing(assetId) | Matching EXPORTER | REGISTERED → FINANCE_AVAILABLE |
| LockReceivable(assetId, financierOrgId, agreementHash) | Matching EXPORTER | FINANCE_AVAILABLE → LOCKED |
| RecordFinancing(assetId) | Assigned FINANCIER | LOCKED → FINANCED |
| ReleaseLock(assetId) | Assigned FINANCIER | LOCKED → RELEASED; clears current owner |
| ConfirmPayment(assetId) | Settlement backend service | FINANCED → PAYMENT_CONFIRMED |
| MarkRealized(assetId) | Settlement backend or ADMIN | PAYMENT_CONFIRMED → REALIZED |
| MarkEbrcEligible(assetId) | Settlement backend or ADMIN | REALIZED → EBRC_ELIGIBLE; SELF_CERTIFICATION_PENDING |
| CloseReceivable(assetId) | Settlement backend or ADMIN | EBRC_ELIGIBLE → CLOSED |
| RaiseDispute(assetId) | Assigned FINANCIER or ADMIN | FINANCED → DISPUTED |
| MarkOverdue(assetId) | Assigned FINANCIER or ADMIN | FINANCED → OVERDUE, only after the UTC due date ends |
| GetHistory(assetId) | Any recognized participant | Sanitized committed history with transaction IDs/timestamps |

DRAFT/SUBMITTED remain application states. The contract's verification attestation is an
explicit verifier decision, not automatic commercial or document verification. Exporter
registration cannot bypass it. Fingerprints remain reserved even after closure; CLOSED,
RELEASED, OVERDUE and DISPUTED have no outgoing transitions under the current PRD matrix.
There is no exposed generic transition function, delete, reset or arbitrary-state setter.

Registration and matching acceptance retries return the current asset without rewinding
state or writing another revision; original registration/lock transaction IDs are retained.
Conflicting retries fail. Payment event IDs are single-use across every asset; replay fails.
Mutations read/write the same asset/index keys so Fabric MVCC can invalidate competing
transactions at commit. A future gateway MUST check the commit status, not equate a
successful endorsement with a committed transaction. The unit race detector is not proof
of network-level concurrency behavior.

## Identity deployment profile

Every invocation checks CA-certified tradecred.org and tradecred.role attributes against
the caller MSP. Organization IDs in arguments cannot confer authority.

| Organization | MSP | Required role |
| --- | --- | --- |
| ORG_EXPORTER_ALPHA | ExporterAlphaMSP | EXPORTER |
| ORG_EXPORTER_BETA | ExporterBetaMSP | EXPORTER |
| ORG_BANK_CITI_DEMO | CitiDemoMSP | FINANCIER |
| ORG_BANK_NBFC_DEMO | NbfcDemoMSP | FINANCIER |
| ORG_SETTLEMENT_BANK | SettlementBankMSP | SETTLEMENT_OPERATOR |
| ORG_CONSORTIUM_ADMIN | ConsortiumAdminMSP | ADMIN |

Settlement also requires tradecred.settlement=true. Issue this attribute only to the
backend service certificate that invokes the contract AFTER verifying the signed bank
event using Milestone 6's controls; a general settlement-user certificate is insufficient.
The chaincode independently validates amount, currency, FINANCED state and event uniqueness.
It does not reimplement the webhook key registry, timestamp or nonce verification.

These are explicit demo MSP names, not claims about actual Drunix provisioning. All
endorsers must run the same participant/collection profile. Deployment must map the
consortium's real MSPs, restrict CA attribute issuance, install collection definitions,
configure endorsement and enable ledger history. Those network steps are Milestone 8.
Do not configure authority from peer-local environment variables, which could diverge.

## Confidential inputs and storage

Only registrationJSON and identifiers/hashes are ordinary transaction arguments.
registrationJSON accepts assetId, invoiceFingerprint, documentHash, exporterOrgId, currency,
and dueDate (YYYY-MM-DD). The backend generates the business fingerprint separately from
the PDF hash. No raw PDF, invoice number, buyer details or commercial terms are accepted
in the public registration object. Unknown fields, duplicate JSON fields, trailing JSON
and inputs exceeding 8192 bytes fail.

Sensitive data MUST be passed in the Fabric transient map (each value is raw UTF-8 JSON):

- invoice: assetId, amountMinor (positive signed 64-bit integer), currency, salt (64 lowercase
  hex characters generated from 32 random bytes). Required during verification, registration,
  locking and payment confirmation. Preserve these exact bytes and salt off-chain for retries.
- agreement: the TC-AGR-1 payload generated by the API, including assetId, exporterOrgId,
  financierOrgId, advanceAmountMinor, currency, discountRateBps, tenorDays, acceptedAt,
  termsVersion=demo-v1, assignmentStatus=CONSORTIUM_FINANCING_LOCK. Required for first lock.
  Hash the exact canonical payload bytes with SHA-256 before invoking LockReceivable.
- offer: offerId, expiresAt (RFC3339 with timezone). Required for first lock. Expiry must be
  after the proposal timestamp; acceptedAt must be within five minutes of that timestamp.
- payment: eventId, amountMinor, currency, reference, salt (fresh 32 random bytes as hex).
  Required for ConfirmPayment. Full invoice amount in its original currency is required;
  there is no FX conversion or partial repayment inference.

All salts originate at the client/backend; never generate randomness or read wall-clock
time inside chaincode. Chaincode uses the proposal timestamp. Currency exponents are an
embedded snapshot of the API's ISO-4217 library; parity tests detect drift. Value buckets
use integer arithmetic, including for amounts above JavaScript's safe integer range.

Verification commits only a salted private-details hash plus sanitized metadata. Registration
stores exact invoice bytes in _implicit_org_<ExporterMSP>. At lock, the contract checks
those bytes against the committed private-data hash and copies them, plus the agreement,
into the selected exporter/lender pair collection. collections_config.json defines all four
pairs with member-only reads/writes and exporter-plus-bank endorsement of private writes.
A losing financier's peers are not collection members. Public world state, history and
chaincode events contain no exact invoice amount, rate or remittance reference.

ConfirmPayment verifies the invoice using GetPrivateDataHash, so the settlement endorser
need not be a member of the exporter collection. Its transient proposal still contains
sensitive data: submit it only to authorized endorsers. The payment reference/payload is
not persisted as plaintext on-chain; only a salted commitment and a hash-keyed event
uniqueness index are written. The backend retains private settlement details off-chain.
No method returns private data. Private collection access and CA/MSP policies require
real-network verification before deployment; the test harness cannot enforce peer gossip.

## Failure and regulatory boundaries

Methods return stable error codes such as DUPLICATE_RECEIVABLE (with existing asset/status),
UNAUTHORIZED_ROLE, INVALID_STATE_TRANSITION, PAYMENT_EVENT_REPLAY, PAYMENT_AMOUNT_MISMATCH,
and PAYMENT_CURRENCY_MISMATCH. Storage/history failures are propagated; no fabricated
receipts or history are returned. Fabric discards failed simulations, and the gateway must
also reject invalid committed transactions. History-disabled peers return an error.

e-BRC status means eligibility/self-certification pending, never issuance. Token state does
not transfer legal ownership. This contract moves no funds and has no live banking calls.
A compromised authorized verifier or settlement backend remains a trust risk.

## References

- [Official Fabric contract API](https://github.com/hyperledger/fabric-contract-api-go)
- [Fabric private-data architecture](https://hyperledger-fabric.readthedocs.io/en/latest/private-data-arch.html)
- [Transient inputs and private hash checks](https://hyperledger-fabric.readthedocs.io/en/latest/private_data_tutorial.html)

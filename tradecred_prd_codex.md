# TradeCred — Product Requirements Document (PRD)

**Project:** TradeCred  
**Hackathon:** India Blockchain Forum — CHL-7007  
**Domain:** Blockchain / Fintech  
**Primary Theme:** Real Asset Tokenization  
**Secondary Themes:** Cross-Border Remittances, Financial Inclusion, Real-Time Payments  
**Prototype Type:** End-to-end hackathon MVP  
**Primary Platform:** NPCI Drunix  
**Target Users:** MSME exporters, financing institutions, authorized bank/remittance operators, consortium participants  
**Document Purpose:** This PRD is written to be directly usable by Codex or another coding agent for implementation.

---

# 1. Executive Summary

TradeCred is a permissioned trade-receivables infrastructure layer built on NPCI Drunix.

The prototype represents a verified trade receivable as a permissioned digital asset and tracks its lifecycle across verification, registration, financing, locking, payment confirmation, realization, and closure.

The core value proposition is not “put invoices on blockchain.” The prototype demonstrates how a consortium ledger can provide a shared financial state machine for:

1. deterministic invoice fingerprinting,
2. duplicate-financing detection across participating institutions,
3. receivable registration,
4. controlled financing state transitions,
5. auditable assignment/financing references,
6. privacy-preserving document handling,
7. authenticated settlement events,
8. cross-organization reconciliation.

The prototype must NOT claim that:
- it replaces TReDS,
- it guarantees prevention of off-network fraud,
- it directly executes foreign exchange settlement,
- it issues legal e-BRC certificates,
- a token automatically constitutes legal ownership of a receivable,
- it is production-ready or regulator-approved.

The prototype should clearly frame these as interoperable infrastructure primitives.

---

# 2. Problem Statement

Indian MSME exporters frequently sell goods using deferred-payment terms. This creates a working-capital gap between shipment and receipt of payment.

Receivable financing exists today, but the ecosystem can suffer from:

- fragmented verification,
- duplicate financing risk,
- inconsistent records across institutions,
- limited cross-platform visibility,
- manual reconciliation,
- document-heavy workflows,
- settlement-state ambiguity,
- lack of a shared source of truth.

A single receivable may be presented to multiple institutions. A blockchain network can prevent duplicate financing only inside the participating network. Therefore, TradeCred must be positioned as an interoperable shared registry that can expose pre-financing status through APIs to external systems.

---

# 3. Product Vision

Build a reusable receivables trust layer where authorized participants can answer:

- Has this invoice already been registered?
- Has it already been financed?
- Which institution currently owns or controls the financing state?
- Is the receivable locked?
- Has settlement been confirmed?
- Was the settlement event authenticated?
- What is the audit history of this receivable?

TradeCred should behave more like financial infrastructure than a consumer-facing marketplace.

---

# 4. Primary Demo Narrative

The final demo should show three scenarios.

## Scenario A — Happy Path

1. Exporter logs in.
2. Exporter uploads an invoice.
3. Backend normalizes invoice fields.
4. Backend generates:
   - documentHash
   - invoiceFingerprint
5. Duplicate check returns clear.
6. Invoice is verified.
7. Receivable is registered on Drunix.
8. Financing institutions can view sanitized eligible receivables.
9. One institution creates a financing offer.
10. Exporter accepts.
11. Receivable transitions to LOCKED.
12. Financing agreement hash is committed.
13. Mock payout is triggered.
14. Receivable transitions to FINANCED.
15. Authorized bank simulator sends a signed payment webhook.
16. Backend verifies signature, nonce, timestamp, amount, currency, and reference.
17. Drunix state transitions to PAYMENT_CONFIRMED.
18. Asset transitions to REALIZED.
19. System marks e-BRC status as ELIGIBLE / SELF_CERTIFICATION_PENDING.
20. Receivable closes.

## Scenario B — Duplicate Financing Attack

1. Same invoice is submitted again.
2. Canonical invoice fingerprint resolves to the same hash.
3. Registry API returns:
   - existing asset ID
   - current status
   - financed/locked flag
4. Financing attempt is rejected.
5. UI shows “Duplicate receivable already financed.”

## Scenario C — Fake Settlement Webhook

1. Unauthorized caller sends payment webhook.
2. Signature check fails.
3. Request is rejected.
4. No chain state changes.
5. Authorized simulator sends a valid signed event.
6. Backend verifies it.
7. State transition succeeds.

These three flows are mandatory.

---

# 5. Users and Roles

## 5.1 Exporter User

Capabilities:
- log in,
- create receivable,
- upload invoice document,
- see verification status,
- see duplicate-detection result,
- see financing offers,
- accept financing offer,
- see lifecycle timeline,
- see payment and settlement status.

## 5.2 Financier User

Represents:
- bank,
- NBFC,
- TReDS-like participant,
- institutional lender.

Capabilities:
- browse eligible receivables,
- inspect sanitized metadata,
- submit financing offer,
- check registry before financing,
- view assigned receivables,
- view status changes.

## 5.3 Bank / Settlement Operator

Capabilities:
- generate authenticated payment events,
- submit settlement webhook,
- view event verification result.

For prototype purposes this role is simulated.

## 5.4 Consortium Admin

Capabilities:
- view all ledger assets,
- view audit events,
- inspect network participants,
- view duplicate attempts,
- view failed payment-webhook attempts.

Admin must NOT be the primary user experience.

---

# 6. Scope

## 6.1 Must Have

- Monorepo or clearly organized multi-service repo.
- Next.js frontend.
- FastAPI backend.
- PostgreSQL for application metadata.
- Drunix integration abstraction.
- Local/mock ledger fallback if Drunix cannot run in CI.
- Chaincode state machine.
- Deterministic invoice fingerprinting.
- Document SHA-256 hashing.
- Duplicate-check API.
- Receivable registration.
- Financing offer workflow.
- Financing acceptance workflow.
- Financing lock.
- Agreement hash.
- Mock disbursement event.
- Signed settlement webhook.
- Signature verification.
- Replay protection.
- Payment amount and currency validation.
- Audit log.
- Role-based access.
- Seed/demo accounts.
- Seed/demo receivables.
- End-to-end demo script.
- Unit tests.
- Integration tests.
- README with setup steps.
- Docker Compose where practical.

## 6.2 Nice to Have

Only implement after Must Have is stable.

- basic risk score,
- suspicious invoice heuristics,
- event streaming,
- WebSocket UI updates,
- visual blockchain timeline,
- consortium network graph,
- Swagger screenshots,
- local Drunix explorer page,
- mocked NPCI payment adapter,
- PDF preview.

## 6.3 Explicit Non-Goals

Do not implement:
- cryptocurrency,
- stablecoin,
- public EVM smart contracts,
- retail token trading,
- real KYC,
- real remittance,
- real FEMA workflows,
- real RBI integrations,
- real DGFT/e-BRC issuance,
- actual bank fund transfer,
- secondary market,
- legal receivable assignment engine,
- real TReDS integration,
- production custody,
- production-grade HSM integration.

---

# 7. System Architecture

High-level architecture:

```text
┌──────────────────────────────┐
│         Next.js UI           │
│ Exporter / Financier / Admin │
└──────────────┬───────────────┘
               │ HTTPS
               ▼
┌──────────────────────────────┐
│         FastAPI API          │
│ Auth / Receivables / Offers  │
│ Registry / Settlement / Audit│
└──────────────┬───────────────┘
               │
     ┌─────────┼──────────┐
     │         │          │
     ▼         ▼          ▼
PostgreSQL   Drunix     Object Store
App State    Ledger     Invoice PDFs
             │
             ▼
       Chaincode / PDC
             │
     ┌───────┴────────┐
     ▼                ▼
Exporter Org      Financier Org

               ▲
               │ signed event
               │
┌──────────────┴───────────────┐
│ Mock Authorized Bank Adapter │
│ HMAC/RSA signed settlement   │
└──────────────────────────────┘
```

---

# 8. Recommended Repository Structure

Codex should create the following structure unless an existing repository dictates otherwise.

```text
tradecred/
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Makefile
├── docs/
│   ├── architecture.md
│   ├── demo-script.md
│   ├── api.md
│   ├── threat-model.md
│   └── regulatory-boundaries.md
├── apps/
│   ├── web/
│   │   ├── app/
│   │   ├── components/
│   │   ├── lib/
│   │   ├── public/
│   │   ├── package.json
│   │   └── ...
│   └── api/
│       ├── app/
│       │   ├── main.py
│       │   ├── core/
│       │   ├── api/
│       │   │   └── routes/
│       │   ├── models/
│       │   ├── schemas/
│       │   ├── services/
│       │   ├── repositories/
│       │   ├── integrations/
│       │   │   ├── ledger/
│       │   │   ├── payments/
│       │   │   └── storage/
│       │   └── security/
│       ├── tests/
│       ├── pyproject.toml
│       └── ...
├── blockchain/
│   ├── chaincode/
│   │   └── tradecred/
│   │       ├── main.go
│   │       ├── contract.go
│   │       ├── models.go
│   │       ├── validation.go
│   │       └── contract_test.go
│   ├── network/
│   │   ├── config/
│   │   ├── scripts/
│   │   └── README.md
│   └── mock-ledger/
├── services/
│   └── bank-simulator/
│       ├── app.py
│       ├── signing.py
│       ├── requirements.txt
│       └── README.md
├── scripts/
│   ├── seed_demo.py
│   ├── run_demo.sh
│   ├── generate_keys.py
│   └── reset_demo.sh
└── tests/
    └── e2e/
```

---

# 9. Core Domain Model

## 9.1 Receivable

Fields:

```text
id: UUID
asset_id: string
exporter_org_id: string
buyer_id: string
invoice_number: string
invoice_date: date
currency: string
face_value_minor: integer
due_date: date
document_hash: string
invoice_fingerprint: string
status: ReceivableStatus
owner_org_id: string | null
financing_agreement_hash: string | null
settlement_reference: string | null
ebrc_status: string | null
created_at: datetime
updated_at: datetime
```

## 9.2 Receivable Status Enum

```text
DRAFT
SUBMITTED
VERIFIED
REGISTERED
FINANCE_AVAILABLE
LOCKED
FINANCED
PAYMENT_CONFIRMED
REALIZED
EBRC_ELIGIBLE
CLOSED

REJECTED_DUPLICATE
RELEASED
OVERDUE
DISPUTED
```

State transitions must be validated server-side and in chaincode.

---

# 10. Deterministic Invoice Fingerprinting

A business-level fingerprint must be different from a file hash.

## 10.1 documentHash

Definition:

```text
SHA256(raw uploaded document bytes)
```

Purpose:
- integrity verification,
- prove same uploaded artifact.

## 10.2 invoiceFingerprint

Canonical input:

```json
{
  "version": "TC-FP-1",
  "exporterId": "...",
  "buyerId": "...",
  "invoiceNumber": "...",
  "currency": "EUR",
  "amountMinor": 1080000,
  "invoiceDate": "2026-09-21"
}
```

Normalization rules:

- trim whitespace,
- uppercase IDs,
- remove non-semantic spaces from invoice numbers,
- normalize invoice number to `[A-Z0-9]` where safe,
- ISO-4217 uppercase currency,
- convert amount to integer minor units,
- ISO date,
- serialize keys in fixed order,
- UTF-8 encode,
- hash with SHA-256.

Function:

```text
fingerprint = SHA256(canonical_json_bytes)
```

Required tests:
- whitespace variants produce same fingerprint,
- lowercase/uppercase identifier variants produce same fingerprint,
- different invoice amount produces different fingerprint,
- different invoice date produces different fingerprint,
- document changes do NOT affect business fingerprint,
- identical invoice metadata but different PDF produces same fingerprint and different documentHash.

---

# 11. Drunix Ledger Model

The implementation should target Drunix but keep a ledger abstraction so local development can continue with an in-memory or PostgreSQL mock ledger.

Define:

```python
class LedgerClient(Protocol):
    async def register_receivable(...)
    async def get_receivable(...)
    async def find_by_fingerprint(...)
    async def transition_receivable(...)
    async def lock_receivable(...)
    async def confirm_payment(...)
    async def get_history(...)
```

Implementations:

```text
DrunixLedgerClient
MockLedgerClient
```

The app must support:

```text
LEDGER_BACKEND=mock
LEDGER_BACKEND=drunix
```

This is mandatory so the prototype remains runnable even if Drunix setup fails on a judge's machine.

---

# 12. Drunix Global Ledger State

Only sanitized metadata should be globally available.

Recommended:

```json
{
  "assetId": "TC-82912",
  "invoiceFingerprint": "84afe1...",
  "documentHash": "8f3...",
  "status": "FINANCED",
  "exporterOrgId": "ORG_EXPORTER_001",
  "ownerOrgId": "ORG_BANK_B",
  "currency": "EUR",
  "faceValueBucket": "10000-25000",
  "dueDate": "2026-11-25",
  "agreementHash": "93fd...",
  "updatedAt": "..."
}
```

Do not expose buyer name, bank account, PDF, line items, discount rate, personal information, or commercial contract details in global state.

---

# 13. Private Data Collections

Use Fabric/Drunix private data patterns for confidential commercial information.

Private data may include:

```json
{
  "assetId": "TC-82912",
  "buyerName": "Example GmbH",
  "buyerTaxId": "DE...",
  "invoiceNumber": "INV-102",
  "exactFaceValueMinor": 1080000,
  "invoiceLineItems": [],
  "bankAccountReference": "...",
  "discountRateBps": 275,
  "documentStorageKey": "...",
  "riskAssessment": {},
  "commercialTerms": {}
}
```

Prototype collection strategy:

```text
ExporterBankCollection
```

Members:
- Exporter Org
- Financing Bank Org

Optional future:
- Regulator/Auditor collection
- Settlement Bank collection

---

# 14. Chaincode Requirements

Language: Go.

Contract name:

```text
TradeCredContract
```

Required chaincode functions:

```text
RegisterReceivable
GetReceivable
GetReceivableByFingerprint
VerifyReceivable
OpenForFinancing
LockReceivable
RecordFinancing
ReleaseLock
ConfirmPayment
MarkRealized
MarkEbrcEligible
CloseReceivable
RaiseDispute
MarkOverdue
GetHistory
```

## 14.1 RegisterReceivable

Input:
- assetId
- invoiceFingerprint
- documentHash
- sanitized metadata

Checks:
- fingerprint must not already exist in active registry,
- caller must have exporter/authorized registrar identity,
- required fields valid,
- initial state must be VERIFIED or REGISTERED according to final flow.

On duplicate:
- reject transaction,
- return existing asset/status.

## 14.2 LockReceivable

Checks:
- current status = FINANCE_AVAILABLE,
- no existing lock,
- offer valid,
- caller authorized.

Transition:

```text
FINANCE_AVAILABLE -> LOCKED
```

## 14.3 RecordFinancing

Checks:
- status = LOCKED,
- agreement hash exists,
- financing institution matches lock owner.

Transition:

```text
LOCKED -> FINANCED
```

## 14.4 ConfirmPayment

Must only be called by backend identity that has already validated signed payment event.

Checks:
- current status = FINANCED,
- expected amount matches,
- expected currency matches,
- event ID not already consumed.

Transition:

```text
FINANCED -> PAYMENT_CONFIRMED
```

## 14.5 GetHistory

Return ledger-state changes suitable for timeline UI.

---

# 15. Financing Workflow

## 15.1 FinancingOffer Model

```text
id: UUID
receivable_id: UUID
financier_org_id: string
advance_amount_minor: integer
discount_rate_bps: integer
tenor_days: integer
expires_at: datetime
status: OFFERED | ACCEPTED | REJECTED | EXPIRED
created_at: datetime
```

API logic:
- only verified/open receivables can receive offers,
- exporter can accept only one active offer,
- accepting one invalidates others,
- acceptance triggers ledger lock,
- agreement payload generated,
- SHA-256 agreement hash committed,
- local DB stores agreement payload.

Agreement must contain:

```json
{
  "agreementVersion": "TC-AGR-1",
  "assetId": "...",
  "exporterOrgId": "...",
  "financierOrgId": "...",
  "advanceAmountMinor": 975000,
  "currency": "INR",
  "discountRateBps": 250,
  "acceptedAt": "...",
  "termsVersion": "demo-v1"
}
```

---

# 16. Duplicate Registry API

External participants must be able to query a fingerprint before financing.

Endpoint:

```http
POST /api/v1/registry/check
```

Request:

```json
{
  "exporterId": "29ABCDE1234F1Z5",
  "buyerId": "DE123456789",
  "invoiceNumber": "INV-001",
  "currency": "EUR",
  "amountMinor": 1080000,
  "invoiceDate": "2026-09-21"
}
```

Response when clean:

```json
{
  "fingerprint": "...",
  "exists": false,
  "eligible": true
}
```

Response when financed:

```json
{
  "fingerprint": "...",
  "exists": true,
  "eligible": false,
  "assetId": "TC-82912",
  "status": "FINANCED",
  "reason": "RECEIVABLE_ALREADY_FINANCED"
}
```

Do not expose confidential commercial data from this endpoint.

---

# 17. Settlement Event Architecture

TradeCred must NOT directly move foreign currency.

A bank/remittance simulator sends an authenticated event to the TradeCred backend.

Flow:

```text
Mock AD Bank
   │
   │ Signed JSON
   ▼
POST /api/v1/settlement/events
   │
   ├─ validate timestamp
   ├─ validate nonce
   ├─ validate signature
   ├─ validate allowed bank ID
   ├─ validate amount
   ├─ validate currency
   ├─ validate receivable state
   ├─ validate event ID uniqueness
   │
   ▼
Ledger ConfirmPayment
   │
   ▼
PAYMENT_CONFIRMED
```

---

# 18. Payment Event Schema

```json
{
  "eventId": "PAY-829193",
  "assetId": "TC-82912",
  "bankId": "BANK_SETTLEMENT_01",
  "bankReference": "IRM-DEMO-938291",
  "amountMinor": 1080000,
  "currency": "EUR",
  "timestamp": "2026-11-20T14:32:01Z",
  "nonce": "a8912f..."
}
```

Security metadata:

```http
X-TradeCred-Signature
X-TradeCred-Key-Id
```

Prototype may use Ed25519 or RSA signatures.

Preferred:
- Ed25519 for simplicity and modern signing.

Do not rely on plain API keys as the only protection.

---

# 19. Webhook Security Requirements

Mandatory:

- asymmetric signature verification,
- allowed public-key registry,
- timestamp freshness check,
- nonce uniqueness,
- eventId uniqueness,
- replay prevention,
- amount validation,
- currency validation,
- asset state validation,
- bank ID validation,
- audit record on rejection.

Default timestamp tolerance:

```text
±5 minutes
```

Replay protection table:

```text
payment_events
- event_id unique
- nonce unique
- received_at
- verification_status
```

Invalid events must never modify ledger state.

---

# 20. e-BRC / Regulatory Representation

The system must model but NOT issue regulatory documents.

State:

```text
REALIZED
   ->
EBRC_ELIGIBLE
```

UI language:

```text
Inward payment confirmed
Remittance reference linked
Eligible for exporter e-BRC workflow
Self-certification pending
```

Never display:

```text
TradeCred issued e-BRC
```

Regulatory boundary documentation must state:
- cross-border FX is processed externally,
- TradeCred consumes settlement confirmation,
- AD banks/remittance providers remain regulated intermediaries,
- actual DGFT and RBI workflows are outside prototype scope.

---

# 21. Backend Technology

Recommended:

```text
Python 3.12+
FastAPI
Pydantic v2
SQLAlchemy 2
Alembic
PostgreSQL
httpx
PyJWT or python-jose
cryptography / PyNaCl
pytest
pytest-asyncio
ruff
mypy
```

Use async endpoints where appropriate.

---

# 22. Backend Modules

Recommended paths:

```text
apps/api/app/core/config.py
apps/api/app/core/database.py
apps/api/app/core/logging.py

apps/api/app/api/routes/auth.py
apps/api/app/api/routes/receivables.py
apps/api/app/api/routes/financing.py
apps/api/app/api/routes/registry.py
apps/api/app/api/routes/settlement.py
apps/api/app/api/routes/audit.py

apps/api/app/services/fingerprint_service.py
apps/api/app/services/receivable_service.py
apps/api/app/services/financing_service.py
apps/api/app/services/settlement_service.py
apps/api/app/services/audit_service.py

apps/api/app/integrations/ledger/base.py
apps/api/app/integrations/ledger/mock.py
apps/api/app/integrations/ledger/drunix.py

apps/api/app/security/signatures.py
apps/api/app/security/rbac.py
apps/api/app/security/replay.py
```

---

# 23. Backend REST API

Base path:

```text
/api/v1
```

## Authentication

```text
POST /auth/login
GET  /auth/me
```

Use seeded demo users.

## Receivables

```text
POST /receivables
GET /receivables
GET /receivables/{id}
POST /receivables/{id}/submit
POST /receivables/{id}/verify
POST /receivables/{id}/open-financing
GET /receivables/{id}/history
```

## Financing

```text
POST /receivables/{id}/offers
GET /receivables/{id}/offers
POST /offers/{offer_id}/accept
POST /offers/{offer_id}/reject
POST /receivables/{id}/disbursement/mock
```

## Registry

```text
POST /registry/check
GET /registry/fingerprint/{fingerprint}
```

## Settlement

```text
POST /settlement/events
GET /settlement/events/{event_id}
```

## Admin / Audit

```text
GET /audit/events
GET /audit/security-events
```

---

# 24. PostgreSQL Tables

Minimum:

```text
users
organizations
receivables
financing_offers
financing_agreements
documents
payment_events
audit_events
security_events
ledger_transactions
```

Do not duplicate entire blockchain state unnecessarily. Store transaction references and cache useful projection fields.

---

# 25. Frontend Technology

Recommended:

```text
Next.js 15+
TypeScript
Tailwind CSS
shadcn/ui
TanStack Query
Zod
React Hook Form
Recharts only if useful
```

Keep UI polished and enterprise-fintech oriented.

---

# 26. Required Frontend Screens

## 26.1 Login

Demo identities:

```text
exporter@tradecred.demo
bank@tradecred.demo
settlement@tradecred.demo
admin@tradecred.demo
```

## 26.2 Exporter Dashboard

Show:
- total receivables,
- available for finance,
- financed,
- settled,
- recent activity.

## 26.3 Create Receivable

Form:
- buyer ID,
- invoice number,
- invoice date,
- currency,
- face value,
- due date,
- PDF upload.

Display after upload:
- document hash,
- invoice fingerprint,
- duplicate-check result.

## 26.4 Receivable Detail

Sections:
- sanitized metadata,
- status badge,
- lifecycle timeline,
- document integrity hash,
- financing offers,
- ledger transaction IDs,
- settlement status.

## 26.5 Financier Marketplace

Cards/table:
- asset ID,
- currency,
- value range,
- due date,
- exporter consortium ID,
- status.

Do not expose confidential data.

## 26.6 Financing Offer Form

- advance amount,
- discount rate,
- expiry.

## 26.7 Registry Check

Standalone page where a bank can enter invoice metadata and query deduplication status.

This screen is highly important for the demo.

## 26.8 Settlement Simulator

Show:
- select asset,
- payment amount,
- currency,
- reference,
- “Send Valid Signed Event”
- “Send Invalid Signature”
- “Replay Event”

Show verification result.

## 26.9 Admin Audit Dashboard

Display:
- duplicate financing attempts,
- invalid settlement signatures,
- successful ledger transitions,
- participant activity.

---

# 27. UI Design Requirements

Visual language:
- institutional fintech,
- clean,
- modern,
- trustworthy,
- not crypto-themed.

Avoid:
- neon crypto aesthetics,
- coins,
- NFT imagery,
- speculative investment language.

Suggested page framing:

```text
TradeCred
Receivable Trust Infrastructure
Powered by Drunix
```

Core badges:

```text
VERIFIED
REGISTERED
AVAILABLE
LOCKED
FINANCED
PAYMENT CONFIRMED
REALIZED
CLOSED
DUPLICATE BLOCKED
SIGNATURE REJECTED
```

---

# 28. Object Storage

For prototype:
- local filesystem or MinIO.

Store:
- original invoice PDF.

Database stores:
- path/object key,
- document hash,
- metadata.

Ledger stores:
- hash only.

Never write raw PDFs into ledger state.

---

# 29. Authentication and RBAC

Seeded roles:

```text
EXPORTER
FINANCIER
SETTLEMENT_OPERATOR
ADMIN
```

Authorization examples:

- only exporter can create receivable,
- only authorized verifier/admin can verify,
- only financier can create offer,
- only receivable exporter can accept offer,
- only settlement endpoint identity can trigger payment confirmation,
- only admin can inspect security audit.

JWT is sufficient for hackathon.

---

# 30. Audit Logging

Every significant action must create an audit event.

Fields:

```text
id
event_type
actor_user_id
actor_org_id
asset_id
request_id
metadata_json
created_at
```

Events:

```text
RECEIVABLE_CREATED
DUPLICATE_CHECKED
DUPLICATE_REJECTED
RECEIVABLE_REGISTERED
OFFER_CREATED
OFFER_ACCEPTED
RECEIVABLE_LOCKED
FINANCING_RECORDED
PAYMENT_EVENT_RECEIVED
PAYMENT_SIGNATURE_REJECTED
PAYMENT_REPLAY_REJECTED
PAYMENT_CONFIRMED
RECEIVABLE_REALIZED
RECEIVABLE_CLOSED
```

---

# 31. Security Threat Model

Document at:

```text
docs/threat-model.md
```

Must include:

## Threat: Duplicate Financing

Mitigation:
- deterministic fingerprint,
- consortium registry lookup,
- lock state,
- single active financing state.

Residual risk:
- institutions outside network may not query registry.

## Threat: Invoice Document Modification

Mitigation:
- SHA-256 document hash,
- integrity check.

## Threat: Fake Settlement Event

Mitigation:
- asymmetric signature,
- trusted key registry,
- amount/currency validation.

## Threat: Replay Attack

Mitigation:
- unique event ID,
- unique nonce,
- timestamp TTL.

## Threat: Unauthorized State Transition

Mitigation:
- chaincode authorization,
- RBAC,
- explicit transition matrix.

## Threat: Sensitive Data Leakage

Mitigation:
- private data collections,
- sanitized world state,
- raw files off-chain.

## Threat: Ledger unavailable

Mitigation:
- idempotency,
- retry,
- local transaction status,
- no false success response.

---

# 32. State Transition Matrix

Implement centrally and duplicate enforcement in chaincode.

```text
DRAFT -> SUBMITTED
SUBMITTED -> VERIFIED
VERIFIED -> REGISTERED
REGISTERED -> FINANCE_AVAILABLE
FINANCE_AVAILABLE -> LOCKED
LOCKED -> FINANCED
LOCKED -> RELEASED
FINANCED -> PAYMENT_CONFIRMED
FINANCED -> OVERDUE
FINANCED -> DISPUTED
PAYMENT_CONFIRMED -> REALIZED
REALIZED -> EBRC_ELIGIBLE
EBRC_ELIGIBLE -> CLOSED
```

Invalid transitions must return HTTP 409.

---

# 33. Mock Payment / NPCI Adapter

Create:

```text
apps/api/app/integrations/payments/base.py
apps/api/app/integrations/payments/mock_npci.py
```

Interface:

```python
class PaymentAdapter(Protocol):
    async def disburse_financing(...)
    async def get_payment_status(...)
```

Mock behavior:
- generate mock payment transaction ID,
- persist status,
- simulate success.

UI must label it clearly:

```text
NPCI Payment Adapter — Sandbox Simulation
```

Do not claim live NPCI API connectivity unless actually provided during hackathon.

---

# 34. Optional Risk Engine

Only implement if core system is complete.

Rules-based v1 is sufficient.

Features:

```text
duplicate fingerprint
invoice amount z-score
buyer history
repeated bank account
invoice date inconsistency
unusual invoice frequency
document hash reuse
```

Output:

```json
{
  "riskScore": 0.18,
  "riskBand": "LOW",
  "reasons": [
    "No duplicate fingerprint",
    "Amount within exporter historical range"
  ]
}
```

Do not let ML block implementation of core blockchain flow.

---

# 35. Development Environment

Prefer:

```text
Node 20+
Python 3.12+
Go 1.22+
Docker Desktop
PostgreSQL 16
```

Environment file:

```text
DATABASE_URL=
JWT_SECRET=
LEDGER_BACKEND=mock
DRUNIX_GATEWAY_URL=
DRUNIX_CHANNEL=
DRUNIX_CHAINCODE_NAME=tradecred
DOCUMENT_STORAGE_PATH=
BANK_PUBLIC_KEY_PATH=
BANK_PRIVATE_KEY_PATH=
PAYMENT_TIMESTAMP_TOLERANCE_SECONDS=300
```

---

# 36. Docker Compose

docker-compose.yml should include where feasible:

```text
postgres
api
web
bank-simulator
```

Drunix network may remain separately bootstrapped due to complexity.

Document exact commands.

---

# 37. Makefile

Required targets:

```text
make install
make dev
make api
make web
make test
make test-api
make test-web
make test-chaincode
make lint
make format
make seed
make demo
make reset
```

---

# 38. Seed Data

Seed:

Organizations:

```text
ORG_EXPORTER_ALPHA
ORG_EXPORTER_BETA
ORG_BANK_CITI_DEMO
ORG_BANK_NBFC_DEMO
ORG_SETTLEMENT_BANK
```

Users:
- one for each role.

Receivables:

1. clean verified receivable,
2. finance-available receivable,
3. already financed receivable,
4. realized receivable,
5. duplicate-attempt fixture.

Use fake company names.

Do not use real confidential customer data.

---

# 39. Demo Fixture

Use a single flagship asset.

Example:

```text
Asset ID: TC-2026-001
Exporter: ORG_EXPORTER_ALPHA
Buyer: BUYER-DE-001
Invoice: EXP-2026-1042
Invoice Date: 2026-09-21
Currency: EUR
Face Value: EUR 10,800
Due Date: 2026-11-25
```

Financing:

```text
Advance: INR equivalent mock value
Discount: 2.5%
Financier: ORG_BANK_CITI_DEMO
```

Settlement reference:

```text
IRM-DEMO-938291
```

---

# 40. Automated Test Requirements

## 40.1 Fingerprinting

- same logical invoice -> same fingerprint,
- formatting variants -> same fingerprint,
- changed amount -> new fingerprint,
- changed date -> new fingerprint.

## 40.2 Duplicate Registry

- first registration succeeds,
- second registration fails,
- registry returns existing status,
- financed receivable returns eligible=false.

## 40.3 State Machine

- valid transitions succeed,
- invalid transitions fail,
- FINANCED cannot move back to AVAILABLE,
- CLOSED is terminal.

## 40.4 Financing

- multiple offers allowed before acceptance,
- only one offer accepted,
- accepting offer locks asset,
- other offers rejected/expired,
- agreement hash persisted.

## 40.5 Settlement Security

- valid signature accepted,
- invalid signature rejected,
- stale timestamp rejected,
- reused nonce rejected,
- reused event ID rejected,
- incorrect amount rejected,
- incorrect currency rejected,
- non-financed asset rejected.

## 40.6 API RBAC

- exporter cannot create bank offer,
- financier cannot accept on behalf of exporter,
- anonymous user cannot access protected endpoint.

## 40.7 Ledger

Mock ledger integration tests mandatory.

Drunix tests if environment available.

---

# 41. Chaincode Tests

Must test:

- duplicate fingerprint rejection,
- allowed transitions,
- unauthorized caller rejection,
- lock ownership,
- payment event uniqueness,
- history retrieval,
- terminal CLOSED state.

---

# 42. Error Model

Use structured errors.

Example:

```json
{
  "error": {
    "code": "RECEIVABLE_ALREADY_FINANCED",
    "message": "This receivable is already financed.",
    "details": {
      "assetId": "TC-2026-001",
      "status": "FINANCED"
    }
  }
}
```

Important error codes:

```text
DUPLICATE_RECEIVABLE
RECEIVABLE_ALREADY_FINANCED
INVALID_STATE_TRANSITION
UNAUTHORIZED_ROLE
INVALID_PAYMENT_SIGNATURE
PAYMENT_EVENT_REPLAY
PAYMENT_AMOUNT_MISMATCH
PAYMENT_CURRENCY_MISMATCH
LEDGER_UNAVAILABLE
```

---

# 43. Idempotency

Mandatory for:
- receivable registration,
- financing acceptance,
- payment event processing.

Use:
- unique constraints,
- idempotency keys where appropriate,
- deterministic event IDs.

No duplicate payment event may create multiple state transitions.

---

# 44. Observability

Prototype logging should include:
- request ID,
- user ID,
- org ID,
- asset ID,
- ledger transaction ID,
- event ID.

Never log:
- JWT,
- private keys,
- raw bank account details,
- raw document contents.

---

# 45. Regulatory Boundaries Document

Create:

```text
docs/regulatory-boundaries.md
```

Must state:

1. TradeCred is a prototype.
2. Foreign exchange movement is performed outside TradeCred.
3. Actual remittance is assumed to occur through regulated banking channels.
4. TradeCred consumes authenticated payment confirmation only.
5. e-BRC is not issued by TradeCred.
6. TradeCred may expose eligibility/status required for downstream workflows.
7. Token state is not itself a legal assignment.
8. Financing agreements remain conventional legal instruments.
9. Integration with banks, TReDS, DGFT, RBI, NPCI production infrastructure is future work.

---

# 46. Legal Ownership Representation

Do not use wording:

```text
The token legally transfers ownership.
```

Use:

```text
The ledger records the consortium-recognized financing and assignment state,
with a cryptographic hash of the underlying financing agreement.
```

Store:

```text
agreementHash
assignmentStatus
financierOrgId
acceptedAt
```

---

# 47. README Requirements

README must contain:

1. project summary,
2. problem,
3. solution,
4. architecture diagram,
5. features,
6. demo roles,
7. local installation,
8. environment setup,
9. mock-ledger mode,
10. Drunix mode,
11. database migration,
12. seed command,
13. run commands,
14. test commands,
15. demo walkthrough,
16. limitations,
17. regulatory disclaimer.

---

# 48. Implementation Milestones

Codex should implement in this order.

## Milestone 0 — Bootstrap

Create:
- repo structure,
- FastAPI project,
- Next.js project,
- PostgreSQL,
- Docker Compose,
- config,
- lint/test setup.

Acceptance:
- API health endpoint works,
- frontend loads,
- DB connection succeeds,
- `make test` succeeds.

## Milestone 1 — Domain and Auth

Implement:
- organizations,
- users,
- JWT,
- roles,
- receivable SQL models,
- migrations,
- seed users.

Acceptance:
- login works,
- role protected endpoints work.

## Milestone 2 — Fingerprinting and Documents

Implement:
- PDF upload,
- storage,
- document SHA-256,
- canonical fingerprint,
- tests.

Acceptance:
- same invoice variants generate same fingerprint,
- stored PDF integrity can be checked.

## Milestone 3 — Mock Ledger

Implement:
- LedgerClient interface,
- mock implementation,
- registry lookup,
- state machine,
- audit history.

Acceptance:
- asset registration and duplicate block work end-to-end.

## Milestone 4 — Receivables UI

Implement:
- exporter dashboard,
- create form,
- receivable detail,
- fingerprint display,
- lifecycle.

Acceptance:
- exporter can create, verify, register, and view asset.

## Milestone 5 — Financing

Implement:
- financier dashboard,
- offers,
- acceptance,
- locking,
- agreement hash,
- mock disbursement.

Acceptance:
- one lender can finance,
- second financing is blocked.

## Milestone 6 — Settlement Security

Implement:
- key generation,
- bank simulator,
- signed webhook,
- signature verification,
- replay protection,
- amount/currency validation.

Acceptance:
- valid settlement succeeds,
- fake event fails,
- replay fails.

## Milestone 7 — Drunix Chaincode

Implement:
- Go chaincode,
- state model,
- duplicate registry,
- transitions,
- tests.

Acceptance:
- contract tests pass.

## Milestone 8 — Drunix Gateway

Implement:
- DrunixLedgerClient,
- gateway config,
- network scripts,
- fallback to mock.

Acceptance:
- application can switch by env variable.

## Milestone 9 — Demo UX

Implement:
- registry checker,
- settlement simulator,
- admin security dashboard,
- polished status timeline,
- seeded flagship demo.

Acceptance:
- all three demo scenarios can be shown without manual DB edits.

## Milestone 10 — Hardening

Implement:
- integration tests,
- e2e tests,
- structured errors,
- logging,
- reset script,
- complete docs.

Acceptance:
- fresh clone -> documented commands -> working demo.

---

# 49. Codex Execution Rules

Codex should follow these rules during implementation:

1. Do not skip tests.
2. Do not leave placeholder TODOs in core flows.
3. Do not fake successful ledger writes.
4. Use mock ledger explicitly when Drunix is unavailable.
5. Never silently fall back from Drunix to mock in production mode.
6. Keep business logic out of route handlers.
7. Use typed service interfaces.
8. Keep state-transition logic centralized.
9. Do not store sensitive PDF contents on global ledger state.
10. Do not implement crypto/stablecoins.
11. Preserve regulatory boundary language.
12. Prefer simple, understandable code over over-engineering.
13. Every milestone must leave the repository runnable.
14. Run lint and tests after each milestone.
15. Document commands whenever adding infrastructure.

---

# 50. Definition of Done

Prototype is complete when:

- exporter can create a receivable,
- invoice fingerprint is deterministic,
- duplicate receivable is detected,
- receivable can be registered,
- financier can submit offer,
- exporter can accept exactly one offer,
- receivable becomes locked,
- financing is recorded,
- agreement hash exists,
- mock payout exists,
- unauthorized duplicate financing is blocked,
- invalid settlement webhook is rejected,
- replayed event is rejected,
- valid signed settlement succeeds,
- receivable becomes realized,
- e-BRC state is represented safely,
- full lifecycle is visible in UI,
- audit log records important actions,
- mock ledger works,
- Drunix chaincode exists,
- Drunix client path exists,
- automated tests pass,
- README documents full setup,
- demo can be reset and replayed.

---

# 51. Hackathon Demo Script

## Opening

“TradeCred is a Drunix-based shared receivables trust layer for MSME trade finance. We use tokenization not to create a speculative asset, but to establish a shared, auditable financing and settlement state across institutions.”

## Demo 1

- Log in as exporter.
- Upload invoice.
- Show fingerprint.
- Show clear registry result.
- Register.
- Open for financing.
- Switch to bank.
- Submit offer.
- Switch to exporter.
- Accept.
- Show LOCKED -> FINANCED.
- Show agreement hash.

## Demo 2

- Open registry checker.
- Enter same invoice.
- Show FINANCED.
- Try financing again.
- Show blocked result.

Narration:

“TradeCred only guarantees this across participating institutions. The registry API is designed so banks or TReDS platforms can query this state before disbursement.”

## Demo 3

- Open settlement simulator.
- Send invalid signature.
- Show rejection.
- Send replay event.
- Show rejection.
- Send valid event.
- Show PAYMENT_CONFIRMED -> REALIZED.

Narration:

“TradeCred does not execute forex movement. It consumes an authenticated payment event from a regulated settlement participant and updates the receivable state.”

## Close

- Show audit timeline.
- Show architecture.
- Show Drunix ledger state versus private data.

---

# 52. Submission Copy Reference

## Proposal Title

**TradeCred — A Drunix-Based Tokenized Receivables & Settlement Infrastructure for MSME Trade Finance**

## One-Line Description

A permissioned receivables trust layer that enables deterministic invoice deduplication, institutional financing locks, auditable assignment state, and authenticated settlement events using Drunix.

---

# 53. Final Product Principles

TradeCred must optimize for:

- implementability,
- financial-infrastructure realism,
- permissioned privacy,
- shared state,
- security,
- auditability,
- regulatory restraint,
- demo clarity.

The prototype wins by demonstrating a realistic enterprise workflow, not by maximizing the number of buzzwords.

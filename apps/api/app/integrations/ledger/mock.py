"""PostgreSQL-backed simulation. Never represents a Drunix transaction."""

import hashlib
import re
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from iso4217 import Currency
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.integrations.ledger.base import (
    LedgerActor,
    LedgerAsset,
    LedgerHistoryEntry,
    LedgerReceipt,
    Registration,
)
from app.models.domain import Organization, OrganizationType, Role
from app.models.domain import ReceivableStatus as Status
from app.models.ledger import LedgerTransaction, MockLedgerAsset, MockLedgerPrivate
from app.services.fingerprint_service import normalize_currency
from app.services.state_machine import require_transition


def value_bucket(amount_minor: int, currency: str) -> str:
    exponent = Currency(normalize_currency(currency)).exponent
    assert isinstance(exponent, int)
    major = Decimal(amount_minor) / (10**exponent)
    for lower, upper in ((0, 10000), (10000, 25000), (25000, 100000), (100000, 1000000)):
        if lower <= major < upper:
            return f"{lower}-{upper}"
    return "1000000+"


class MockLedgerClient:
    def __init__(self, session: AsyncSession, actor: LedgerActor) -> None:
        self.session = session
        self.actor = actor

    async def _serialize(self, key: str) -> None:
        lock_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
        await self.session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})

    async def _locked_asset(self, asset_id: str) -> MockLedgerAsset:
        asset = await self.session.scalar(
            select(MockLedgerAsset)
            .where(MockLedgerAsset.asset_id == asset_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if asset is None:
            raise APIError(404, "ASSET_NOT_FOUND", "Ledger asset not found.")
        return asset

    def _exporter(self, exporter_org_id: str) -> None:
        if self.actor.role != Role.EXPORTER or self.actor.organization_id != exporter_org_id:
            raise APIError(
                403, "UNAUTHORIZED_ROLE", "Only the receivable exporter may perform this action."
            )

    def _financier(self, asset: MockLedgerAsset) -> None:
        if self.actor.role != Role.FINANCIER or self.actor.organization_id != asset.owner_org_id:
            raise APIError(403, "UNAUTHORIZED_ROLE", "Only the lock owner may perform this action.")

    async def _record(
        self, asset: MockLedgerAsset, previous: Status, event_id: str | None = None
    ) -> LedgerReceipt:
        transaction_id = "MOCK-" + uuid4().hex
        self.session.add(
            LedgerTransaction(
                transaction_id=transaction_id,
                asset_id=asset.asset_id,
                revision=asset.revision,
                from_status=previous,
                to_status=asset.status,
                actor_org_id=self.actor.organization_id,
                payment_event_id=event_id,
                backend="mock",
            )
        )
        await self.session.flush()
        return LedgerReceipt(asset=LedgerAsset.model_validate(asset), transaction_id=transaction_id)

    async def register_receivable(self, registration: Registration) -> LedgerReceipt:
        if self.actor.role != Role.ADMIN:
            self._exporter(registration.exporter_org_id)
        org = await self.session.get(Organization, registration.exporter_org_id)
        if org is None or org.organization_type != OrganizationType.EXPORTER:
            raise APIError(422, "INVALID_EXPORTER", "Exporter organization is not registered.")
        normalize_currency(registration.currency)
        await self._serialize("asset:" + registration.asset_id)
        await self._serialize("fingerprint:" + registration.invoice_fingerprint)
        existing = await self.session.scalar(
            select(MockLedgerAsset).where(
                MockLedgerAsset.invoice_fingerprint == registration.invoice_fingerprint
            )
        )
        if existing is not None and existing.asset_id != registration.asset_id:
            raise APIError(
                409,
                "DUPLICATE_RECEIVABLE",
                "Fingerprint is already registered.",
                {
                    "assetId": existing.asset_id,
                    "status": existing.status,
                },
            )
        same_id = await self.session.get(MockLedgerAsset, registration.asset_id)
        if same_id is not None:
            private = await self.session.get(MockLedgerPrivate, registration.asset_id)
            expected = registration.model_dump(exclude={"face_value_minor"})
            if (
                any(getattr(same_id, key) != value for key, value in expected.items())
                or private is None
                or private.face_value_minor != registration.face_value_minor
            ):
                raise APIError(
                    409,
                    "REGISTRATION_CONFLICT",
                    "Asset ID was used for different registration data.",
                )
            first = await self.session.scalar(
                select(LedgerTransaction).where(
                    LedgerTransaction.asset_id == same_id.asset_id,
                    LedgerTransaction.revision == 1,
                )
            )
            if first is None:
                raise APIError(503, "LEDGER_UNAVAILABLE", "Mock ledger history is inconsistent.")
            return LedgerReceipt(
                asset=LedgerAsset.model_validate(same_id),
                transaction_id=first.transaction_id,
                replayed=True,
            )
        asset = MockLedgerAsset(
            **registration.model_dump(exclude={"face_value_minor"}),
            face_value_bucket=value_bucket(registration.face_value_minor, registration.currency),
            status=Status.REGISTERED,
            revision=1,
            updated_at=datetime.now(UTC),
        )
        self.session.add(asset)
        await self.session.flush()
        self.session.add(
            MockLedgerPrivate(
                asset_id=asset.asset_id, face_value_minor=registration.face_value_minor
            )
        )
        return await self._record(asset, Status.VERIFIED)

    async def get_receivable(self, asset_id: str) -> LedgerAsset | None:
        asset = await self.session.get(MockLedgerAsset, asset_id)
        return LedgerAsset.model_validate(asset) if asset is not None else None

    async def find_by_fingerprint(self, fingerprint: str) -> LedgerAsset | None:
        asset = await self.session.scalar(
            select(MockLedgerAsset).where(MockLedgerAsset.invoice_fingerprint == fingerprint)
        )
        return LedgerAsset.model_validate(asset) if asset is not None else None

    async def transition_receivable(self, asset_id: str, target: Status) -> LedgerReceipt:
        asset = await self._locked_asset(asset_id)
        previous = Status(asset.status)
        require_transition(previous, target)
        if target in {Status.LOCKED, Status.PAYMENT_CONFIRMED}:
            raise APIError(
                409, "GUARDED_LEDGER_OPERATION", "Use the dedicated validated ledger operation."
            )
        if target == Status.FINANCE_AVAILABLE:
            self._exporter(asset.exporter_org_id)
        elif target in {Status.FINANCED, Status.RELEASED}:
            self._financier(asset)
            if not asset.agreement_hash:
                raise APIError(409, "AGREEMENT_REQUIRED", "A financing agreement hash is required.")
        elif target in {Status.OVERDUE, Status.DISPUTED}:
            if self.actor.role != Role.ADMIN:
                self._financier(asset)
        elif target in {Status.REALIZED, Status.EBRC_ELIGIBLE, Status.CLOSED}:
            if self.actor.role not in {Role.SETTLEMENT_OPERATOR, Role.ADMIN}:
                raise APIError(
                    403, "UNAUTHORIZED_ROLE", "A settlement or administrator identity is required."
                )
        else:
            raise APIError(
                409, "INVALID_STATE_TRANSITION", "This transition is not a ledger operation."
            )
        asset.status = target
        if target == Status.RELEASED:
            asset.owner_org_id = None
        asset.revision += 1
        asset.updated_at = datetime.now(UTC)
        return await self._record(asset, previous)

    async def lock_receivable(
        self, asset_id: str, financier_org_id: str, agreement_hash: str
    ) -> LedgerReceipt:
        asset = await self._locked_asset(asset_id)
        self._exporter(asset.exporter_org_id)
        require_transition(Status(asset.status), Status.LOCKED)
        financier = await self.session.get(Organization, financier_org_id)
        if financier is None or financier.organization_type != OrganizationType.FINANCIER:
            raise APIError(422, "INVALID_FINANCIER", "Financier organization is not registered.")
        if not re.fullmatch(r"[a-f0-9]{64}", agreement_hash):
            raise APIError(422, "INVALID_AGREEMENT_HASH", "A SHA-256 agreement hash is required.")
        if asset.owner_org_id is not None:
            raise APIError(409, "RECEIVABLE_ALREADY_LOCKED", "Receivable already has an owner.")
        previous = Status(asset.status)
        asset.status = Status.LOCKED
        asset.owner_org_id = financier_org_id
        asset.agreement_hash = agreement_hash
        asset.revision += 1
        asset.updated_at = datetime.now(UTC)
        return await self._record(asset, previous)

    async def confirm_payment(
        self, asset_id: str, event_id: str, amount_minor: int, currency: str, reference: str
    ) -> LedgerReceipt:
        # Internal adapter contract only. No settlement endpoint is exposed in Milestone 3.
        # The future settlement service must authenticate the signed event before this call.
        if self.actor.role != Role.SETTLEMENT_OPERATOR:
            raise APIError(403, "UNAUTHORIZED_ROLE", "Settlement identity required.")
        if (
            not event_id.strip()
            or len(event_id) > 160
            or not reference.strip()
            or len(reference) > 160
        ):
            raise APIError(422, "INVALID_PAYMENT_EVENT", "Event ID and reference are required.")
        await self._serialize("payment:" + event_id)
        existing = await self.session.scalar(
            select(LedgerTransaction).where(LedgerTransaction.payment_event_id == event_id)
        )
        if existing is not None:
            raise APIError(409, "PAYMENT_EVENT_REPLAY", "Payment event was already consumed.")
        asset = await self._locked_asset(asset_id)
        require_transition(Status(asset.status), Status.PAYMENT_CONFIRMED)
        private = await self.session.get(MockLedgerPrivate, asset_id)
        if private is None:
            raise APIError(503, "LEDGER_UNAVAILABLE", "Mock ledger private data is unavailable.")
        if type(amount_minor) is not int or amount_minor != private.face_value_minor:
            raise APIError(409, "PAYMENT_AMOUNT_MISMATCH", "Payment amount does not match.")
        if currency != asset.currency:
            raise APIError(409, "PAYMENT_CURRENCY_MISMATCH", "Payment currency does not match.")
        private.settlement_reference = reference
        previous = Status(asset.status)
        asset.status = Status.PAYMENT_CONFIRMED
        asset.revision += 1
        asset.updated_at = datetime.now(UTC)
        return await self._record(asset, previous, event_id)

    async def get_history(self, asset_id: str) -> list[LedgerHistoryEntry]:
        rows = await self.session.scalars(
            select(LedgerTransaction)
            .where(LedgerTransaction.asset_id == asset_id)
            .order_by(LedgerTransaction.revision)
        )
        return [LedgerHistoryEntry.model_validate(row) for row in rows]

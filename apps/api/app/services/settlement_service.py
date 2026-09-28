import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import APIError
from app.integrations.ledger.base import LedgerActor
from app.integrations.ledger.drunix import DrunixLedgerClient
from app.integrations.ledger.factory import create_ledger_client
from app.models.domain import (
    Organization,
    OrganizationType,
    Receivable,
    ReceivableStatus,
    Role,
    User,
)
from app.models.settlement import PaymentEvent, SecurityEvent
from app.schemas.settlement import PaymentEventInput, PaymentEventView
from app.security.signatures import verify_signature
from app.services.audit_service import record_audit
from app.services.ledger_mode import require_ledger_mode


def unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def event_view(event: PaymentEvent) -> PaymentEventView:
    return PaymentEventView(
        event_id=event.event_id,
        asset_id=event.asset_id,
        transaction_id=event.transaction_id,
        received_at=event.received_at,
        backend=event.backend,
    )


class SettlementService:
    def __init__(self, session: AsyncSession, settings: Settings, request_id: str) -> None:
        self.session = session
        self.settings = settings
        self.request_id = request_id

    async def reject(self, code: str, digest: str) -> None:
        await self.session.rollback()
        event_type = {
            "INVALID_PAYMENT_SIGNATURE": "PAYMENT_SIGNATURE_REJECTED",
            "PAYMENT_EVENT_REPLAY": "PAYMENT_REPLAY_REJECTED",
        }.get(code, "PAYMENT_EVENT_REJECTED")
        self.session.add(
            SecurityEvent(
                event_type=event_type,
                reason=code,
                request_id=self.request_id,
                payload_hash=digest,
            )
        )
        await self.session.commit()

    async def process(self, body: bytes, signature: str, key_id: str) -> PaymentEventView:
        digest = hashlib.sha256(body).hexdigest()
        try:
            result = await self._process(body, signature, key_id, digest)
            await self.session.commit()
            return result
        except APIError as exc:
            try:
                await self.reject(exc.code, digest)
            except SQLAlchemyError as audit_exc:
                await self.session.rollback()
                raise APIError(
                    503, "SETTLEMENT_UNAVAILABLE", "Security audit unavailable."
                ) from audit_exc
            raise
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise APIError(
                503, "SETTLEMENT_UNAVAILABLE", "Settlement storage unavailable."
            ) from exc

    async def _process(
        self,
        body: bytes,
        signature: str,
        key_id: str,
        digest: str,
    ) -> PaymentEventView:
        if len(body) > 8192:
            raise APIError(413, "INVALID_PAYMENT_EVENT", "Payment event exceeds 8192 bytes.")
        trusted = self.settings.bank_trusted_keys.get(key_id)
        if trusted is None:
            raise APIError(401, "INVALID_PAYMENT_SIGNATURE", "Payment signature rejected.")
        verify_signature(body, signature, trusted.public_key_path)
        try:
            payload = PaymentEventInput.model_validate(
                json.loads(body, object_pairs_hook=unique_fields)
            )
        except (ValueError, UnicodeError, ValidationError, RecursionError) as exc:
            raise APIError(422, "INVALID_PAYMENT_EVENT", "Invalid payment event schema.") from exc
        if payload.bankId != trusted.bank_id:
            raise APIError(403, "UNTRUSTED_BANK", "Key is not authorized for this bank.")
        if (
            abs((datetime.now(UTC) - payload.timestamp).total_seconds())
            > self.settings.payment_timestamp_tolerance_seconds
        ):
            raise APIError(
                409, "PAYMENT_TIMESTAMP_EXPIRED", "Payment timestamp is outside tolerance."
            )
        user = await self.session.scalar(
            select(User)
            .join(Organization)
            .where(
                User.organization_id == trusted.organization_id,
                Organization.organization_type == OrganizationType.SETTLEMENT_BANK,
                User.role == Role.SETTLEMENT_OPERATOR,
                User.is_active.is_(True),
            )
            .order_by(User.id)
        )
        if user is None:
            raise APIError(403, "UNTRUSTED_BANK", "No active settlement identity for this bank.")
        actor = LedgerActor(user_id=user.id, organization_id=user.organization_id, role=user.role)
        # Global event and nonce locks also serialize replays targeting different assets.
        for key in sorted(("event:" + payload.eventId, "nonce:" + payload.nonce)):
            lock_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
            await self.session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})
        existing = await self.session.scalar(
            select(PaymentEvent).where(
                or_(
                    PaymentEvent.event_id == payload.eventId,
                    PaymentEvent.nonce == payload.nonce,
                )
            )
        )
        if existing:
            raise APIError(409, "PAYMENT_EVENT_REPLAY", "Payment event or nonce already consumed.")
        row = await self.session.scalar(
            select(Receivable)
            .where(
                Receivable.asset_id == payload.assetId,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise APIError(404, "ASSET_NOT_FOUND", "Receivable not found.")
        require_ledger_mode(row, self.settings)
        if row.status != ReceivableStatus.FINANCED:
            raise APIError(
                409, "INVALID_STATE_TRANSITION", "Only financed receivables accept settlement."
            )
        if payload.amountMinor != row.face_value_minor:
            raise APIError(409, "PAYMENT_AMOUNT_MISMATCH", "Payment must match full invoice value.")
        if payload.currency != row.currency:
            raise APIError(
                409, "PAYMENT_CURRENCY_MISMATCH", "Payment currency does not match invoice."
            )
        ledger = create_ledger_client(self.session, self.settings, actor)
        asset = await ledger.get_receivable(payload.assetId)
        recovering = (
            asset is not None
            and isinstance(ledger, DrunixLedgerClient)
            and await ledger.recovery_matches("payment:" + payload.eventId, asset)
        )
        if not recovering and (
            asset is None
            or (
                asset.status != row.status
                or asset.owner_org_id != row.owner_org_id
                or asset.agreement_hash != row.financing_agreement_hash
                or asset.invoice_fingerprint != row.invoice_fingerprint
                or asset.exporter_org_id != row.exporter_org_id
                or asset.currency != row.currency
            )
        ):
            raise APIError(503, "LEDGER_UNAVAILABLE", "Ledger projection is inconsistent.")
        receipt = await ledger.confirm_payment(
            payload.assetId,
            payload.eventId,
            payload.amountMinor,
            payload.currency,
            payload.bankReference,
        )
        row.status = receipt.asset.status
        row.settlement_reference = payload.bankReference
        event = PaymentEvent(
            event_id=payload.eventId,
            nonce=payload.nonce,
            receivable_id=row.id,
            bank_org_id=actor.organization_id,
            asset_id=payload.assetId,
            payload_hash=digest,
            key_id=key_id,
            transaction_id=receipt.transaction_id,
            backend=receipt.asset.backend,
            received_at=datetime.now(UTC),
        )
        self.session.add(event)
        for event_type in ("PAYMENT_EVENT_RECEIVED", "PAYMENT_CONFIRMED"):
            record_audit(
                self.session,
                event_type,
                actor_user_id=actor.user_id,
                actor_org_id=actor.organization_id,
                request_id=self.request_id,
                receivable_id=row.id,
                asset_id=row.asset_id,
                metadata={
                    "eventId": payload.eventId,
                    "transactionId": receipt.transaction_id,
                    "backend": receipt.asset.backend,
                },
            )
        await self.session.flush()
        return event_view(event)

    async def get(self, event_id: str, user: User) -> PaymentEventView:
        query = select(PaymentEvent).join(Receivable)
        if user.role == Role.EXPORTER:
            query = query.where(Receivable.exporter_org_id == user.organization_id)
        elif user.role == Role.FINANCIER:
            query = query.where(Receivable.owner_org_id == user.organization_id)
        elif user.role == Role.SETTLEMENT_OPERATOR:
            query = query.where(PaymentEvent.bank_org_id == user.organization_id)
        elif user.role != Role.ADMIN:
            raise APIError(403, "UNAUTHORIZED_ROLE", "Role cannot inspect settlement.")
        event = await self.session.scalar(query.where(PaymentEvent.event_id == event_id))
        if event is None:
            raise APIError(404, "PAYMENT_EVENT_NOT_FOUND", "Payment event not found.")
        return event_view(event)

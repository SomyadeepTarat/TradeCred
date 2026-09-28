from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from iso4217 import Currency
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import APIError
from app.integrations.ledger.base import LedgerActor, LedgerClient
from app.integrations.ledger.drunix import DrunixLedgerClient
from app.integrations.ledger.factory import create_ledger_client
from app.integrations.payments.base import PaymentAdapter
from app.integrations.payments.mock_npci import MockNPCIPaymentAdapter
from app.models.domain import Receivable, Role
from app.models.domain import ReceivableStatus as S
from app.models.financing import FinancingAgreement, FinancingOffer
from app.schemas.financing import (
    AgreementView,
    FinancingResult,
    FinancingView,
    OfferInput,
    OfferView,
)
from app.services.agreement_service import agreement_hash, agreement_payload, canonical_agreement
from app.services.audit_service import record_audit
from app.services.fingerprint_service import amount_to_minor
from app.services.ledger_mode import require_ledger_mode
from app.services.receivable_access import financier_scope


class FinancingService:
    def __init__(
        self, session: AsyncSession, settings: Settings, actor: LedgerActor, request_id: str
    ) -> None:
        self.session, self.settings, self.actor, self.request_id = (
            session,
            settings,
            actor,
            request_id,
        )
        self.payment: PaymentAdapter = MockNPCIPaymentAdapter(session)
        self.audit_target: tuple[UUID, str | None] | None = None

    @asynccontextmanager
    async def _transaction(self) -> AsyncIterator[None]:
        try:
            yield
            await self.session.commit()
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise APIError(
                503,
                "FINANCING_UNAVAILABLE",
                "The financing transaction could not be confirmed. Refresh before retrying.",
            ) from exc
        except APIError as exc:
            await self.session.rollback()
            if self.audit_target and exc.code in {
                "RECEIVABLE_ALREADY_LOCKED",
                "RECEIVABLE_ALREADY_FINANCED",
            }:
                record_audit(
                    self.session,
                    "DUPLICATE_FINANCING_BLOCKED",
                    actor_user_id=self.actor.user_id,
                    actor_org_id=self.actor.organization_id,
                    request_id=self.request_id,
                    receivable_id=self.audit_target[0],
                    asset_id=self.audit_target[1],
                    metadata={"reason": exc.code},
                )
                try:
                    await self.session.commit()
                except SQLAlchemyError as audit_error:
                    await self.session.rollback()
                    raise APIError(
                        503,
                        "FINANCING_UNAVAILABLE",
                        "Could not record the rejected financing attempt.",
                    ) from audit_error
            raise
        except Exception:
            await self.session.rollback()
            raise

    def _role(self, role: Role) -> None:
        if self.actor.role != role:
            raise APIError(403, "UNAUTHORIZED_ROLE", f"This action requires the {role} role.")

    def _ledger(self) -> LedgerClient:
        return create_ledger_client(self.session, self.settings, self.actor)

    async def _row(self, receivable_id: UUID, *, lock: bool = False) -> Receivable:
        query = select(Receivable).where(Receivable.id == receivable_id)
        if self.actor.role == Role.EXPORTER:
            query = query.where(Receivable.exporter_org_id == self.actor.organization_id)
        elif self.actor.role == Role.FINANCIER:
            query = query.where(financier_scope(self.actor.organization_id))
        elif self.actor.role != Role.ADMIN:
            raise APIError(403, "UNAUTHORIZED_ROLE", "This role cannot access financing.")
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        row = await self.session.scalar(query)
        if row is None:
            raise APIError(404, "RECEIVABLE_NOT_FOUND", "Receivable not found.")
        require_ledger_mode(row, self.settings)
        self.audit_target = (row.id, row.asset_id)
        return row

    def _audit(self, event: str, row: Receivable, **metadata: str) -> None:
        record_audit(
            self.session,
            event,
            actor_user_id=self.actor.user_id,
            actor_org_id=self.actor.organization_id,
            request_id=self.request_id,
            receivable_id=row.id,
            asset_id=row.asset_id,
            metadata=metadata,
        )

    async def _asset(
        self, ledger: LedgerClient, row: Receivable, recovery_key: str | None = None
    ) -> bool:
        if not row.asset_id or not row.invoice_fingerprint:
            raise APIError(
                409, "ASSET_NOT_REGISTERED", "Register and open the receivable before financing."
            )
        asset = await ledger.find_by_fingerprint(row.invoice_fingerprint)
        if asset is not None and isinstance(ledger, DrunixLedgerClient) and recovery_key:
            if await ledger.recovery_matches(recovery_key, asset):
                return True
        if asset is None or (
            asset.asset_id,
            asset.exporter_org_id,
            asset.currency,
            asset.status,
            asset.owner_org_id,
            asset.agreement_hash,
        ) != (
            row.asset_id,
            row.exporter_org_id,
            row.currency,
            row.status,
            row.owner_org_id,
            row.financing_agreement_hash,
        ):
            raise APIError(
                503,
                "LEDGER_STATE_MISMATCH",
                "Ledger and application state do not agree; financing is unavailable.",
            )
        return False

    def _open(self, row: Receivable) -> None:
        if row.status != S.FINANCE_AVAILABLE:
            code = (
                "RECEIVABLE_ALREADY_LOCKED"
                if row.status == S.LOCKED
                else "RECEIVABLE_ALREADY_FINANCED"
                if row.status
                in {
                    S.FINANCED,
                    S.PAYMENT_CONFIRMED,
                    S.REALIZED,
                    S.EBRC_ELIGIBLE,
                    S.CLOSED,
                    S.OVERDUE,
                    S.DISPUTED,
                }
                else "RECEIVABLE_NOT_OPEN"
            )
            raise APIError(409, code, "This receivable is not available for new financing.")

    def _offer_view(self, offer: FinancingOffer) -> OfferView:
        status = (
            "EXPIRED"
            if offer.status == "OFFERED" and offer.expires_at <= datetime.now(UTC)
            else offer.status
        )
        amount = format(
            Decimal(offer.advance_amount_minor).scaleb(
                -int(Currency(offer.currency).exponent or 0)
            ),
            "f",
        )
        return OfferView(
            id=offer.id,
            receivable_id=offer.receivable_id,
            financier_org_id=offer.financier_org_id,
            advance_amount=amount,
            currency=offer.currency,
            discount_rate_bps=offer.discount_rate_bps,
            tenor_days=offer.tenor_days,
            expires_at=offer.expires_at,
            status=cast(Literal["OFFERED", "ACCEPTED", "REJECTED", "EXPIRED"], status),
            created_at=offer.created_at,
        )

    async def _offers(self, row: Receivable) -> list[FinancingOffer]:
        return list(
            await self.session.scalars(
                select(FinancingOffer)
                .where(FinancingOffer.receivable_id == row.id)
                .order_by(FinancingOffer.created_at, FinancingOffer.id)
            )
        )

    def _expire(self, row: Receivable, offers: list[FinancingOffer]) -> None:
        now = datetime.now(UTC)
        for offer in offers:
            if offer.status == "OFFERED" and offer.expires_at <= now:
                offer.status = "EXPIRED"
                self._audit("OFFER_EXPIRED", row, offerId=str(offer.id))

    async def create_offer(self, receivable_id: UUID, payload: OfferInput) -> OfferView:
        self._role(Role.FINANCIER)
        async with self._transaction():
            row = await self._row(receivable_id, lock=True)
            ledger = self._ledger()
            await self._asset(ledger, row)
            self._open(row)
            if payload.expires_at <= datetime.now(UTC):
                raise APIError(422, "OFFER_EXPIRED", "Offer expiry must be in the future.")
            if payload.currency != row.currency:
                raise APIError(
                    422,
                    "OFFER_CURRENCY_MISMATCH",
                    "Use the invoice currency; no FX conversion is performed.",
                )
            try:
                amount = amount_to_minor(payload.advance_amount, payload.currency)
            except ValueError as exc:
                raise APIError(422, "INVALID_ADVANCE_AMOUNT", str(exc)) from exc
            if amount > row.face_value_minor:
                raise APIError(
                    422, "INVALID_ADVANCE_AMOUNT", "Advance must not exceed the invoice face value."
                )
            self._expire(row, await self._offers(row))
            offer = FinancingOffer(
                receivable_id=row.id,
                financier_org_id=self.actor.organization_id,
                advance_amount_minor=amount,
                currency=payload.currency,
                discount_rate_bps=payload.discount_rate_bps,
                tenor_days=payload.tenor_days,
                expires_at=payload.expires_at,
                status="OFFERED",
            )
            self.session.add(offer)
            await self.session.flush()
            self._audit("OFFER_CREATED", row, offerId=str(offer.id))
            result = self._offer_view(offer)
        return result

    async def view(self, receivable_id: UUID) -> FinancingView:
        row = await self._row(receivable_id)
        offers = await self._offers(row)
        visible = (
            offers
            if self.actor.role == Role.EXPORTER
            else [
                o
                for o in offers
                if self.actor.role == Role.FINANCIER
                and o.financier_org_id == self.actor.organization_id
            ]
        )
        agreement = await self.session.scalar(
            select(FinancingAgreement).where(FinancingAgreement.receivable_id == row.id)
        )
        agreement_view = None
        payment = None
        if agreement and any(o.id == agreement.offer_id for o in visible):
            agreement_view = AgreementView(
                id=agreement.id,
                offer_id=agreement.offer_id,
                agreement_hash=agreement.agreement_hash,
                canonical_payload=canonical_agreement(agreement.payload),
                accepted_at=agreement.accepted_at,
                lock_transaction_id=agreement.lock_transaction_id,
                financing_transaction_id=agreement.financing_transaction_id,
            )
            payment = await self.payment.get_payment_status(agreement.id)
        return FinancingView(
            offers=[self._offer_view(o) for o in visible],
            agreement=agreement_view,
            payment=payment,
            can_offer=self.actor.role == Role.FINANCIER and row.status == S.FINANCE_AVAILABLE,
            can_accept=self.actor.role == Role.EXPORTER and row.status == S.FINANCE_AVAILABLE,
            can_disburse=self.actor.role == Role.FINANCIER
            and row.owner_org_id == self.actor.organization_id
            and row.status == S.LOCKED
            and agreement_view is not None,
            backend=self.settings.ledger_backend,
        )

    async def _offer_row(self, offer_id: UUID) -> tuple[Receivable, FinancingOffer]:
        # Always lock the receivable first, then load offers, across all financing mutations.
        receivable_id = await self.session.scalar(
            select(FinancingOffer.receivable_id).where(FinancingOffer.id == offer_id)
        )
        if receivable_id is None:
            raise APIError(404, "OFFER_NOT_FOUND", "Offer not found.")
        row = await self._row(receivable_id, lock=True)
        offer = await self.session.get(FinancingOffer, offer_id, populate_existing=True)
        assert offer is not None
        return row, offer

    def _payload(
        self, row: Receivable, offer: FinancingOffer, accepted_at: datetime
    ) -> dict[str, str | int]:
        assert row.asset_id is not None
        return agreement_payload(
            asset_id=row.asset_id,
            exporter_org_id=row.exporter_org_id,
            financier_org_id=offer.financier_org_id,
            advance_amount_minor=offer.advance_amount_minor,
            currency=offer.currency,
            discount_rate_bps=offer.discount_rate_bps,
            tenor_days=offer.tenor_days,
            accepted_at=accepted_at,
        )

    def _verify_agreement(
        self, row: Receivable, offer: FinancingOffer, agreement: FinancingAgreement
    ) -> None:
        expected = self._payload(row, offer, agreement.accepted_at)
        if (
            agreement.payload != expected
            or agreement_hash(expected) != agreement.agreement_hash
            or agreement.agreement_hash != row.financing_agreement_hash
            or offer.status != "ACCEPTED"
            or row.owner_org_id != offer.financier_org_id
        ):
            raise APIError(
                409,
                "AGREEMENT_INTEGRITY_FAILED",
                "The recorded financing agreement failed integrity verification.",
            )

    async def accept(self, offer_id: UUID) -> FinancingResult:
        self._role(Role.EXPORTER)
        expired = False
        async with self._transaction():
            row, offer = await self._offer_row(offer_id)
            ledger = self._ledger()
            recovering = await self._asset(ledger, row, "lock:" + str(offer.id))
            existing = await self.session.scalar(
                select(FinancingAgreement).where(FinancingAgreement.receivable_id == row.id)
            )
            if existing and existing.offer_id == offer.id:
                self._verify_agreement(row, offer, existing)
                result = FinancingResult(
                    backend=self.settings.ledger_backend,
                    receivable_id=row.id,
                    status=row.status,
                    offer_id=offer.id,
                    agreement_hash=existing.agreement_hash,
                    transaction_id=existing.lock_transaction_id,
                    replayed=True,
                )
            else:
                self._open(row)
                offers = await self._offers(row)
                if not recovering:
                    self._expire(row, offers)
                if offer.status == "EXPIRED" and not recovering:
                    expired = True
                elif offer.status != "OFFERED" and not recovering:
                    raise APIError(409, "OFFER_NOT_AVAILABLE", "Offer is no longer available.")
                else:
                    accepted_at = datetime.now(UTC)
                    payload = self._payload(row, offer, accepted_at)
                    if isinstance(ledger, DrunixLedgerClient):
                        payload = await ledger.acceptance_payload(
                            offer.id, payload, offer.expires_at
                        )
                        accepted_at = datetime.fromisoformat(
                            str(payload["acceptedAt"]).replace("Z", "+00:00")
                        )
                    digest = agreement_hash(payload)
                    receipt = await ledger.lock_receivable(
                        row.asset_id or "",
                        offer.financier_org_id,
                        digest,
                        payload=payload,
                        offer_id=offer.id,
                        expires_at=offer.expires_at,
                    )
                    agreement = FinancingAgreement(
                        receivable_id=row.id,
                        offer_id=offer.id,
                        payload=payload,
                        agreement_hash=digest,
                        accepted_at=accepted_at,
                        lock_transaction_id=receipt.transaction_id,
                    )
                    self.session.add(agreement)
                    offer.status = "ACCEPTED"
                    for other in offers:
                        if other.id != offer.id and other.status == "OFFERED":
                            other.status = "REJECTED"
                            self._audit(
                                "OFFER_REJECTED",
                                row,
                                offerId=str(other.id),
                                reason="ANOTHER_OFFER_ACCEPTED",
                            )
                    row.status, row.owner_org_id, row.financing_agreement_hash = (
                        receipt.asset.status,
                        receipt.asset.owner_org_id,
                        digest,
                    )
                    self._audit("OFFER_ACCEPTED", row, offerId=str(offer.id), agreementHash=digest)
                    self._audit(
                        "RECEIVABLE_LOCKED",
                        row,
                        fromStatus="FINANCE_AVAILABLE",
                        toStatus="LOCKED",
                        backend=self.settings.ledger_backend,
                        transactionId=receipt.transaction_id,
                    )
                    result = FinancingResult(
                        backend=self.settings.ledger_backend,
                        receivable_id=row.id,
                        status=row.status,
                        offer_id=offer.id,
                        agreement_hash=digest,
                        transaction_id=receipt.transaction_id,
                    )
        if expired:
            raise APIError(
                409, "OFFER_EXPIRED", "Offer expired before acceptance; request a new offer."
            )
        return result

    async def reject(self, offer_id: UUID) -> OfferView:
        self._role(Role.EXPORTER)
        async with self._transaction():
            row, offer = await self._offer_row(offer_id)
            if self.settings.ledger_backend == "drunix":
                await self._asset(self._ledger(), row)
            self._expire(row, await self._offers(row))
            if offer.status == "ACCEPTED":
                raise APIError(
                    409, "OFFER_ALREADY_ACCEPTED", "An accepted agreement cannot be rejected."
                )
            if offer.status == "OFFERED":
                offer.status = "REJECTED"
                self._audit(
                    "OFFER_REJECTED", row, offerId=str(offer.id), reason="EXPORTER_REJECTED"
                )
            result = self._offer_view(offer)
        return result

    async def disburse(self, receivable_id: UUID) -> FinancingResult:
        self._role(Role.FINANCIER)
        async with self._transaction():
            row = await self._row(receivable_id, lock=True)
            if row.owner_org_id != self.actor.organization_id:
                raise APIError(
                    403,
                    "UNAUTHORIZED_ROLE",
                    "Only the financing lock owner may simulate disbursement.",
                )
            ledger = self._ledger()
            await self._asset(ledger, row, "transition:" + (row.asset_id or "") + ":FINANCED")
            agreement = await self.session.scalar(
                select(FinancingAgreement).where(FinancingAgreement.receivable_id == row.id)
            )
            if agreement is None:
                raise APIError(409, "AGREEMENT_REQUIRED", "Accept an offer before disbursement.")
            offer = await self.session.get(FinancingOffer, agreement.offer_id)
            assert offer is not None
            self._verify_agreement(row, offer, agreement)
            existing = await self.payment.get_payment_status(agreement.id)
            if existing:
                if not agreement.financing_transaction_id or row.status in {
                    S.LOCKED,
                    S.FINANCE_AVAILABLE,
                }:
                    raise APIError(
                        503,
                        "PAYMENT_STATE_MISMATCH",
                        "The recorded payment simulation is inconsistent.",
                    )
                result = FinancingResult(
                    backend=self.settings.ledger_backend,
                    receivable_id=row.id,
                    status=row.status,
                    offer_id=offer.id,
                    agreement_hash=agreement.agreement_hash,
                    transaction_id=agreement.financing_transaction_id,
                    payment=existing,
                    replayed=True,
                )
            else:
                if row.status != S.LOCKED:
                    raise APIError(
                        409, "INVALID_STATE_TRANSITION", "Only a locked receivable can be financed."
                    )
                payment = await self.payment.disburse_financing(
                    agreement.id, offer.advance_amount_minor, offer.currency
                )
                receipt = await ledger.transition_receivable(row.asset_id or "", S.FINANCED)
                row.status = receipt.asset.status
                agreement.financing_transaction_id = receipt.transaction_id
                self._audit(
                    "MOCK_DISBURSEMENT_RECORDED",
                    row,
                    paymentId=payment.transaction_id,
                    backend="mock",
                )
                self._audit(
                    "FINANCING_RECORDED",
                    row,
                    fromStatus="LOCKED",
                    toStatus="FINANCED",
                    backend=self.settings.ledger_backend,
                    transactionId=receipt.transaction_id,
                )
                result = FinancingResult(
                    backend=self.settings.ledger_backend,
                    receivable_id=row.id,
                    status=row.status,
                    offer_id=offer.id,
                    agreement_hash=agreement.agreement_hash,
                    transaction_id=receipt.transaction_id,
                    payment=payment,
                )
        return result

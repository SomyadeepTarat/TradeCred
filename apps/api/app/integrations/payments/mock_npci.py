"""NPCI Payment Adapter — Sandbox Simulation. No external calls or movement of funds."""

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.integrations.payments.base import PaymentReceipt
from app.models.financing import MockDisbursement


class MockNPCIPaymentAdapter:
    """Caller holds the receivable lock and commits the shared unit of work."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def disburse_financing(
        self, agreement_id: UUID, amount_minor: int, currency: str
    ) -> PaymentReceipt:
        existing = await self.session.scalar(
            select(MockDisbursement).where(MockDisbursement.agreement_id == agreement_id)
        )
        if existing:
            if existing.amount_minor != amount_minor or existing.currency != currency:
                raise APIError(
                    409,
                    "DISBURSEMENT_CONFLICT",
                    "Payment data differs from the recorded simulation.",
                )
            return PaymentReceipt.model_validate(existing)
        if type(amount_minor) is not int or amount_minor <= 0:
            raise APIError(422, "INVALID_PAYMENT_AMOUNT", "A positive amount is required.")
        payment = MockDisbursement(
            transaction_id="MOCKPAY-" + uuid4().hex,
            agreement_id=agreement_id,
            amount_minor=amount_minor,
            currency=currency,
            status="SIMULATED_SUCCEEDED",
        )
        self.session.add(payment)
        await self.session.flush()
        return PaymentReceipt.model_validate(payment)

    async def get_payment_status(self, agreement_id: UUID) -> PaymentReceipt | None:
        row = await self.session.scalar(
            select(MockDisbursement).where(MockDisbursement.agreement_id == agreement_id)
        )
        return PaymentReceipt.model_validate(row) if row else None

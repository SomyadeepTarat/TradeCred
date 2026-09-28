from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, field_validator

from app.integrations.payments.base import PaymentReceipt
from app.models.domain import ReceivableStatus
from app.services.fingerprint_service import normalize_currency


class OfferInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    advance_amount: str = Field(alias="advanceAmount", strict=True, max_length=32)
    currency: str
    discount_rate_bps: StrictInt = Field(alias="discountRateBps", ge=0, le=10000)
    tenor_days: StrictInt = Field(alias="tenorDays", gt=0, le=3650)
    expires_at: AwareDatetime = Field(alias="expiresAt")

    @field_validator("currency")
    @classmethod
    def currency_code(cls, value: str) -> str:
        return normalize_currency(value)


class OfferView(BaseModel):
    id: UUID
    receivable_id: UUID
    financier_org_id: str
    advance_amount: str
    currency: str
    discount_rate_bps: int
    tenor_days: int
    expires_at: datetime
    status: Literal["OFFERED", "ACCEPTED", "REJECTED", "EXPIRED"]
    created_at: datetime


class AgreementView(BaseModel):
    id: UUID
    offer_id: UUID
    agreement_hash: str
    canonical_payload: str
    accepted_at: datetime
    lock_transaction_id: str
    financing_transaction_id: str | None


class FinancingView(BaseModel):
    offers: list[OfferView]
    agreement: AgreementView | None
    payment: PaymentReceipt | None
    can_offer: bool
    can_accept: bool
    can_disburse: bool
    backend: Literal["mock", "drunix"]


class FinancingResult(BaseModel):
    receivable_id: UUID
    status: ReceivableStatus
    offer_id: UUID
    agreement_hash: str
    transaction_id: str
    payment: PaymentReceipt | None = None
    replayed: bool = False
    backend: Literal["mock", "drunix"] = "mock"

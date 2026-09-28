from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt


class PaymentEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eventId: str = Field(pattern=r"^[A-Za-z0-9_-]{1,160}$")
    assetId: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    bankId: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    bankReference: str = Field(pattern=r"^[A-Za-z0-9_./-]{1,160}$")
    amountMinor: StrictInt = Field(gt=0, le=2**63 - 1)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    timestamp: AwareDatetime
    nonce: str = Field(pattern=r"^[A-Za-z0-9_-]{16,160}$")


class PaymentEventView(BaseModel):
    event_id: str
    asset_id: str
    verification_status: Literal["VERIFIED"] = "VERIFIED"
    status: Literal["PAYMENT_CONFIRMED"] = "PAYMENT_CONFIRMED"
    transaction_id: str
    received_at: datetime
    backend: Literal["mock", "drunix"] = "mock"

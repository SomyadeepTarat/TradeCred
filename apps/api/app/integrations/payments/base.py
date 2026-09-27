from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PaymentReceipt(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    transaction_id: str
    agreement_id: UUID
    status: Literal["SIMULATED_SUCCEEDED"]
    backend: Literal["mock"] = "mock"


class PaymentAdapter(Protocol):
    async def disburse_financing(
        self, agreement_id: UUID, amount_minor: int, currency: str
    ) -> PaymentReceipt: ...
    async def get_payment_status(self, agreement_id: UUID) -> PaymentReceipt | None: ...

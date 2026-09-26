from datetime import date, datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.models.domain import ReceivableStatus, Role


class LedgerActor(BaseModel):
    model_config = ConfigDict(frozen=True)
    user_id: UUID
    organization_id: str
    role: Role


class Registration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    asset_id: str = Field(min_length=1, max_length=80)
    invoice_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    document_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    exporter_org_id: str = Field(min_length=1, max_length=80)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    face_value_minor: StrictInt = Field(gt=0, le=2**63 - 1)
    due_date: date


class LedgerAsset(BaseModel):
    """Sanitized world-state projection. Exact value never leaves private storage here."""

    model_config = ConfigDict(from_attributes=True)
    asset_id: str
    invoice_fingerprint: str
    document_hash: str
    exporter_org_id: str
    owner_org_id: str | None
    currency: str
    face_value_bucket: str
    due_date: date
    agreement_hash: str | None
    status: ReceivableStatus
    updated_at: datetime
    backend: Literal["mock"] = "mock"


class LedgerReceipt(BaseModel):
    asset: LedgerAsset
    transaction_id: str
    replayed: bool = False


class LedgerHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    transaction_id: str
    asset_id: str
    revision: int
    from_status: ReceivableStatus
    to_status: ReceivableStatus
    actor_org_id: str
    created_at: datetime
    backend: Literal["mock"] = "mock"


class LedgerClient(Protocol):
    """Caller owns commit/rollback. Receipts are confirmed only after the unit of work commits."""

    async def register_receivable(self, registration: Registration) -> LedgerReceipt: ...
    async def get_receivable(self, asset_id: str) -> LedgerAsset | None: ...
    async def find_by_fingerprint(self, fingerprint: str) -> LedgerAsset | None: ...
    async def transition_receivable(
        self, asset_id: str, target: ReceivableStatus
    ) -> LedgerReceipt: ...
    async def lock_receivable(
        self, asset_id: str, financier_org_id: str, agreement_hash: str
    ) -> LedgerReceipt: ...
    async def confirm_payment(
        self, asset_id: str, event_id: str, amount_minor: int, currency: str, reference: str
    ) -> LedgerReceipt: ...
    async def get_history(self, asset_id: str) -> list[LedgerHistoryEntry]: ...

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from app.integrations.ledger.base import LedgerHistoryEntry
from app.models.domain import ReceivableStatus
from app.schemas.receivables import InvoiceMetadata
from app.services.fingerprint_service import canonical_invoice, invoice_fingerprint


class RegistryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exporter_id: str = Field(alias="exporterId", max_length=120)
    buyer_id: str = Field(alias="buyerId", max_length=120)
    invoice_number: str = Field(alias="invoiceNumber", max_length=120)
    currency: str = Field(max_length=16)
    amount_minor: StrictInt = Field(alias="amountMinor", gt=0, le=2**63 - 1)
    invoice_date: date = Field(alias="invoiceDate")

    @field_validator("invoice_date", mode="before")
    @classmethod
    def iso_date(cls, value: object) -> object:
        return InvoiceMetadata.iso_date(value)

    def fingerprint(self) -> str:
        return invoice_fingerprint(canonical_invoice(**self.model_dump()))

    @model_validator(mode="after")
    def validate_identity(self) -> "RegistryInput":
        self.fingerprint()
        return self


class RegistryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    fingerprint: str
    exists: bool
    eligible: bool
    asset_id: str | None = Field(default=None, alias="assetId")
    status: ReceivableStatus | None = None
    reason: str | None = None
    locked: bool = False
    financed: bool = False
    backend: Literal["mock"] = "mock"


class LifecycleResponse(BaseModel):
    id: UUID
    status: ReceivableStatus
    asset_id: str | None
    transaction_id: str | None = None
    backend: Literal["mock"] | None = None
    replayed: bool = False


class AuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    event_type: str
    actor_user_id: UUID
    actor_org_id: str
    receivable_id: UUID | None
    asset_id: str | None
    request_id: str
    metadata_json: dict[str, str]
    created_at: datetime


class HistoryResponse(BaseModel):
    events: list[AuditResponse]
    ledger: list[LedgerHistoryEntry]

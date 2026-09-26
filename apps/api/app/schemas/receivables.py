import re
from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.domain import ReceivableStatus
from app.services.fingerprint_service import (
    amount_to_minor,
    normalize_currency,
    normalize_identifier,
    normalize_invoice_number,
)


class InvoiceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    buyer_id: str = Field(alias="buyerId", max_length=120)
    invoice_number: str = Field(alias="invoiceNumber", max_length=120)
    invoice_date: date = Field(alias="invoiceDate")
    currency: str
    amount: str = Field(strict=True, max_length=32)
    due_date: date = Field(alias="dueDate")

    @field_validator("buyer_id")
    @classmethod
    def buyer(cls, value: str) -> str:
        return normalize_identifier(value)

    @field_validator("invoice_number")
    @classmethod
    def invoice(cls, value: str) -> str:
        return normalize_invoice_number(value)

    @field_validator("currency")
    @classmethod
    def currency_code(cls, value: str) -> str:
        return normalize_currency(value)

    @field_validator("invoice_date", "due_date", mode="before")
    @classmethod
    def iso_date(cls, value: object) -> object:
        if type(value) is date:
            return value
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
            raise ValueError("Dates must use YYYY-MM-DD.")
        return value.strip()

    @model_validator(mode="after")
    def validate_terms(self) -> "InvoiceMetadata":
        amount_to_minor(self.amount, self.currency)
        if self.due_date < self.invoice_date:
            raise ValueError("Due date must not precede invoice date.")
        return self


class DraftResponse(BaseModel):
    id: UUID
    status: ReceivableStatus
    document_id: UUID
    document_hash: str
    invoice_fingerprint: str
    fingerprint_version: str = "TC-FP-1"
    currency: str
    face_value_minor: int


class IntegrityResponse(BaseModel):
    document_id: UUID
    expected_hash: str
    actual_hash: str
    verified: bool

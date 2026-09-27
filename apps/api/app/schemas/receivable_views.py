from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.models.domain import ReceivableStatus
from app.schemas.ledger import AuditResponse


class ReceivableView(BaseModel):
    id: UUID
    asset_id: str | None
    exporter_org_id: str
    invoice_number: str | None
    buyer_id: str | None
    invoice_date: date | None
    due_date: date
    currency: str
    face_value: str | None
    face_value_bucket: str
    status: ReceivableStatus
    invoice_fingerprint: str | None
    document_hash: str | None
    owner_org_id: str | None
    financing_agreement_hash: str | None
    ebrc_status: str | None
    created_at: datetime
    updated_at: datetime


class ReceivableDetail(ReceivableView):
    document_available: bool
    available_actions: list[str]
    ledger_backend: Literal["mock", "drunix"]


class DashboardSummary(BaseModel):
    total: int
    available: int
    financed: int
    settled: int


class ReceivablePage(BaseModel):
    items: list[ReceivableView]
    total: int
    summary: DashboardSummary
    recent_activity: list[AuditResponse]

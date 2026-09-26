from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.domain import Base


class MockLedgerAsset(Base):
    __tablename__ = "mock_ledger_assets"
    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_mock_ledger_revision"),
        CheckConstraint("invoice_fingerprint ~ '^[a-f0-9]{64}$'", name="ck_mock_fingerprint"),
        CheckConstraint("document_hash ~ '^[a-f0-9]{64}$'", name="ck_mock_document_hash"),
    )
    asset_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    invoice_fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    document_hash: Mapped[str] = mapped_column(String(64))
    exporter_org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    owner_org_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"))
    currency: Mapped[str] = mapped_column(String(3))
    face_value_bucket: Mapped[str] = mapped_column(String(40))
    due_date: Mapped[date] = mapped_column(Date)
    agreement_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    revision: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MockLedgerPrivate(Base):
    __tablename__ = "mock_ledger_private"
    __table_args__ = (CheckConstraint("face_value_minor > 0", name="ck_mock_private_value"),)
    asset_id: Mapped[str] = mapped_column(
        ForeignKey("mock_ledger_assets.asset_id"), primary_key=True
    )
    face_value_minor: Mapped[int] = mapped_column(BigInteger)
    settlement_reference: Mapped[str | None] = mapped_column(String(160))


class LedgerTransaction(Base):
    __tablename__ = "ledger_transactions"
    __table_args__ = (UniqueConstraint("asset_id", "revision", name="uq_ledger_revision"),)
    transaction_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("mock_ledger_assets.asset_id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    from_status: Mapped[str] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    actor_org_id: Mapped[str] = mapped_column(String(80))
    payment_event_id: Mapped[str | None] = mapped_column(String(160), unique=True)
    backend: Mapped[str] = mapped_column(String(16), default="mock")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    actor_org_id: Mapped[str] = mapped_column(String(80))
    receivable_id: Mapped[UUID | None] = mapped_column(ForeignKey("receivables.id"), index=True)
    asset_id: Mapped[str | None] = mapped_column(String(80))
    request_id: Mapped[str] = mapped_column(String(36))
    metadata_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

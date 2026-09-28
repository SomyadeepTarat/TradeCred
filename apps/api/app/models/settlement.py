from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.domain import Base


class PaymentEvent(Base):
    __tablename__ = "payment_events"
    event_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    nonce: Mapped[str] = mapped_column(String(160), unique=True)
    receivable_id: Mapped[UUID] = mapped_column(ForeignKey("receivables.id"), unique=True)
    bank_org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    asset_id: Mapped[str] = mapped_column(String(80))
    payload_hash: Mapped[str] = mapped_column(String(64))
    key_id: Mapped[str] = mapped_column(String(80))
    verification_status: Mapped[str] = mapped_column(String(16), default="VERIFIED")
    backend: Mapped[str] = mapped_column(String(16), default="mock", server_default="mock")
    transaction_id: Mapped[str] = mapped_column(String(80))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SecurityEvent(Base):
    __tablename__ = "security_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    reason: Mapped[str] = mapped_column(String(80))
    request_id: Mapped[str] = mapped_column(String(36))
    payload_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

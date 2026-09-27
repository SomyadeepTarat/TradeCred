from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.domain import Base


class FinancingOffer(Base):
    __tablename__ = "financing_offers"
    __table_args__ = (
        CheckConstraint("advance_amount_minor > 0", name="ck_offer_amount"),
        CheckConstraint(
            "discount_rate_bps >= 0 AND discount_rate_bps <= 10000", name="ck_offer_rate"
        ),
        CheckConstraint("tenor_days > 0 AND tenor_days <= 3650", name="ck_offer_tenor"),
        CheckConstraint(
            "status IN ('OFFERED','ACCEPTED','REJECTED','EXPIRED')", name="ck_offer_status"
        ),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_offer_currency"),
        Index(
            "uq_one_accepted_offer",
            "receivable_id",
            unique=True,
            postgresql_where=text("status = 'ACCEPTED'"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    receivable_id: Mapped[UUID] = mapped_column(ForeignKey("receivables.id"), index=True)
    financier_org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    advance_amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    discount_rate_bps: Mapped[int] = mapped_column(Integer)
    tenor_days: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="OFFERED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FinancingAgreement(Base):
    __tablename__ = "financing_agreements"
    __table_args__ = (
        CheckConstraint("agreement_hash ~ '^[a-f0-9]{64}$'", name="ck_agreement_hash"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    receivable_id: Mapped[UUID] = mapped_column(ForeignKey("receivables.id"), unique=True)
    offer_id: Mapped[UUID] = mapped_column(ForeignKey("financing_offers.id"), unique=True)
    payload: Mapped[dict[str, str | int]] = mapped_column(JSON)
    agreement_hash: Mapped[str] = mapped_column(String(64))
    lock_transaction_id: Mapped[str] = mapped_column(String(80))
    financing_transaction_id: Mapped[str | None] = mapped_column(String(80))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MockDisbursement(Base):
    __tablename__ = "mock_disbursements"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="ck_disbursement_amount"),
        CheckConstraint("status = 'SIMULATED_SUCCEEDED'", name="ck_disbursement_status"),
    )
    transaction_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    agreement_id: Mapped[UUID] = mapped_column(ForeignKey("financing_agreements.id"), unique=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(24), default="SIMULATED_SUCCEEDED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

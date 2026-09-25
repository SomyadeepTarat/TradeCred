import enum
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, String, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Role(str, enum.Enum):
    EXPORTER = "EXPORTER"
    FINANCIER = "FINANCIER"
    SETTLEMENT_OPERATOR = "SETTLEMENT_OPERATOR"
    ADMIN = "ADMIN"


class OrganizationType(str, enum.Enum):
    EXPORTER = "EXPORTER"
    FINANCIER = "FINANCIER"
    SETTLEMENT_BANK = "SETTLEMENT_BANK"
    CONSORTIUM = "CONSORTIUM"


class ReceivableStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    VERIFIED = "VERIFIED"
    REGISTERED = "REGISTERED"
    FINANCE_AVAILABLE = "FINANCE_AVAILABLE"
    LOCKED = "LOCKED"
    FINANCED = "FINANCED"
    PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
    REALIZED = "REALIZED"
    EBRC_ELIGIBLE = "EBRC_ELIGIBLE"
    CLOSED = "CLOSED"
    REJECTED_DUPLICATE = "REJECTED_DUPLICATE"
    RELEASED = "RELEASED"
    OVERDUE = "OVERDUE"
    DISPUTED = "DISPUTED"


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Organization(Timestamps, Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    organization_type: Mapped[OrganizationType] = mapped_column(
        Enum(OrganizationType, name="organization_type")
    )


class User(Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("email = lower(trim(email))", name="ck_users_email_canonical"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Receivable(Timestamps, Base):
    __tablename__ = "receivables"
    __table_args__ = (
        CheckConstraint("face_value_minor > 0", name="ck_receivables_positive_value"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_receivables_currency"),
        CheckConstraint("due_date >= invoice_date", name="ck_receivables_dates"),
        CheckConstraint(
            "document_hash IS NULL OR document_hash ~ '^[a-f0-9]{64}$'",
            name="ck_receivables_document_hash",
        ),
        CheckConstraint(
            "invoice_fingerprint IS NULL OR invoice_fingerprint ~ '^[a-f0-9]{64}$'",
            name="ck_receivables_fingerprint",
        ),
        CheckConstraint(
            "financing_agreement_hash IS NULL OR financing_agreement_hash ~ '^[a-f0-9]{64}$'",
            name="ck_receivables_agreement_hash",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    asset_id: Mapped[str | None] = mapped_column(String(80), unique=True)
    exporter_org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    buyer_id: Mapped[str] = mapped_column(String(120))
    invoice_number: Mapped[str] = mapped_column(String(120))
    invoice_date: Mapped[date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3))
    face_value_minor: Mapped[int] = mapped_column(BigInteger)
    due_date: Mapped[date] = mapped_column(Date)
    document_hash: Mapped[str | None] = mapped_column(String(64))
    invoice_fingerprint: Mapped[str | None] = mapped_column(String(64), unique=True)
    status: Mapped[ReceivableStatus] = mapped_column(
        Enum(ReceivableStatus, name="receivable_status"),
        default=ReceivableStatus.DRAFT, server_default="DRAFT",
    )
    owner_org_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    financing_agreement_hash: Mapped[str | None] = mapped_column(String(64))
    settlement_reference: Mapped[str | None] = mapped_column(String(160))
    ebrc_status: Mapped[str | None] = mapped_column(String(80))

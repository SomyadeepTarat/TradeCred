"""organizations users and receivables

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "organization_type",
            sa.Enum(
                "EXPORTER", "FINANCIER", "SETTLEMENT_BANK", "CONSORTIUM", name="organization_type"
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "receivables",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.String(length=80), nullable=True),
        sa.Column("exporter_org_id", sa.String(length=80), nullable=False),
        sa.Column("buyer_id", sa.String(length=120), nullable=False),
        sa.Column("invoice_number", sa.String(length=120), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("face_value_minor", sa.BigInteger(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("document_hash", sa.String(length=64), nullable=True),
        sa.Column("invoice_fingerprint", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "SUBMITTED",
                "VERIFIED",
                "REGISTERED",
                "FINANCE_AVAILABLE",
                "LOCKED",
                "FINANCED",
                "PAYMENT_CONFIRMED",
                "REALIZED",
                "EBRC_ELIGIBLE",
                "CLOSED",
                "REJECTED_DUPLICATE",
                "RELEASED",
                "OVERDUE",
                "DISPUTED",
                name="receivable_status",
            ),
            server_default="DRAFT",
            nullable=False,
        ),
        sa.Column("owner_org_id", sa.String(length=80), nullable=True),
        sa.Column("financing_agreement_hash", sa.String(length=64), nullable=True),
        sa.Column("settlement_reference", sa.String(length=160), nullable=True),
        sa.Column("ebrc_status", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_receivables_currency"),
        sa.CheckConstraint(
            "document_hash IS NULL OR document_hash ~ '^[a-f0-9]{64}$'",
            name="ck_receivables_document_hash",
        ),
        sa.CheckConstraint(
            "financing_agreement_hash IS NULL OR financing_agreement_hash ~ '^[a-f0-9]{64}$'",
            name="ck_receivables_agreement_hash",
        ),
        sa.CheckConstraint(
            "invoice_fingerprint IS NULL OR invoice_fingerprint ~ '^[a-f0-9]{64}$'",
            name="ck_receivables_fingerprint",
        ),
        sa.CheckConstraint("due_date >= invoice_date", name="ck_receivables_dates"),
        sa.CheckConstraint("face_value_minor > 0", name="ck_receivables_positive_value"),
        sa.ForeignKeyConstraint(
            ["exporter_org_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["owner_org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id"),
        sa.UniqueConstraint("invoice_fingerprint"),
    )
    op.create_index(
        op.f("ix_receivables_exporter_org_id"), "receivables", ["exporter_org_id"], unique=False
    )
    op.create_index(
        op.f("ix_receivables_owner_org_id"), "receivables", ["owner_org_id"], unique=False
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("EXPORTER", "FINANCIER", "SETTLEMENT_OPERATOR", "ADMIN", name="user_role"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("email = lower(trim(email))", name="ck_users_email_canonical"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_organization_id"), "users", ["organization_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_organization_id"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_receivables_owner_org_id"), table_name="receivables")
    op.drop_index(op.f("ix_receivables_exporter_org_id"), table_name="receivables")
    op.drop_table("receivables")
    op.drop_table("organizations")

    for name in ("user_role", "receivable_status", "organization_type"):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)

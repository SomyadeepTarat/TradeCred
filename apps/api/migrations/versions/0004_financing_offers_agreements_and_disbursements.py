"""financing offers agreements and mock disbursement

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "financing_offers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("receivable_id", sa.Uuid(), nullable=False),
        sa.Column("financier_org_id", sa.String(length=80), nullable=False),
        sa.Column("advance_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("discount_rate_bps", sa.Integer(), nullable=False),
        sa.Column("tenor_days", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_offer_currency"),
        sa.CheckConstraint(
            "status IN ('OFFERED','ACCEPTED','REJECTED','EXPIRED')", name="ck_offer_status"
        ),
        sa.CheckConstraint("advance_amount_minor > 0", name="ck_offer_amount"),
        sa.CheckConstraint(
            "discount_rate_bps >= 0 AND discount_rate_bps <= 10000", name="ck_offer_rate"
        ),
        sa.CheckConstraint("tenor_days > 0 AND tenor_days <= 3650", name="ck_offer_tenor"),
        sa.ForeignKeyConstraint(
            ["financier_org_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["receivable_id"],
            ["receivables.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_financing_offers_financier_org_id"),
        "financing_offers",
        ["financier_org_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financing_offers_receivable_id"),
        "financing_offers",
        ["receivable_id"],
        unique=False,
    )
    op.create_index(
        "uq_one_accepted_offer",
        "financing_offers",
        ["receivable_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACCEPTED'"),
    )
    op.create_table(
        "financing_agreements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("receivable_id", sa.Uuid(), nullable=False),
        sa.Column("offer_id", sa.Uuid(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("agreement_hash", sa.String(length=64), nullable=False),
        sa.Column("lock_transaction_id", sa.String(length=80), nullable=False),
        sa.Column("financing_transaction_id", sa.String(length=80), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("agreement_hash ~ '^[a-f0-9]{64}$'", name="ck_agreement_hash"),
        sa.ForeignKeyConstraint(
            ["offer_id"],
            ["financing_offers.id"],
        ),
        sa.ForeignKeyConstraint(
            ["receivable_id"],
            ["receivables.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("offer_id"),
        sa.UniqueConstraint("receivable_id"),
    )
    op.create_table(
        "mock_disbursements",
        sa.Column("transaction_id", sa.String(length=50), nullable=False),
        sa.Column("agreement_id", sa.Uuid(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status = 'SIMULATED_SUCCEEDED'", name="ck_disbursement_status"),
        sa.CheckConstraint("amount_minor > 0", name="ck_disbursement_amount"),
        sa.ForeignKeyConstraint(
            ["agreement_id"],
            ["financing_agreements.id"],
        ),
        sa.PrimaryKeyConstraint("transaction_id"),
        sa.UniqueConstraint("agreement_id"),
    )


def downgrade() -> None:
    op.drop_table("mock_disbursements")
    op.drop_table("financing_agreements")
    op.drop_index(
        "uq_one_accepted_offer",
        table_name="financing_offers",
        postgresql_where=sa.text("status = 'ACCEPTED'"),
    )
    op.drop_index(op.f("ix_financing_offers_receivable_id"), table_name="financing_offers")
    op.drop_index(op.f("ix_financing_offers_financier_org_id"), table_name="financing_offers")
    op.drop_table("financing_offers")

"""mock ledger and audit history

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mock_ledger_assets",
        sa.Column("asset_id", sa.String(length=80), nullable=False),
        sa.Column("invoice_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("document_hash", sa.String(length=64), nullable=False),
        sa.Column("exporter_org_id", sa.String(length=80), nullable=False),
        sa.Column("owner_org_id", sa.String(length=80), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("face_value_bucket", sa.String(length=40), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("agreement_hash", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("document_hash ~ '^[a-f0-9]{64}$'", name="ck_mock_document_hash"),
        sa.CheckConstraint("invoice_fingerprint ~ '^[a-f0-9]{64}$'", name="ck_mock_fingerprint"),
        sa.CheckConstraint("revision > 0", name="ck_mock_ledger_revision"),
        sa.ForeignKeyConstraint(
            ["exporter_org_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["owner_org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("asset_id"),
        sa.UniqueConstraint("invoice_fingerprint"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_org_id", sa.String(length=80), nullable=False),
        sa.Column("receivable_id", sa.Uuid(), nullable=True),
        sa.Column("asset_id", sa.String(length=80), nullable=True),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["receivable_id"],
            ["receivables.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audit_events_event_type"), "audit_events", ["event_type"], unique=False
    )
    op.create_index(
        op.f("ix_audit_events_receivable_id"), "audit_events", ["receivable_id"], unique=False
    )
    op.create_table(
        "ledger_transactions",
        sa.Column("transaction_id", sa.String(length=50), nullable=False),
        sa.Column("asset_id", sa.String(length=80), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=False),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("actor_org_id", sa.String(length=80), nullable=False),
        sa.Column("payment_event_id", sa.String(length=160), nullable=True),
        sa.Column("backend", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["mock_ledger_assets.asset_id"],
        ),
        sa.PrimaryKeyConstraint("transaction_id"),
        sa.UniqueConstraint("asset_id", "revision", name="uq_ledger_revision"),
        sa.UniqueConstraint("payment_event_id"),
    )
    op.create_index(
        op.f("ix_ledger_transactions_asset_id"), "ledger_transactions", ["asset_id"], unique=False
    )
    op.create_table(
        "mock_ledger_private",
        sa.Column("asset_id", sa.String(length=80), nullable=False),
        sa.Column("face_value_minor", sa.BigInteger(), nullable=False),
        sa.Column("settlement_reference", sa.String(length=160), nullable=True),
        sa.CheckConstraint("face_value_minor > 0", name="ck_mock_private_value"),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["mock_ledger_assets.asset_id"],
        ),
        sa.PrimaryKeyConstraint("asset_id"),
    )


def downgrade() -> None:
    op.drop_table("mock_ledger_private")
    op.drop_index(op.f("ix_ledger_transactions_asset_id"), table_name="ledger_transactions")
    op.drop_table("ledger_transactions")
    op.drop_index(op.f("ix_audit_events_receivable_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_event_type"), table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("mock_ledger_assets")

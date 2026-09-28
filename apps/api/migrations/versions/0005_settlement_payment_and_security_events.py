"""settlement payment and security events

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "security_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_security_events_event_type"), "security_events", ["event_type"], unique=False
    )
    op.create_table(
        "payment_events",
        sa.Column("event_id", sa.String(length=160), nullable=False),
        sa.Column("nonce", sa.String(length=160), nullable=False),
        sa.Column("receivable_id", sa.Uuid(), nullable=False),
        sa.Column("bank_org_id", sa.String(length=80), nullable=False),
        sa.Column("asset_id", sa.String(length=80), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("key_id", sa.String(length=80), nullable=False),
        sa.Column("verification_status", sa.String(length=16), nullable=False),
        sa.Column("transaction_id", sa.String(length=50), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["bank_org_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["receivable_id"],
            ["receivables.id"],
        ),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint("nonce"),
        sa.UniqueConstraint("receivable_id"),
    )


def downgrade() -> None:
    op.drop_table("payment_events")
    op.drop_index(op.f("ix_security_events_event_type"), table_name="security_events")
    op.drop_table("security_events")

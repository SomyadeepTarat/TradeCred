"""durable drunix inputs and backend binding

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("payment_events", "transaction_id", type_=sa.String(80))
    op.create_table(
        "ledger_artifacts",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )
    op.add_column(
        "payment_events",
        sa.Column("backend", sa.String(length=16), server_default="mock", nullable=False),
    )
    op.add_column("receivables", sa.Column("ledger_backend", sa.String(length=16), nullable=True))
    op.add_column("receivables", sa.Column("ledger_network", sa.String(length=120), nullable=True))

    op.execute(
        "UPDATE receivables SET ledger_backend = 'mock' "
        "WHERE asset_id IS NOT NULL OR status = 'VERIFIED'"
    )


def downgrade() -> None:
    # Preserve 64-character Fabric IDs rather than truncating committed receipts.
    op.drop_column("receivables", "ledger_network")
    op.drop_column("receivables", "ledger_backend")
    op.drop_column("payment_events", "backend")
    op.drop_table("ledger_artifacts")

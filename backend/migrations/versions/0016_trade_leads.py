"""trade leads: companies found on the web per product, country and side

Revision ID: 0016
Revises: 0015
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trade_leads",
        sa.Column("hs6", sa.CHAR(length=6), nullable=False),
        sa.Column("country", sa.CHAR(length=3), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name=op.f("fk_trade_leads_requested_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("hs6", "country", "side", name=op.f("pk_trade_leads")),
    )
    op.create_index(
        "ix_trade_leads_requested_by_updated", "trade_leads", ["requested_by", "updated_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_trade_leads_requested_by_updated", table_name="trade_leads")
    op.drop_table("trade_leads")

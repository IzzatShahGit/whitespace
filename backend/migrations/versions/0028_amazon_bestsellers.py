"""amazon_bestsellers: the latest weekly captures of Amazon US best-seller lists

Revision ID: 0028
Revises: 0027
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "amazon_bestsellers",
        sa.Column("run_id", sa.String(length=40), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_amazon_bestsellers")),
    )
    op.create_index(
        op.f("ix_amazon_bestsellers_captured_at"), "amazon_bestsellers", ["captured_at"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_amazon_bestsellers_captured_at"), table_name="amazon_bestsellers")
    op.drop_table("amazon_bestsellers")

"""analytics: first-party daily counts and day-scoped visitor hashes

Revision ID: 0019
Revises: 0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analytics_daily",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("event", sa.String(length=40), nullable=False),
        sa.Column("path", sa.String(length=120), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("day", "event", "path", name=op.f("pk_analytics_daily")),
    )
    op.create_table(
        "analytics_visitors",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("visitor", sa.CHAR(length=16), nullable=False),
        sa.PrimaryKeyConstraint("day", "visitor", name=op.f("pk_analytics_visitors")),
    )


def downgrade() -> None:
    op.drop_table("analytics_visitors")
    op.drop_table("analytics_daily")

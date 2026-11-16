"""tariff cache: import duties per tariff area and product, fetched on demand

Revision ID: 0015
Revises: 0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tariff_cache",
        sa.Column("reporter", sa.CHAR(length=3), nullable=False),
        sa.Column("hs6", sa.CHAR(length=6), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("reporter", "hs6", name=op.f("pk_tariff_cache")),
    )


def downgrade() -> None:
    op.drop_table("tariff_cache")

"""product_embeddings: one vector per HS6 product, for finding a code from a description

Revision ID: 0027
Revises: 0026
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_embeddings",
        sa.Column("hs6", sa.CHAR(length=6), nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column("model", sa.String(length=40), nullable=False),
        sa.Column("text_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("hs6", name=op.f("pk_product_embeddings")),
    )


def downgrade() -> None:
    op.drop_table("product_embeddings")

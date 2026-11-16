"""sea routes: distances between exporters and markets, for freight estimates

Revision ID: 0017
Revises: 0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ref_sea_route",
        sa.Column("origin", sa.CHAR(length=3), nullable=False),
        sa.Column("dest", sa.CHAR(length=3), nullable=False),
        sa.Column("sea_nm", sa.Float(), nullable=False),
        sa.Column("origin_port", sa.String(length=80), nullable=False),
        sa.Column("origin_port_code", sa.String(length=5), nullable=False),
        sa.Column("dest_port", sa.String(length=80), nullable=False),
        sa.Column("dest_port_code", sa.String(length=5), nullable=False),
        sa.Column("origin_inland_km", sa.Integer(), nullable=False),
        sa.Column("dest_inland_km", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("origin", "dest", name=op.f("pk_ref_sea_route")),
    )


def downgrade() -> None:
    op.drop_table("ref_sea_route")

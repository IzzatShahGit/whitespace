"""market requirements: researched import rules per lane, and users' checklist ticks

Revision ID: 0020
Revises: 0019
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_requirements",
        sa.Column("hs6", sa.CHAR(length=6), nullable=False),
        sa.Column("market", sa.CHAR(length=3), nullable=False),
        sa.Column("exporter", sa.CHAR(length=3), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["users.id"],
            name=op.f("fk_market_requirements_requested_by_users"), ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("hs6", "market", "exporter", name=op.f("pk_market_requirements")),
    )  # fmt: skip
    op.create_index(
        "ix_market_requirements_requested_by_updated",
        "market_requirements",
        ["requested_by", "updated_at"],
    )
    op.create_table(
        "requirement_checks",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("hs6", sa.CHAR(length=6), nullable=False),
        sa.Column("market", sa.CHAR(length=3), nullable=False),
        sa.Column("item", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_requirement_checks_user_id_users"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "hs6", "market", "item", name=op.f("pk_requirement_checks")),
    )  # fmt: skip


def downgrade() -> None:
    op.drop_table("requirement_checks")
    op.drop_index("ix_market_requirements_requested_by_updated", table_name="market_requirements")
    op.drop_table("market_requirements")

"""quotes: business details for the letterhead, and issued quotes / proformas

Revision ID: 0022
Revises: 0021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "business_details",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("company_name", sa.String(length=160), nullable=True),
        sa.Column("address", sa.String(length=400), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("tax_id", sa.String(length=60), nullable=True),
        sa.Column("bank_details", sa.Text(), nullable=True),
        sa.Column("next_quote", sa.Integer(), server_default="1", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_business_details_user_id_users"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_business_details")),
    )  # fmt: skip
    op.create_table(
        "quotes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(length=20), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("hs6", sa.CHAR(length=6), nullable=False),
        sa.Column("market", sa.CHAR(length=3), nullable=False),
        sa.Column("buyer_name", sa.String(length=160), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("total_usd", sa.Numeric(14, 2), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_quotes_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"], ["pipeline_contacts.id"],
            name=op.f("fk_quotes_contact_id_pipeline_contacts"), ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotes")),
    )  # fmt: skip
    op.create_index("ix_quotes_user_created", "quotes", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_quotes_user_created", table_name="quotes")
    op.drop_table("quotes")
    op.drop_table("business_details")

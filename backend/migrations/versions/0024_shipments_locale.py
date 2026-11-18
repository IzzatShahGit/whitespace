"""shipments (documents per won deal), invoice numbering, REX number; users.locale

Revision ID: 0024
Revises: 0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.text("now()")


def upgrade() -> None:
    op.add_column("users", sa.Column("locale", sa.String(length=8), nullable=True))
    op.add_column("business_details", sa.Column("rex_number", sa.String(length=40), nullable=True))
    op.add_column(
        "business_details",
        sa.Column("next_invoice", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_table(
        "shipments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("quote_id", sa.Uuid(), nullable=True),
        sa.Column("invoice_number", sa.String(length=20), nullable=False),
        sa.Column("hs6", sa.CHAR(length=6), nullable=False),
        sa.Column("market", sa.CHAR(length=3), nullable=False),
        sa.Column("buyer_name", sa.String(length=160), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_shipments_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["quote_id"], ["quotes.id"], name=op.f("fk_shipments_quote_id_quotes"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shipments")),
        sa.UniqueConstraint("quote_id", name=op.f("uq_shipments_quote_id")),
    )  # fmt: skip
    op.create_index("ix_shipments_user_created", "shipments", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_shipments_user_created", table_name="shipments")
    op.drop_table("shipments")
    op.drop_column("business_details", "next_invoice")
    op.drop_column("business_details", "rex_number")
    op.drop_column("users", "locale")

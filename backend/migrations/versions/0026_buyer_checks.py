"""sanction_sources + sanction_names (official lists, trigram-searchable); buyer_checks

Revision ID: 0026
Revises: 0025
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "sanction_sources",
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("loaded_at", TS, nullable=True),
        sa.Column("checked_at", TS, nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("parties", sa.Integer(), server_default="0", nullable=False),
        sa.Column("names", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error", sa.String(length=300), nullable=True),
        sa.PrimaryKeyConstraint("source", name=op.f("pk_sanction_sources")),
    )
    op.create_table(
        "sanction_names",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("ref", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=400), nullable=False),
        sa.Column("name_core", sa.String(length=400), nullable=False),
        sa.Column("program", sa.String(length=300), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sanction_names")),
    )
    op.create_index(
        "ix_sanction_names_core_trgm", "sanction_names", ["name_core"],
        postgresql_using="gin", postgresql_ops={"name_core": "gin_trgm_ops"},
    )  # fmt: skip
    op.create_index("ix_sanction_names_source", "sanction_names", ["source"])
    op.create_table(
        "buyer_checks",
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("verdict", sa.String(length=5), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("checked_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["contact_id"], ["pipeline_contacts.id"],
            name=op.f("fk_buyer_checks_contact_id_pipeline_contacts"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("contact_id", name=op.f("pk_buyer_checks")),
    )  # fmt: skip


def downgrade() -> None:
    op.drop_table("buyer_checks")
    op.drop_index("ix_sanction_names_source", table_name="sanction_names")
    op.drop_index("ix_sanction_names_core_trgm", table_name="sanction_names")
    op.drop_table("sanction_names")
    op.drop_table("sanction_sources")

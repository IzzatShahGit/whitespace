"""pipeline: outreach contacts and events; job leases, email sends, email verification;
users.digest_enabled

Revision ID: 0021
Revises: 0020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.text("now()")


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("digest_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_table(
        "pipeline_contacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("hs6", sa.CHAR(length=6), nullable=False),
        sa.Column("market", sa.CHAR(length=3), nullable=False),
        sa.Column("side", sa.String(length=10), server_default="buyers", nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("name_key", sa.String(length=160), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=True),
        sa.Column("city", sa.String(length=80), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("stage", sa.String(length=12), server_default="to_contact", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("follow_up_on", sa.Date(), nullable=True),
        sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_pipeline_contacts_user_id_users"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pipeline_contacts")),
        sa.UniqueConstraint("user_id", "hs6", "market", "name_key", name="uq_pipeline_contact"),
    )  # fmt: skip
    op.create_index(
        "ix_pipeline_contacts_user_updated", "pipeline_contacts", ["user_id", "updated_at"]
    )
    op.create_index("ix_pipeline_contacts_follow_up", "pipeline_contacts", ["follow_up_on"])
    op.create_table(
        "pipeline_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("detail", sa.String(length=300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.ForeignKeyConstraint(
            ["contact_id"], ["pipeline_contacts.id"],
            name=op.f("fk_pipeline_events_contact_id_pipeline_contacts"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pipeline_events")),
    )  # fmt: skip
    op.create_index(
        "ix_pipeline_events_contact_created", "pipeline_events", ["contact_id", "created_at"]
    )
    op.create_table(
        "job_leases",
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("holder", sa.Uuid(), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_ok_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=300), nullable=True),
        sa.PrimaryKeyConstraint("name", name=op.f("pk_job_leases")),
    )
    op.create_table(
        "email_sends",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_email_sends_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "kind", "period", name=op.f("pk_email_sends")),
    )
    op.create_table(
        "email_verifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_email_verifications_user_id_users"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_verifications")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_email_verifications_token_hash")),
    )  # fmt: skip
    op.create_index(
        op.f("ix_email_verifications_user_id"), "email_verifications", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_email_verifications_user_id"), table_name="email_verifications")
    op.drop_table("email_verifications")
    op.drop_table("email_sends")
    op.drop_table("job_leases")
    op.drop_index("ix_pipeline_events_contact_created", table_name="pipeline_events")
    op.drop_table("pipeline_events")
    op.drop_index("ix_pipeline_contacts_follow_up", table_name="pipeline_contacts")
    op.drop_index("ix_pipeline_contacts_user_updated", table_name="pipeline_contacts")
    op.drop_table("pipeline_contacts")
    op.drop_column("users", "digest_enabled")

"""admin: last seen and test accounts on users, daily activity, visits, admin actions

Revision ID: 0029
Revises: 0028
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users", sa.Column("is_test", sa.Boolean(), server_default=sa.text("false"), nullable=False)
    )
    # Best guess for existing accounts: last seen when they last signed in.
    op.execute("UPDATE users SET last_seen_at = coalesce(last_login_at, created_at)")

    op.create_table(
        "user_activity_days",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_activity_days_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "day", name=op.f("pk_user_activity_days")),
    )
    op.create_index("ix_user_activity_days_day", "user_activity_days", ["day"])
    # Days we already know about: the sign-up day and the last sign-in day.
    op.execute(
        """
        INSERT INTO user_activity_days (user_id, day)
        SELECT id, (created_at AT TIME ZONE 'UTC')::date FROM users
        UNION
        SELECT id, (last_login_at AT TIME ZONE 'UTC')::date FROM users
        WHERE last_login_at IS NOT NULL
        """
    )

    op.create_table(
        "admin_actions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("admin_email", sa.String(length=320), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("target_email", sa.String(length=320), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["users.id"],
            name=op.f("fk_admin_actions_target_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_actions")),
    )
    op.create_index(op.f("ix_admin_actions_target_id"), "admin_actions", ["target_id"])

    op.create_table(
        "visits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("visitor", sa.CHAR(length=16), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("country", sa.CHAR(length=2), nullable=True),
        sa.Column("source", sa.String(length=60), nullable=False),
        sa.Column("referrer", sa.String(length=120), nullable=True),
        sa.Column("utm_campaign", sa.String(length=60), nullable=True),
        sa.Column("landing", sa.String(length=120), nullable=False),
        sa.Column("device", sa.String(length=10), nullable=False),
        sa.Column("browser", sa.String(length=20), nullable=False),
        sa.Column("os", sa.String(length=20), nullable=False),
        sa.Column("pages", sa.Integer(), nullable=False),
        sa.Column("engaged_seconds", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_visits_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visits")),
    )
    op.create_index("ix_visits_started", "visits", ["started_at"])
    op.create_index("ix_visits_user_started", "visits", ["user_id", "started_at"])
    op.create_index("ix_visits_visitor_last_seen", "visits", ["visitor", "last_seen_at"])

    op.create_table(
        "visit_pages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.String(length=120), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("seconds", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["visit_id"],
            ["visits.id"],
            name=op.f("fk_visit_pages_visit_id_visits"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visit_pages")),
    )
    op.create_index("ix_visit_pages_visit_at", "visit_pages", ["visit_id", "at"])


def downgrade() -> None:
    op.drop_table("visit_pages")
    op.drop_table("visits")
    op.drop_table("admin_actions")
    op.drop_table("user_activity_days")
    op.drop_column("users", "is_test")
    op.drop_column("users", "last_seen_at")

"""watches and notifications

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-16 06:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0014'
down_revision: str | None = '0013'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('watches',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('exporter', sa.CHAR(length=3), nullable=False),
    sa.Column('hs6', sa.CHAR(length=6), nullable=False),
    sa.Column('market', sa.CHAR(length=3), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_watches_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_watches')),
    sa.UniqueConstraint('user_id', 'exporter', 'hs6', 'market', name='uq_watches_user_pair')
    )
    op.create_index('ix_watches_market_hs6', 'watches', ['market', 'hs6'], unique=False)
    op.create_table('notifications',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=40), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('link', sa.String(length=300), nullable=True),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('dedupe_key', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notifications_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications')),
    sa.UniqueConstraint('user_id', 'dedupe_key', name='uq_notifications_user_dedupe')
    )
    op.create_index('ix_notifications_user_created', 'notifications', ['user_id', sa.text('created_at DESC')], unique=False)
    op.create_index('ix_notifications_user_unread', 'notifications', ['user_id'], unique=False, postgresql_where=sa.text('read_at IS NULL'))


def downgrade() -> None:
    op.drop_index('ix_notifications_user_unread', table_name='notifications', postgresql_where=sa.text('read_at IS NULL'))
    op.drop_index('ix_notifications_user_created', table_name='notifications')
    op.drop_table('notifications')
    op.drop_index('ix_watches_market_hs6', table_name='watches')
    op.drop_table('watches')

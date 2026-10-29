"""messages between users, blocks, reports, notifications

Revision ID: 0005_messages
Revises: 0004_phone_login
"""
from alembic import op
import sqlalchemy as sa


revision = '0005_messages'
down_revision = '0004_phone_login'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sender_id', sa.Integer(), nullable=False),
        sa.Column('recipient_id', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.Text(), nullable=False),
        sa.Column('read_at', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id']),
        sa.ForeignKeyConstraint(['recipient_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_messages_pair', 'messages', ['sender_id', 'recipient_id'])
    op.create_index('idx_messages_unread', 'messages', ['recipient_id', 'read_at'])

    op.create_table(
        'blocks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('blocker_id', sa.Integer(), nullable=False),
        sa.Column('blocked_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['blocker_id'], ['users.id']),
        sa.ForeignKeyConstraint(['blocked_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('blocker_id', 'blocked_id', name='uq_block_pair'),
    )

    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reporter_id', sa.Integer(), nullable=False),
        sa.Column('reported_id', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['reporter_id'], ['users.id']),
        sa.ForeignKeyConstraint(['reported_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.Text(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('link', sa.Text(), nullable=True),
        sa.Column('created_at', sa.Text(), nullable=False),
        sa.Column('read_at', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_notifications_user', 'notifications', ['user_id', 'read_at'])


def downgrade():
    op.drop_index('idx_notifications_user', table_name='notifications')
    op.drop_table('notifications')
    op.drop_table('reports')
    op.drop_table('blocks')
    op.drop_index('idx_messages_unread', table_name='messages')
    op.drop_index('idx_messages_pair', table_name='messages')
    op.drop_table('messages')

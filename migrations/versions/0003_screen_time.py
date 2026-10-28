"""screen time per user per day

Revision ID: 0003_screen_time
Revises: 0002_forwarding
"""
from alembic import op
import sqlalchemy as sa


revision = '0003_screen_time'
down_revision = '0002_forwarding'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_activity',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('day', sa.Text(), nullable=False),
        sa.Column('seconds', sa.Integer(), nullable=False),
        sa.Column('last_ping', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'day', name='uq_activity_user_day'),
    )


def downgrade():
    op.drop_table('user_activity')

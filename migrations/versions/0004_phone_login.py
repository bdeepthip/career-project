"""phone number log-in

Revision ID: 0004_phone_login
Revises: 0003_screen_time
"""
from alembic import op
import sqlalchemy as sa


revision = '0004_phone_login'
down_revision = '0003_screen_time'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('phone', sa.Text(), nullable=True))
    op.create_index('uq_users_phone', 'users', ['phone'], unique=True)
    op.create_table(
        'phone_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('phone', sa.Text(), nullable=False),
        sa.Column('code_hash', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.Text(), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_phone_codes_phone', 'phone_codes', ['phone'], unique=False)


def downgrade():
    op.drop_index('ix_phone_codes_phone', table_name='phone_codes')
    op.drop_table('phone_codes')
    op.drop_index('uq_users_phone', table_name='users')
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('phone')

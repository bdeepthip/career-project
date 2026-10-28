"""forwarding address for every user

Adds users.inbound_token (the secret part of each user's JobTrack
forwarding address) and gives every existing user one.

Revision ID: 0002_forwarding
Revises: 4059315dae7f
"""
from alembic import op
import sqlalchemy as sa

from jobtrack.models import new_inbound_token


revision = '0002_forwarding'
down_revision = '4059315dae7f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('inbound_token', sa.Text(), nullable=True))

    users = sa.table('users', sa.column('id', sa.Integer),
                     sa.column('inbound_token', sa.Text))
    conn = op.get_bind()
    for (user_id,) in conn.execute(sa.select(users.c.id)).fetchall():
        conn.execute(users.update().where(users.c.id == user_id)
                     .values(inbound_token=new_inbound_token()))

    op.create_index('uq_users_inbound_token', 'users', ['inbound_token'], unique=True)


def downgrade():
    op.drop_index('uq_users_inbound_token', table_name='users')
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('inbound_token')

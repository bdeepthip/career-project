"""initial schema

The tables JobTrack already had before migrations existed.

Every table and index uses if_not_exists=True, so running this on a
database created by the old schema.sql leaves existing tables and data
untouched and simply records that the database is at this version.
On a brand-new database (e.g. PostgreSQL in production) it creates
everything.

Revision ID: 4059315dae7f
Revises: 
Create Date: 2026-10-28 12:37:22.207284

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4059315dae7f'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('jobs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('company', sa.Text(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('domain', sa.Text(), nullable=True),
    sa.Column('location', sa.Text(), nullable=True),
    sa.Column('experience_level', sa.Text(), nullable=True),
    sa.Column('required_skills', sa.Text(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('job_url', sa.Text(), nullable=True),
    sa.Column('posted_date', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    if_not_exists=True,
    )
    op.create_table('learning_resources',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('skill_name', sa.Text(), nullable=False),
    sa.Column('resource_name', sa.Text(), nullable=False),
    sa.Column('provider', sa.Text(), nullable=True),
    sa.Column('url', sa.Text(), nullable=True),
    sa.Column('estimated_hours', sa.Integer(), nullable=True),
    sa.Column('cost', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('skill_name'),
    if_not_exists=True,
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('email', sa.Text(), nullable=False),
    sa.Column('password', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    if_not_exists=True,
    )
    op.create_table('education',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('institution', sa.Text(), nullable=False),
    sa.Column('degree', sa.Text(), nullable=False),
    sa.Column('field_of_study', sa.Text(), nullable=True),
    sa.Column('start_year', sa.Text(), nullable=True),
    sa.Column('end_year', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    if_not_exists=True,
    )
    op.create_table('experience',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('company', sa.Text(), nullable=False),
    sa.Column('job_title', sa.Text(), nullable=False),
    sa.Column('location', sa.Text(), nullable=True),
    sa.Column('start_date', sa.Text(), nullable=True),
    sa.Column('end_date', sa.Text(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    if_not_exists=True,
    )
    op.create_table('job_applications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('company', sa.Text(), nullable=False),
    sa.Column('job_title', sa.Text(), nullable=False),
    sa.Column('location', sa.Text(), nullable=True),
    sa.Column('job_url', sa.Text(), nullable=True),
    sa.Column('date_applied', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), server_default='Applied', nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    if_not_exists=True,
    )
    op.create_index('idx_applications_user', 'job_applications', ['user_id'], unique=False, if_not_exists=True)

    op.create_table('profiles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('headline', sa.Text(), nullable=True),
    sa.Column('phone', sa.Text(), nullable=True),
    sa.Column('location', sa.Text(), nullable=True),
    sa.Column('domain', sa.Text(), nullable=True),
    sa.Column('target_role', sa.Text(), nullable=True),
    sa.Column('experience_level', sa.Text(), nullable=True),
    sa.Column('preferred_location', sa.Text(), nullable=True),
    sa.Column('about', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id'),
    if_not_exists=True,
    )
    op.create_table('skills',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('skill_name', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    if_not_exists=True,
    )
    op.create_index('idx_skills_user', 'skills', ['user_id'], unique=False, if_not_exists=True)

    op.create_table('job_emails',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('message_id', sa.Text(), nullable=True),
    sa.Column('sender', sa.Text(), nullable=True),
    sa.Column('subject', sa.Text(), nullable=True),
    sa.Column('body', sa.Text(), nullable=True),
    sa.Column('received_at', sa.Text(), nullable=True),
    sa.Column('detected_status', sa.Text(), nullable=True),
    sa.Column('application_id', sa.Integer(), nullable=True),
    sa.Column('update_note', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['application_id'], ['job_applications.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'message_id'),
    if_not_exists=True,
    )
    op.create_index('idx_emails_user', 'job_emails', ['user_id'], unique=False, if_not_exists=True)



def downgrade():
    with op.batch_alter_table('job_emails', schema=None) as batch_op:
        batch_op.drop_index('idx_emails_user')

    op.drop_table('job_emails')
    with op.batch_alter_table('skills', schema=None) as batch_op:
        batch_op.drop_index('idx_skills_user')

    op.drop_table('skills')
    op.drop_table('profiles')
    with op.batch_alter_table('job_applications', schema=None) as batch_op:
        batch_op.drop_index('idx_applications_user')

    op.drop_table('job_applications')
    op.drop_table('experience')
    op.drop_table('education')
    op.drop_table('users')
    op.drop_table('learning_resources')
    op.drop_table('jobs')

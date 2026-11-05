"""resume builder: resume versions built inside Roleflow

Revision ID: 0007_resume_builder
Revises: 0006_easy_apply
"""
from alembic import op
import sqlalchemy as sa


revision = '0007_resume_builder'
down_revision = '0006_easy_apply'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'resume_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('target_text', sa.Text(), nullable=True),
        sa.Column('content_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_resume_versions_user', 'resume_versions', ['user_id'])


def downgrade():
    op.drop_index('idx_resume_versions_user', table_name='resume_versions')
    op.drop_table('resume_versions')

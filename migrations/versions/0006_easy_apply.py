"""employer accounts, resumes, Easy Apply submissions

Revision ID: 0006_easy_apply
Revises: 0005_messages
"""
from alembic import op
import sqlalchemy as sa


revision = '0006_easy_apply'
down_revision = '0005_messages'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('account_type', sa.Text(), nullable=False, server_default='seeker'))
    op.add_column('users', sa.Column('company', sa.Text(), nullable=True))

    # SQLite can't add a foreign key to an existing table in place; batch mode
    # rebuilds the table there and is a plain ALTER on PostgreSQL
    with op.batch_alter_table('jobs') as batch_op:
        batch_op.add_column(sa.Column('posted_by_user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('is_open', sa.Integer(), nullable=False, server_default='1'))
        batch_op.create_foreign_key('fk_jobs_posted_by', 'users', ['posted_by_user_id'], ['id'])

    op.create_table(
        'resumes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.Text(), nullable=False),
        sa.Column('data', sa.LargeBinary(), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('uploaded_at', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )

    op.create_table(
        'submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('applicant_id', sa.Integer(), nullable=False),
        sa.Column('application_id', sa.Integer(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('profile_json', sa.Text(), nullable=False),
        sa.Column('resume_filename', sa.Text(), nullable=True),
        sa.Column('resume_data', sa.LargeBinary(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('created_at', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id']),
        sa.ForeignKeyConstraint(['applicant_id'], ['users.id']),
        sa.ForeignKeyConstraint(['application_id'], ['job_applications.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id', 'applicant_id', name='uq_submission_job_applicant'),
    )
    op.create_index('idx_submissions_job', 'submissions', ['job_id'])


def downgrade():
    op.drop_index('idx_submissions_job', table_name='submissions')
    op.drop_table('submissions')
    op.drop_table('resumes')
    with op.batch_alter_table('jobs') as batch_op:
        batch_op.drop_constraint('fk_jobs_posted_by', type_='foreignkey')
        batch_op.drop_column('is_open')
        batch_op.drop_column('posted_by_user_id')
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('company')
        batch_op.drop_column('account_type')

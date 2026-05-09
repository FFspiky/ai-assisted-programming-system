"""Add indexes for submission queries

Revision ID: 9c1f0f4f0a51
Revises: be074cf3578a
Create Date: 2026-05-09 00:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '9c1f0f4f0a51'
down_revision = 'be074cf3578a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('submission', schema=None) as batch_op:
        batch_op.create_index('ix_submission_status', ['status'], unique=False)
        batch_op.create_index('ix_submission_timestamp', ['timestamp'], unique=False)
        batch_op.create_index('ix_submission_user_id', ['user_id'], unique=False)
        batch_op.create_index('ix_submission_problem_id', ['problem_id'], unique=False)


def downgrade():
    with op.batch_alter_table('submission', schema=None) as batch_op:
        batch_op.drop_index('ix_submission_problem_id')
        batch_op.drop_index('ix_submission_user_id')
        batch_op.drop_index('ix_submission_timestamp')
        batch_op.drop_index('ix_submission_status')

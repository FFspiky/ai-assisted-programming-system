"""Persist submission evidence and grounded diagnosis.

Revision ID: c41e20261012
Revises: 9c1f0f4f0a51
"""

from alembic import op
import sqlalchemy as sa

revision = "c41e20261012"
down_revision = "9c1f0f4f0a51"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("problem") as batch:
        batch.add_column(
            sa.Column("judge_mode", sa.String(20), nullable=False, server_default="text")
        )
    with op.batch_alter_table("test_case") as batch:
        batch.add_column(
            sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.true())
        )
    with op.batch_alter_table("submission") as batch:
        batch.add_column(sa.Column("evidence_snapshot", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("diagnosis", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("submission") as batch:
        batch.drop_column("diagnosis")
        batch.drop_column("evidence_snapshot")
    with op.batch_alter_table("test_case") as batch:
        batch.drop_column("is_public")
    with op.batch_alter_table("problem") as batch:
        batch.drop_column("judge_mode")

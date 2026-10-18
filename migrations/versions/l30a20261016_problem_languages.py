"""Problem-based co-creation, reusable proposals and project languages.

Revision ID: l30a20261016
Revises: k29a20261015
"""

from alembic import op
import sqlalchemy as sa

revision = "l30a20261016"
down_revision = "k29a20261015"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for table, additions in {
        "co_create_session": [
            sa.Column("problem_id", sa.String(50), nullable=True),
            sa.Column("language", sa.String(20), nullable=False, server_default="python"),
        ],
        "task_room_project": [
            sa.Column("language", sa.String(16), nullable=False, server_default="python")
        ],
        "task_room_run": [
            sa.Column("language", sa.String(16), nullable=False, server_default="python")
        ],
    }.items():
        existing = {column["name"] for column in inspector.get_columns(table)}
        with op.batch_alter_table(table) as batch:
            for column in additions:
                if column.name not in existing:
                    batch.add_column(column)
            if table == "co_create_session" and "problem_id" not in existing:
                batch.create_index("ix_co_create_session_problem_id", ["problem_id"])
    existing = {column["name"] for column in inspector.get_columns("code_proposal")}
    with op.batch_alter_table("code_proposal") as batch:
        batch.alter_column("help_id", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("submission_id", existing_type=sa.Integer(), nullable=True)
        for column in [
            sa.Column("problem_id", sa.String(50), nullable=True),
            sa.Column("language", sa.String(16), nullable=True),
            sa.Column("source", sa.String(20), nullable=False, server_default="panel"),
            sa.Column("co_create_session_id", sa.String(32), nullable=True),
            sa.Column("co_create_candidate_id", sa.String(100), nullable=True),
        ]:
            if column.name not in existing:
                batch.add_column(column)
        if "co_create_session_id" not in existing:
            batch.create_unique_constraint(
                "uq_proposal_co_create", ["co_create_session_id", "co_create_candidate_id"]
            )
        if "problem_id" not in existing:
            batch.create_index("ix_code_proposal_problem_id", ["problem_id"])


def downgrade():
    # New proposals cannot be represented by the old NOT NULL foreign keys.
    # Downgrading would silently discard user work; restore the pre-upgrade backup instead.
    raise RuntimeError(
        "This migration preserves new user work. Restore a pre-upgrade backup to downgrade."
    )

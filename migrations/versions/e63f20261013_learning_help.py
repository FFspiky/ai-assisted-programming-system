"""Persist learning mode, explicit help requests and returned content."""

from alembic import op
import sqlalchemy as sa

revision = "e63f20261013"
down_revision = "d52e20261012"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("user")}
    with op.batch_alter_table("user") as batch:
        if "help_mode" not in columns:
            batch.add_column(
                sa.Column("help_mode", sa.String(20), nullable=False, server_default="learning")
            )
        if "help_revision" not in columns:
            batch.add_column(
                sa.Column("help_revision", sa.Integer(), nullable=False, server_default="0")
            )
    # The existing app's create_all can create this table before a CLI migration.
    if inspector.has_table("learning_help"):
        expected = {
            "id",
            "user_id",
            "submission_id",
            "source",
            "mode",
            "mode_revision",
            "requested_level",
            "returned_level",
            "state",
            "request_snapshot",
            "result",
            "model",
            "prompt_version",
            "created_at",
            "shown_at",
        }
        if {column["name"] for column in inspector.get_columns("learning_help")} != expected:
            raise RuntimeError("Existing learning_help table does not match the migration")
        return
    op.create_table(
        "learning_help",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submission.id"), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("mode_revision", sa.Integer(), nullable=False),
        sa.Column("requested_level", sa.Integer(), nullable=False),
        sa.Column("returned_level", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("request_snapshot", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("prompt_version", sa.String(60), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("shown_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_learning_help_user_id", "learning_help", ["user_id"])
    op.create_index("ix_learning_help_submission_id", "learning_help", ["submission_id"])


def downgrade():
    op.drop_table("learning_help")
    with op.batch_alter_table("user") as batch:
        batch.drop_column("help_revision")
        batch.drop_column("help_mode")

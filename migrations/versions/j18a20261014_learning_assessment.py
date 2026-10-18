"""Persist short questionnaire and task-room learning recommendations."""

from alembic import op
import sqlalchemy as sa

revision = "j18a20261014"
down_revision = "i07a20261014"
branch_labels = None
depends_on = None


def upgrade():
    if "learning_assessment" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "learning_assessment",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False, unique=True
            ),
            sa.Column("answers", sa.JSON(), nullable=False),
            sa.Column("recommended_ids", sa.JSON(), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )


def downgrade():
    op.drop_table("learning_assessment")

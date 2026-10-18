"""Save example-driven creation and code-review learning sessions."""

from alembic import op
import sqlalchemy as sa

revision = "k29a20261015"
down_revision = "j18a20261014"
branch_labels = None
depends_on = None


def upgrade():
    if "co_create_session" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "co_create_session",
            sa.Column("id", sa.String(length=32), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("mode", sa.String(length=16), nullable=False),
            sa.Column("scenario_id", sa.String(length=40), nullable=False),
            sa.Column("title", sa.String(length=120), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("state", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_co_create_session_user_id", "co_create_session", ["user_id"])


def downgrade():
    op.drop_index("ix_co_create_session_user_id", table_name="co_create_session")
    op.drop_table("co_create_session")

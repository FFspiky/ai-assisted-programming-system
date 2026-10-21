"""Per-user encrypted AI credentials."""

from alembic import op
import sqlalchemy as sa

revision = "m41a20261021"
down_revision = "l30a20261016"
branch_labels = None
depends_on = None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table("user_ai_settings"):
        op.create_table(
            "user_ai_settings",
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), primary_key=True),
            sa.Column("mode", sa.String(16), nullable=False),
            sa.Column("encrypted_key", sa.LargeBinary(), nullable=True),
        )


def downgrade():
    op.drop_table("user_ai_settings")

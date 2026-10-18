"""Add independent creation records without changing exercises or user history."""

from alembic import op
import sqlalchemy as sa

revision = "h96a20261014"
down_revision = "g85a20261014"
branch_labels = None
depends_on = None


def upgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "workshop_suggestion" not in tables:
        op.create_table(
            "workshop_suggestion",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("scene", sa.String(20), nullable=False),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column("base_fingerprint", sa.String(64), nullable=False),
            sa.Column("result", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_workshop_suggestion_user_id", "workshop_suggestion", ["user_id"])
    if "workshop_run" not in tables:
        op.create_table(
            "workshop_run",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("scene", sa.String(20), nullable=False),
            sa.Column("title", sa.String(80), nullable=False),
            sa.Column("code", sa.Text(), nullable=False),
            sa.Column("params", sa.JSON(), nullable=False),
            sa.Column("trace", sa.JSON(), nullable=False),
            sa.Column("execution", sa.JSON(), nullable=False),
            sa.Column("provenance", sa.JSON(), nullable=False),
            sa.Column("fingerprint", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_workshop_run_user_id", "workshop_run", ["user_id"])
    if "workshop_project" not in tables:
        op.create_table(
            "workshop_project",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("title", sa.String(80), nullable=False),
            sa.Column("scene", sa.String(20), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_workshop_project_user_id", "workshop_project", ["user_id"])
    if "workshop_version" not in tables:
        op.create_table(
            "workshop_version",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "project_id", sa.Integer(), sa.ForeignKey("workshop_project.id"), nullable=False
            ),
            sa.Column("run_id", sa.Integer(), sa.ForeignKey("workshop_run.id"), nullable=False),
            sa.Column("number", sa.Integer(), nullable=False),
            sa.Column("palette", sa.String(20), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("project_id", "number", name="uq_workshop_version"),
        )
        op.create_index("ix_workshop_version_project_id", "workshop_version", ["project_id"])


def downgrade():
    for name in ("workshop_version", "workshop_project", "workshop_run", "workshop_suggestion"):
        op.drop_table(name)

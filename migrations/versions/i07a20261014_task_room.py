"""Add standalone AI task room without changing practice or workshop history."""

from alembic import op
import sqlalchemy as sa

revision = "i07a20261014"
down_revision = "h96a20261014"
branch_labels = None
depends_on = None


def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "task_room_project" not in existing:
        op.create_table(
            "task_room_project",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("scenario_id", sa.String(40), nullable=False),
            sa.Column("title", sa.String(120), nullable=False),
            sa.Column("state", sa.String(20), nullable=False),
            sa.Column("archived", sa.Boolean(), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("draft_revision", sa.Integer(), nullable=False),
            sa.Column("code", sa.Text(), nullable=False),
            sa.Column("delivery", sa.JSON(), nullable=True),
            sa.Column("events", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_task_room_project_user_id", "task_room_project", ["user_id"])
    if "task_room_contract" not in existing:
        op.create_table(
            "task_room_contract",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column(
                "project_id", sa.String(32), sa.ForeignKey("task_room_project.id"), nullable=False
            ),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("snapshot", sa.JSON(), nullable=False),
            sa.Column("change_id", sa.String(40), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("project_id", "version", name="uq_task_room_contract_version"),
        )
        op.create_index("ix_task_room_contract_project_id", "task_room_contract", ["project_id"])
    if "task_room_message" not in existing:
        op.create_table(
            "task_room_message",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column(
                "project_id", sa.String(32), sa.ForeignKey("task_room_project.id"), nullable=False
            ),
            sa.Column("role", sa.String(16), nullable=False),
            sa.Column("intent", sa.String(20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("model", sa.String(120), nullable=True),
            sa.Column("operation_id", sa.String(64), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "project_id", "operation_id", name="uq_task_room_message_operation"
            ),
        )
        op.create_index("ix_task_room_message_project_id", "task_room_message", ["project_id"])
    if "task_room_run" not in existing:
        op.create_table(
            "task_room_run",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column(
                "project_id", sa.String(32), sa.ForeignKey("task_room_project.id"), nullable=False
            ),
            sa.Column(
                "contract_id", sa.String(32), sa.ForeignKey("task_room_contract.id"), nullable=False
            ),
            sa.Column("contract_version", sa.Integer(), nullable=False),
            sa.Column("kind", sa.String(16), nullable=False),
            sa.Column("code", sa.Text(), nullable=False),
            sa.Column("code_hash", sa.String(64), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("passed", sa.Integer(), nullable=False),
            sa.Column("total", sa.Integer(), nullable=False),
            sa.Column("results", sa.JSON(), nullable=False),
            sa.Column("execution", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_task_room_run_project_id", "task_room_run", ["project_id"])


def downgrade():
    for table in ("task_room_run", "task_room_message", "task_room_contract", "task_room_project"):
        op.drop_table(table)

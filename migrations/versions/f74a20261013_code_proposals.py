"""Persist exact code proposals and auditable practice actions."""

from alembic import op
import sqlalchemy as sa

revision = "f74a20261013"
down_revision = "e63f20261013"
branch_labels = None
depends_on = None


def upgrade():
    # Existing local startup may have run create_all before the migration command.
    metadata = sa.MetaData()
    # Stub referenced tables for SQLAlchemy's foreign-key resolution only.
    for name in ("user", "submission", "learning_help"):
        sa.Table(name, metadata, sa.Column("id", sa.Integer, primary_key=True))
    proposal = sa.Table(
        "code_proposal",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "help_id", sa.Integer, sa.ForeignKey("learning_help.id"), nullable=False, unique=True
        ),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False, index=True),
        sa.Column(
            "submission_id", sa.Integer, sa.ForeignKey("submission.id"), nullable=False, index=True
        ),
        sa.Column("base_code", sa.Text, nullable=False),
        sa.Column("candidate_code", sa.Text, nullable=False),
        sa.Column("edits", sa.JSON, nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    event = sa.Table(
        "practice_event",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False, index=True),
        sa.Column("problem_id", sa.String(50), nullable=False, index=True),
        sa.Column("language", sa.String(50), nullable=False),
        sa.Column("submission_id", sa.Integer, sa.ForeignKey("submission.id")),
        sa.Column("proposal_id", sa.Integer, sa.ForeignKey("code_proposal.id"), index=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("operation_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("user_id", "operation_id", name="uq_practice_operation"),
    )
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in (proposal, event):
        if inspector.has_table(table.name):
            if {c["name"] for c in inspector.get_columns(table.name)} != set(table.columns.keys()):
                raise RuntimeError(f"Existing {table.name} table does not match the migration")
        else:
            table.create(bind)


def downgrade():
    op.drop_table("practice_event")
    op.drop_table("code_proposal")

"""Add problem taxonomy and provenance; keep existing submissions intact."""

from alembic import op
import sqlalchemy as sa

revision = "g85a20261014"
down_revision = "f74a20261013"
branch_labels = None
depends_on = None


def upgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("problem")}
    with op.batch_alter_table("problem") as batch:
        if "category" not in columns:
            batch.add_column(
                sa.Column("category", sa.String(40), nullable=False, server_default="uncategorized")
            )
        if "tags" not in columns:
            batch.add_column(sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"))
        if "source" not in columns:
            batch.add_column(sa.Column("source", sa.String(200), nullable=False, server_default=""))
    # Only classify the project's known demo IDs; do not guess other imported titles.
    for problem_id, category, tags in [
        ("DEMO-01", "control", '["循环", "边界条件"]'),
        ("DEMO-02", "strings", '["字符串", "索引"]'),
        ("DEMO-03", "basics", '["输入输出", "类型转换"]'),
    ]:
        op.execute(
            sa.text(
                "UPDATE problem SET category=:category, tags=:tags WHERE id=:id AND category='uncategorized'"
            ).bindparams(category=category, tags=tags, id=problem_id)
        )


def downgrade():
    with op.batch_alter_table("problem") as batch:
        batch.drop_column("source")
        batch.drop_column("tags")
        batch.drop_column("category")

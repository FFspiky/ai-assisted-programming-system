"""Add editable profiles without inventing historical registration dates."""

from alembic import op
import sqlalchemy as sa

revision = "d52e20261012"
down_revision = "c41e20261012"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user") as batch:
        for name, length in [("display_name", 80), ("bio", 160), ("location", 80)]:
            batch.add_column(sa.Column(name, sa.String(length), nullable=False, server_default=""))
        batch.add_column(sa.Column("avatar_image", sa.LargeBinary(), nullable=True))
        batch.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))
        batch.add_column(
            sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0")
        )
    connection = op.get_bind()
    for problem_id, old_title, title, topic in [
        ("DEMO-01", "循环边界：最后一项去哪了？", "整数求和", "循环的右边界"),
        ("DEMO-02", "字符串索引：找出最后一个字符", "字符串末位字符", "索引范围"),
        ("DEMO-03", "输入处理：数字还是字符串？", "两数相加", "输入类型"),
    ]:
        connection.execute(
            sa.text("UPDATE problem SET title=:title WHERE id=:id AND title=:old"),
            {"id": problem_id, "title": title, "old": old_title},
        )
        connection.execute(
            sa.text("UPDATE problem SET description=replace(description, :note, '') WHERE id=:id"),
            {"id": problem_id, "note": f"<p>项目演示题，AI 辅助编写。主题：{topic}。</p>"},
        )


def downgrade():
    with op.batch_alter_table("user") as batch:
        for name in [
            "auth_version",
            "created_at",
            "avatar_image",
            "location",
            "bio",
            "display_name",
        ]:
            batch.drop_column(name)

"""Create an isolated preview database; copy only legacy problems and test cases."""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--legacy-db", type=Path)
    args = parser.parse_args()
    target = args.database.resolve()
    source = args.legacy_db.resolve() if args.legacy_db else None
    if target == source or target == ROOT / "app.db":
        parser.error("预览必须使用独立数据库，不能覆盖原始 app.db")
    target.parent.mkdir(parents=True, exist_ok=True)
    os.environ.update(
        PYTHON_DOTENV_DISABLED="1",
        DATABASE_URL="sqlite:///" + str(target),
        AUTO_CREATE_DATABASE="0",
        DEEPSEEK_API_KEY="",
        ADMIN_USERNAME="",
        ADMIN_PASSWORD="",
        ADMIN_EMAIL="",
    )
    from flask_migrate import upgrade

    from app import app
    from models import Problem, TestCase, db
    from services.demo_problems import seed_demo_problems
    from services.problem_library import seed_library

    with app.app_context():
        upgrade(directory=str(ROOT / "migrations"))
        seed_demo_problems()
        seed_library()
        imported = 0
        if source:
            connection = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            try:
                for row in connection.execute(
                    "SELECT * FROM problem WHERE id GLOB 'P[0-9]*' ORDER BY id"
                ):
                    if db.session.get(Problem, row["id"]):
                        continue
                    db.session.add(
                        Problem(
                            **{
                                key: row[key]
                                for key in (
                                    "id",
                                    "title",
                                    "description",
                                    "difficulty",
                                    "judge_mode",
                                )
                            },
                            category="uncategorized",
                            tags=[],
                            source="本地原有题库（保留原题与用例）",
                        )
                    )
                    for case in connection.execute(
                        "SELECT * FROM test_case WHERE problem_id=?", (row["id"],)
                    ):
                        db.session.add(
                            TestCase(
                                **{
                                    key: case[key]
                                    for key in (
                                        "problem_id",
                                        "input_data",
                                        "expected_output",
                                        "is_public",
                                    )
                                }
                            )
                        )
                    imported += 1
                db.session.commit()
            finally:
                connection.close()
        print(
            f"Imported legacy: {imported}; total problems: {Problem.query.count()}; database: {target}"
        )


if __name__ == "__main__":
    main()

"""Versioned teaching data. Repeated imports never overwrite existing problems."""

import json
from pathlib import Path

from models import Problem, TestCase, db
from services.problem_metadata import validate_metadata

LIBRARY_PATH = Path(__file__).resolve().parents[1] / "data" / "problem_library.json"


def load_library():
    records = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    ids = set()
    for record in records:
        if record["id"] in ids or len(record["cases"]) < 6:
            raise ValueError("题库存在重复ID或测试用例不足")
        ids.add(record["id"])
        validate_metadata(record["category"], record["tags"], record["source"])
    return records


def seed_library():
    added, skipped = [], []
    try:
        for record in load_library():
            if db.session.get(Problem, record["id"]):
                skipped.append(record["id"])
                continue
            db.session.add(
                Problem(
                    **{
                        key: record[key]
                        for key in (
                            "id",
                            "title",
                            "description",
                            "difficulty",
                            "category",
                            "tags",
                            "source",
                            "judge_mode",
                        )
                    }
                )
            )
            for case in record["cases"]:
                db.session.add(
                    TestCase(
                        problem_id=record["id"],
                        input_data=case["input"],
                        expected_output=case["output"],
                        is_public=case["public"],
                    )
                )
            added.append(record["id"])
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return {"added": added, "skipped": skipped}

"""Retirement boundaries and shared session recovery; no paid API calls."""

import copy
import unittest
from datetime import timedelta

from models import User, db
from modules.co_create import service
from modules.co_create.models import CoCreateSession, now
from tests import test_problem_co_create as fixtures

BASE, app = fixtures.BASE, fixtures.app


def seed_legacy_record(mode="examples"):
    """Model an existing database record, never create it through the retired API."""
    with app.app_context():
        row = CoCreateSession(
            user_id=User.query.filter_by(username="student").one().id,
            mode=mode,
            scenario_id="dedupe",
            title="历史场景",
            language="python",
            state={
                "examples": [{"input": ["A", "A"], "expected": ["A"]}],
                "generations": [],
                "runs": [],
                "events": [],
                "review": {},
            },
        )
        db.session.add(row)
        db.session.commit()
        return service.serialize(row)


class CoCreateRetirementTest(unittest.TestCase):
    setUp = fixtures.ProblemCoCreateTest.setUp
    login = fixtures.ProblemCoCreateTest.login
    data = fixtures.ProblemCoCreateTest.data
    create = fixtures.ProblemCoCreateTest.create
    post = fixtures.ProblemCoCreateTest.post

    def test_catalog_exposes_current_problem_flow_only(self):
        data = self.data(self.client.get(BASE + "/catalog"))
        self.assertTrue(data["problem_driven"])
        self.assertNotIn("scenarios", data)
        self.assertEqual({x["id"] for x in data["languages"]}, {"python", "cpp"})

    def test_old_scene_creation_is_rejected(self):
        response = self.client.post(
            BASE + "/sessions",
            headers=self.headers,
            json={"mode": "examples", "scenario_id": "dedupe"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"]["code"], "PROBLEM_REQUIRED")
        with app.app_context():
            self.assertEqual(CoCreateSession.query.count(), 0)

    def test_history_is_read_only_and_owner_scoped(self):
        row = seed_legacy_record()
        url = BASE + "/sessions/" + row["id"]
        self.assertEqual(self.other.get(url).status_code, 404)
        self.assertEqual(self.data(self.client.get(url))["session"], row)
        for action in (
            "generate",
            "compare",
            "select",
            "review",
            "review-run",
            "review-generate",
            "verify",
        ):
            with self.subTest(action=action):
                self.assertEqual(self.post(row, action, source="ai").status_code, 400)
        response = self.client.patch(
            url, headers=self.headers, json={"revision": 0, "action": "delete_example"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.data(self.client.get(url))["session"], row)
        self.runner.assert_not_called()

    def test_history_read_does_not_recover_or_rewrite_old_generation(self):
        row = seed_legacy_record()
        with app.app_context():
            record = db.session.get(CoCreateSession, row["id"])
            state = copy.deepcopy(record.state)
            state["generations"] = [
                {"status": "running", "created_at": service.stamp(now() - timedelta(minutes=6))}
            ]
            record.state = state
            db.session.commit()
        result = self.data(self.client.get(BASE + "/sessions/" + row["id"]))["session"]
        self.assertEqual(result["revision"], 0)
        self.assertEqual(result["state"]["generations"][0]["status"], "running")

    def test_current_interrupted_generation_still_recovers(self):
        row = self.create()
        with app.app_context():
            record = db.session.get(CoCreateSession, row["id"])
            state = copy.deepcopy(record.state)
            state["generations"] = [
                {
                    "id": "interrupted",
                    "status": "running",
                    "created_at": service.stamp(now() - timedelta(minutes=6)),
                    "candidates": [],
                }
            ]
            record.state = state
            db.session.commit()
        result = self.data(self.client.get(BASE + "/sessions/" + row["id"]))["session"]
        self.assertEqual(result["state"]["generations"][0]["status"], "failed")
        self.assertEqual(result["revision"], row["revision"] + 1)

    def test_retired_assets_and_workshop_entry_are_gone(self):
        for path in (
            "/workshop.html",
            "/co-create-assets/co-create.js",
            "/static/css/index.css",
            "/static/images/wa.png",
        ):
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.get("/co-create.html").status_code, 200)
        for path in ("/co-create-assets/co-create.css", "/co-create-assets/problem-create.js"):
            with self.client.get(path) as response:
                self.assertEqual(response.status_code, 200)

    def test_runtime_does_not_create_retired_workshop_tables(self):
        self.assertFalse(any(name.startswith("workshop_") for name in db.metadata.tables))

import json
import unittest
from unittest.mock import patch

from models import LearningHelp, Submission, User, db
from services.ai_client import AIClientError
from services.learning_help import validate_help
from tests import test_core_security as core


class LearningHelpTest(unittest.TestCase):
    setUp = core.CoreSecurityTest.setUp
    login_admin = core.CoreSecurityTest.login_admin

    def prepare(self):
        from services.demo_problems import seed_demo_problems

        self.headers = {"X-CSRF-Token": self.login_admin().get_json()["csrf_token"]}
        with core.app.app_context():
            seed_demo_problems()
            user = User.query.filter_by(username="admin").one()
            self.uid = user.id
            sub = Submission(
                user_id=user.id,
                problem_id="DEMO-01",
                language="python",
                code_submitted="n=int(input())\ntotal=0\nfor i in range(1,n):\n total+=i\nprint(total)",
                status="Wrong Answer",
                diagnosis={"summary": "OLD_SECRET_FIX", "findings": []},
                evidence_snapshot={
                    "problem": {"title": "求和", "description": "计算1到n的和"},
                    "cases": [
                        {
                            "id": "case-1",
                            "index": 1,
                            "is_public": True,
                            "status": "Wrong Answer",
                            "passed": False,
                            "input": "3",
                            "expected_output": "6",
                            "actual_output": "3",
                        },
                        {
                            "id": "case-2",
                            "index": 2,
                            "is_public": False,
                            "status": "Wrong Answer",
                            "passed": False,
                            "input": "HIDDEN",
                            "expected_output": "SECRET",
                        },
                    ],
                },
            )
            db.session.add(sub)
            db.session.commit()
            self.sid = sub.id

    def post(self, path, data):
        return self.client.post(path, json=data, headers=self.headers)

    def result(self, level):
        return {
            "status": "supported",
            "summary": "检查范围",
            "explanation": "列举覆盖的数值",
            "lines": [] if level == 1 else [3],
            "evidence_ids": ["case-1"],
            "code": "range(1,n+1)" if level >= 3 else "",
        }

    def test_levels_persist_without_revealing_legacy_diagnosis_and_restore_only_requested(self):
        self.prepare()
        data = self.client.get(f"/api/submissions/{self.sid}").get_json()["data"]
        self.assertIsNone(data["diagnosis"])
        self.assertEqual(self.post(f"/api/submissions/{self.sid}/diagnosis", {}).status_code, 409)
        for level in [1, 3]:
            with patch(
                "services.learning_help.chat_completion",
                return_value=json.dumps(self.result(level)),
            ) as ai:
                response = self.post(f"/api/submissions/{self.sid}/help", {"level": level})
                self.assertEqual(response.status_code, 200, response.get_json())
                self.assertNotIn("HIDDEN", json.dumps(ai.call_args.args[0]))
                self.assertNotIn("SECRET", json.dumps(ai.call_args.args[0]))
                record = response.get_json()["data"]
                self.assertEqual(self.post(f'/api/help/{record["id"]}/shown', {}).status_code, 200)
        rows = self.client.get(f"/api/submissions/{self.sid}/help").get_json()["data"]["records"]
        self.assertEqual([r["returned_level"] for r in rows], [1, 3])
        self.assertTrue(all(r["shown_at"] for r in rows))
        with patch("services.learning_help.chat_completion") as ai:
            self.assertEqual(
                self.post(f"/api/submissions/{self.sid}/help", {"level": 3}).status_code, 200
            )
            ai.assert_not_called()

    def test_foreign_submission_invalid_level_and_free_mode_history_are_not_exposed(self):
        self.prepare()
        for level in [0, 5, "4", True]:
            self.assertEqual(
                self.post(f"/api/submissions/{self.sid}/help", {"level": level}).status_code, 400
            )
        self.post("/api/help-settings", {"mode": "free"})
        with patch(
            "services.learning_help.chat_completion", return_value=json.dumps(self.result(4))
        ):
            self.assertEqual(
                self.post(f"/api/submissions/{self.sid}/help", {"level": 4}).status_code, 200
            )
        self.post("/api/help-settings", {"mode": "learning"})
        self.assertEqual(
            self.client.get(f"/api/submissions/{self.sid}/help").get_json()["data"]["records"], []
        )
        with core.app.app_context():
            other = User(username="other", email="other@test.com")
            other.set_password("strongpass")
            db.session.add(other)
            db.session.flush()
            db.session.get(Submission, self.sid).user_id = other.id
            db.session.commit()
        self.assertEqual(
            self.post(f"/api/submissions/{self.sid}/help", {"level": 1}).status_code, 404
        )
        self.assertEqual(self.client.get(f"/api/submissions/{self.sid}/help").status_code, 404)

    def test_mode_change_during_generation_discards_late_answer(self):
        self.prepare()

        def response(*args, **kwargs):
            user = db.session.get(User, self.uid)
            user.help_mode = "free"
            user.help_revision += 1
            db.session.commit()
            return json.dumps(self.result(1))

        with patch("services.learning_help.chat_completion", side_effect=response):
            self.assertEqual(
                self.post(f"/api/submissions/{self.sid}/help", {"level": 1}).status_code, 503
            )
        with core.app.app_context():
            record = LearningHelp.query.filter_by(source="panel").one()
            self.assertEqual(record.state, "cancelled")
            self.assertIsNone(record.result)

    def test_level_shape_rejects_premature_code_or_lines_and_preserves_abstention(self):
        context = {"code": "a\nb\nc", "public_cases": [{"id": "case-1"}]}
        for level, change in [
            (1, {"lines": [3]}),
            (1, {"explanation": "修改第3行"}),
            (2, {"code": "answer"}),
            (3, {"code": "x\n" * 9}),
            (2, {"evidence_ids": ["hidden"]}),
        ]:
            with self.assertRaises(AIClientError):
                validate_help({**self.result(level), **change}, level, context)
        insufficient = {
            "status": "insufficient_evidence",
            "summary": "无法确定",
            "explanation": "证据不足",
            "lines": [],
            "evidence_ids": [],
            "code": "",
        }
        self.assertEqual(validate_help(insufficient, 1, context), insufficient)

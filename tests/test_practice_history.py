import json
import unittest
from unittest.mock import patch

from models import CodeProposal, PracticeEvent, db
from tests import test_core_security as core
from tests import test_learning_help as learning


class PracticeHistoryTest(unittest.TestCase):
    setUp = core.CoreSecurityTest.setUp
    login_admin = core.CoreSecurityTest.login_admin
    prepare = learning.LearningHelpTest.prepare
    post = learning.LearningHelpTest.post
    result = learning.LearningHelpTest.result

    def proposal(self):
        self.prepare()
        with patch(
            "services.learning_help.chat_completion", return_value=json.dumps(self.result(3))
        ):
            response = self.post(f"/api/submissions/{self.sid}/help", {"level": 3})
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()["data"]["proposal"]

    def act(self, p, kind, code=None, key=None):
        return self.post(
            f'/api/proposals/{p["id"]}/actions',
            {
                "action": kind,
                "revision": p["revision"],
                "code": code if code is not None else p["base_code"],
                "language": "python",
                "operation_id": key or f'{kind}-{p["id"]}-{p["revision"]}',
            },
        )

    def test_accept_reject_undo_are_owned_replay_safe_and_protect_edits(self):
        p = self.proposal()
        self.assertEqual(self.act(p, "accept", p["base_code"] + "\n# edited").status_code, 409)
        # Failure must leave both decision and event log untouched.
        with core.app.app_context():
            self.assertEqual(db.session.get(CodeProposal, p["id"]).state, "pending")
            self.assertEqual(PracticeEvent.query.count(), 0)
        accepted = self.act(p, "accept").get_json()["data"]
        self.assertEqual(accepted["editor_code"], p["candidate_code"])
        self.assertTrue(self.act(p, "accept").get_json()["data"]["replayed"])
        current = accepted["proposal"]
        self.assertEqual(
            self.act(current, "undo", p["candidate_code"] + "\n# edit").status_code, 409
        )
        undone = self.act(current, "undo", p["candidate_code"]).get_json()["data"]
        self.assertEqual(undone["editor_code"], p["base_code"])
        rejected = self.act(undone["proposal"], "reject").get_json()["data"]["proposal"]
        self.assertEqual(rejected["state"], "rejected")
        self.assertEqual(self.act(p, "accept").status_code, 409)
        with core.app.app_context():
            self.assertEqual(
                [e.kind for e in PracticeEvent.query.order_by(PracticeEvent.id)],
                ["accept", "undo", "reject"],
            )
        other = core.app.test_client()
        other.post(
            "/api/register",
            json={"username": "other", "email": "other@test.com", "password": "strongpass"},
        )
        token = other.post(
            "/api/login", json={"username": "other", "password": "strongpass"}
        ).get_json()["csrf_token"]
        response = other.post(
            f'/api/proposals/{p["id"]}/actions', headers={"X-CSRF-Token": token}, json={}
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(other.get(f'/api/help/{p["help_id"]}/review').status_code, 404)
        self.assertEqual(
            other.get("/api/problems/DEMO-01/practice-history").get_json()["data"]["submissions"],
            [],
        )

    def test_save_failure_does_not_commit_action(self):
        from sqlalchemy.exc import OperationalError

        p = self.proposal()
        with patch.object(
            db.session, "commit", side_effect=OperationalError("commit", {}, Exception("offline"))
        ):
            response = self.act(p, "accept")
        self.assertEqual(response.status_code, 503)
        with core.app.app_context():
            self.assertEqual(db.session.get(CodeProposal, p["id"]).state, "pending")
            self.assertEqual(PracticeEvent.query.count(), 0)

    def test_real_retests_persist_failure_then_edited_success_without_false_attribution(self):
        p = self.proposal()
        # A model suggestion can be syntactically valid and still wrong.
        with core.app.app_context():
            proposal = db.session.get(CodeProposal, p["id"])
            proposal.candidate_code = p["base_code"].replace("range(1,n)", "range(1,n-1)")
            db.session.commit()
            p["candidate_code"] = proposal.candidate_code
        p = self.act(p, "accept").get_json()["data"]["proposal"]
        body = {
            "problem_id": "DEMO-01",
            "language": "python",
            "code": p["candidate_code"],
            "proposal_id": p["id"],
            "proposal_revision": p["revision"],
            "parent_submission_id": self.sid,
            "operation_id": "first-retest",
        }
        failed = self.post("/api/check-solution", body).get_json()
        self.assertEqual(failed["status"], "Wrong Answer", failed)
        with patch("routes.solution_checker.run_code") as runner:
            repeated = self.post("/api/check-solution", body).get_json()
            self.assertEqual(repeated["submission_id"], failed["submission_id"])
            runner.assert_not_called()
        history = self.client.get("/api/problems/DEMO-01/practice-history").get_json()["data"]
        latest = next(row for row in history["proposals"] if row["id"] == p["id"])
        body.update(
            code=p["base_code"].replace("range(1,n)", "range(1,n+1)"),
            proposal_revision=latest["revision"],
            parent_submission_id=failed["submission_id"],
            operation_id="second-retest",
        )
        passed = self.post("/api/check-solution", body).get_json()
        self.assertEqual(passed["status"], "Accepted", passed)
        self.assertEqual(passed["data"]["evidence"]["executed"], 3)
        history = self.client.get("/api/problems/DEMO-01/practice-history").get_json()["data"]
        latest = next(row for row in history["proposals"] if row["id"] == p["id"])
        self.assertEqual(latest["latest_test"]["code"], body["code"])
        self.assertEqual(latest["latest_test"]["status"], "Accepted")
        self.assertNotEqual(latest["candidate_code"], latest["latest_test"]["code"])
        events = [event for event in history["events"] if event["kind"] == "retest"]
        self.assertEqual([e["data"]["edited_after_accept"] for e in events], [False, True])
        self.assertEqual(events[-1]["submission_id"], passed["submission_id"])
        self.assertEqual(events[-1]["data"]["parent_submission_id"], failed["submission_id"])
        hidden = [
            case
            for sub in history["submissions"]
            for case in sub["evidence"]["cases"]
            if not case["is_public"]
        ]
        self.assertTrue(hidden)
        self.assertTrue(
            all("input" not in case and "expected_output" not in case for case in hidden)
        )
        self.client.post("/api/logout", headers=self.headers)
        self.assertEqual(self.client.get("/api/problems/DEMO-01/practice-history").status_code, 401)

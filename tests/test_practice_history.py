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

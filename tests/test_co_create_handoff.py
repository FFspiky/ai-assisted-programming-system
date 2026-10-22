"""Co-create to original practice flow; isolated DB, no provider or real Docker calls."""

import unittest
from unittest.mock import patch

from models import CodeProposal, PracticeEvent, Problem, Submission, User, db
from modules.co_create import service
from modules.co_create.models import CoCreateSession
from tests import test_problem_co_create as fixtures
from tests.test_co_create import seed_legacy_record

BASE, PID, app, transport = fixtures.BASE, fixtures.PID, fixtures.app, fixtures.transport


class CoCreateHandoffTest(unittest.TestCase):
    # Reuse fixtures, not inheritance: the 16 unrelated tests must not run a second time.
    setUp = fixtures.ProblemCoCreateTest.setUp
    login = fixtures.ProblemCoCreateTest.login
    data = fixtures.ProblemCoCreateTest.data
    create = fixtures.ProblemCoCreateTest.create
    post = fixtures.ProblemCoCreateTest.post
    generate = fixtures.ProblemCoCreateTest.generate

    def handoff(self, row, candidate_id=None, client=None, headers=None, **data):
        if candidate_id is None:
            candidate_id = (
                "review"
                if row["mode"] == "review"
                else row["state"]["generations"][-1]["candidates"][0]["id"]
            )
        return (client or self.client).post(
            BASE + "/sessions/" + row["id"] + "/handoff",
            headers=headers or self.headers,
            json={"revision": row["revision"], "candidate_id": candidate_id, **data},
        )

    def act(self, proposal, kind, code=None, language=None, client=None, headers=None, key=None):
        return (client or self.client).post(
            f'/api/proposals/{proposal["id"]}/actions',
            headers=headers or self.headers,
            json={
                "revision": proposal["revision"],
                "action": kind,
                "code": proposal["base_code"] if code is None else code,
                "language": language or proposal["language"],
                "operation_id": key or f'{kind}-{proposal["id"]}-{proposal["revision"]}',
            },
        )

    def history(self, language="python", client=None):
        return self.data(
            (client or self.client).get(f"/api/problems/{PID}/practice-history?language={language}")
        )

    def test_empty_submission_history_handoff_is_owned_idempotent_and_visible(self):
        row = self.create("review", code="OK", input_text="3661\n")
        result = self.data(self.handoff(row))
        proposal = result["proposal"]
        self.assertEqual(result["problem_id"], PID)
        self.assertEqual(proposal["source"], "co_create")
        self.assertIsNone(proposal["submission_id"])
        self.assertIsNone(proposal["help_id"])
        self.assertEqual(proposal["base_code"], "OK")
        self.assertEqual(proposal["candidate_code"], "OK")
        again = self.data(self.handoff(row))["proposal"]
        self.assertEqual(again["id"], proposal["id"])
        history = self.history()
        self.assertEqual(history["submissions"], [])
        self.assertEqual([p["id"] for p in history["proposals"]], [proposal["id"]])
        self.assertEqual([e["kind"] for e in history["events"]], ["co_create"])
        self.assertEqual(self.history(client=self.other)["proposals"], [])
        self.assertEqual(self.history(language="cpp")["proposals"], [])
        with app.app_context():
            self.assertEqual(Submission.query.count(), 0)
            self.assertEqual(CodeProposal.query.count(), 1)
            self.assertEqual(User.query.filter_by(username="student").first().points, 0)

    def test_accept_undo_retest_reuses_original_attribution_without_fake_parent(self):
        row = self.generate(self.create(code="BASE"), ("AI_OK",))
        candidate = row["state"]["generations"][-1]["candidates"][1]
        proposal = self.data(self.handoff(row, candidate["id"]))["proposal"]
        self.assertTrue(proposal["diff"])
        accepted = self.data(self.act(proposal, "accept"))
        self.assertEqual(accepted["editor_code"], "AI_OK")
        self.assertTrue(self.data(self.act(proposal, "accept"))["replayed"])
        proposal = accepted["proposal"]
        self.assertEqual(self.history()["active_proposal_id"], proposal["id"])
        undone = self.data(self.act(proposal, "undo", code="AI_OK"))
        self.assertEqual(undone["editor_code"], "BASE")
        self.assertIsNone(self.history()["active_proposal_id"])
        proposal = self.data(self.act(undone["proposal"], "accept"))["proposal"]
        with app.app_context():
            self.assertEqual(Submission.query.count(), 0)
            self.assertEqual(User.query.filter_by(username="student").first().points, 0)
        body = {
            "code": "AI_OK",
            "language": "python",
            "problem_id": PID,
            "proposal_id": proposal["id"],
            "proposal_revision": proposal["revision"],
            "operation_id": "co-create-first-formal-retest",
        }
        with patch("routes.solution_checker.run_code", side_effect=transport) as runner:
            judged = self.data(
                self.client.post("/api/check-solution", json=body, headers=self.headers)
            )
            self.assertEqual(judged["status"], "Accepted")
            self.assertEqual(runner.call_count, 6)
            runner.reset_mock()
            replay = self.data(
                self.client.post("/api/check-solution", json=body, headers=self.headers)
            )
            self.assertEqual(replay["submission_id"], judged["submission_id"])
            runner.assert_not_called()
        history = self.history()
        self.assertEqual(len(history["submissions"]), 1)
        latest = next(p for p in history["proposals"] if p["id"] == proposal["id"])
        self.assertEqual(latest["latest_test"]["submission_id"], judged["submission_id"])
        retest = next(e for e in history["events"] if e["kind"] == "retest")
        self.assertIsNone(retest["data"]["parent_submission_id"])
        self.assertFalse(retest["data"]["edited_after_accept"])
        with app.app_context():
            self.assertEqual(Submission.query.count(), 1)
            self.assertEqual(User.query.filter_by(username="student").first().points, 10)

    def test_stale_revision_and_noncurrent_candidate_rejected(self):
        row = self.generate(self.create())
        previous = row["state"]["generations"][-1]["candidates"][0]["id"]
        new_row = self.generate(row)
        self.assertEqual(self.handoff(row, previous).status_code, 409)
        self.assertEqual(self.handoff(new_row, previous).status_code, 404)
        with app.app_context():
            self.assertEqual(CodeProposal.query.count(), 0)
            self.assertEqual(Submission.query.count(), 0)

    def test_cross_user_language_and_edited_draft_cannot_be_overwritten(self):
        row = self.generate(self.create(code="BASE"), ("AI_OK",))
        candidate = row["state"]["generations"][-1]["candidates"][1]["id"]
        self.assertEqual(
            self.handoff(row, candidate, client=self.other, headers=self.other_headers).status_code,
            404,
        )
        proposal = self.data(self.handoff(row, candidate))["proposal"]
        self.assertEqual(self.act(proposal, "accept", language="cpp").status_code, 409)
        self.assertEqual(
            self.act(proposal, "accept", code="BASE\n# edited after opening co-create").status_code,
            409,
        )
        self.assertEqual(
            self.act(proposal, "accept", client=self.other, headers=self.other_headers).status_code,
            404,
        )
        with app.app_context():
            self.assertEqual(db.session.get(CodeProposal, proposal["id"]).state, "pending")
            self.assertEqual(PracticeEvent.query.count(), 1)
        proposal = self.data(self.act(proposal, "accept"))["proposal"]
        self.assertEqual(self.act(proposal, "undo", code="AI_OK\n# further edit").status_code, 409)
        with patch("routes.solution_checker.run_code") as runner:
            response = self.client.post(
                "/api/check-solution",
                headers=self.headers,
                json={
                    "problem_id": PID,
                    "language": "cpp",
                    "code": "AI_OK",
                    "proposal_id": proposal["id"],
                    "proposal_revision": proposal["revision"],
                    "operation_id": "wrong-language-retest",
                },
            )
            self.assertEqual(response.status_code, 400)
            runner.assert_not_called()

    def test_changed_problem_snapshot_cannot_be_handed_back(self):
        row = self.create("review", code="OK")
        with app.app_context():
            db.session.get(Problem, PID).description += "changed meaning"
            db.session.commit()
        self.assertEqual(self.handoff(row).status_code, 409)
        with app.app_context():
            self.assertEqual(CodeProposal.query.count(), 0)

    def test_handoff_detects_revision_changed_after_initial_check(self):
        row = self.create("review", code="OK")
        original_check = service.check_revision
        changed = False

        def update_after_check(stored, revision):
            nonlocal changed
            original_check(stored, revision)
            if not changed:
                changed = True
                with app.app_context():
                    other = db.session.get(CoCreateSession, row["id"])
                    other.revision += 1
                    db.session.commit()

        with patch("modules.co_create.service.check_revision", side_effect=update_after_check):
            response = self.handoff(row)
        self.assertEqual(response.status_code, 409)
        with app.app_context():
            self.assertEqual(CodeProposal.query.count(), 0)

    def test_legacy_and_examples_review_shortcut_rejected(self):
        legacy = seed_legacy_record("review")
        self.assertEqual(self.handoff(legacy, "review").status_code, 400)
        row = self.create("examples", code="OK")
        self.assertEqual(self.handoff(row, "review").status_code, 400)
        with app.app_context():
            self.assertEqual(CodeProposal.query.count(), 0)

    def test_review_revision_has_stable_distinct_proposal_and_original_baseline(self):
        row = self.create("review", code="BASE")
        first = self.data(self.handoff(row))["proposal"]
        row = self.data(self.post(row, "review", code="AI_OK"))["session"]
        second = self.data(self.handoff(row))["proposal"]
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(second["base_code"], "BASE")
        self.assertEqual(second["candidate_code"], "AI_OK")
        self.assertEqual(self.data(self.handoff(row))["proposal"]["id"], second["id"])

    def test_database_failure_during_idempotent_return_is_recoverable(self):
        from sqlalchemy.exc import OperationalError

        row = self.create("review", code="OK")
        proposal = self.data(self.handoff(row))["proposal"]
        with (
            patch.object(
                db.session,
                "commit",
                side_effect=OperationalError("commit", {}, Exception("offline")),
            ),
            self.assertLogs(app.logger, level="ERROR"),
        ):
            response = self.handoff(row)
        self.assertEqual(response.status_code, 503)
        restored = self.data(self.handoff(row))["proposal"]
        self.assertEqual(restored["id"], proposal["id"])
        with app.app_context():
            self.assertEqual(CodeProposal.query.count(), 1)
            self.assertEqual(PracticeEvent.query.count(), 1)

    def test_database_failure_during_revision_lock_saves_no_partial_proposal(self):
        from sqlalchemy.exc import OperationalError

        row = self.create("review", code="OK")
        with (
            patch(
                "flask_sqlalchemy.query.Query.update",
                side_effect=OperationalError("update", {}, Exception("busy")),
            ),
            self.assertLogs(app.logger, level="ERROR"),
        ):
            response = self.handoff(row)
        self.assertEqual(response.status_code, 503)
        with app.app_context():
            self.assertEqual(CodeProposal.query.count(), 0)
            self.assertEqual(PracticeEvent.query.count(), 0)
            self.assertEqual(Submission.query.count(), 0)


if __name__ == "__main__":
    unittest.main()

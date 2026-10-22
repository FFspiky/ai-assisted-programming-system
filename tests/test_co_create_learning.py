"""Owned evidence links and student reflection; isolated DB and no paid AI."""

import copy
import hashlib
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy.exc import IntegrityError, OperationalError

from models import (
    CodeProposal,
    LearningHelp,
    PracticeEvent,
    Problem,
    Submission,
    TestCase,
    User,
    db,
)
from modules.co_create.models import CoCreateSession
from services.problem_library import load_library
from tests import test_problem_co_create as fixtures
from tests.test_co_create import seed_legacy_record

BASE, PID, app = fixtures.BASE, fixtures.PID, fixtures.app
TARGET = "CL-BASICS-02"


class CoCreateLearningTest(unittest.TestCase):
    login = fixtures.ProblemCoCreateTest.login
    data = fixtures.ProblemCoCreateTest.data
    create = fixtures.ProblemCoCreateTest.create
    post = fixtures.ProblemCoCreateTest.post
    generate = fixtures.ProblemCoCreateTest.generate

    def setUp(self):
        fixtures.ProblemCoCreateTest.setUp(self)
        with app.app_context():
            record = next(p for p in load_library() if p["id"] == TARGET)
            db.session.add(
                Problem(
                    **{
                        k: record[k]
                        for k in (
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
                        problem_id=TARGET,
                        input_data=case["input"],
                        expected_output=case["output"],
                        is_public=case["public"],
                    )
                )
            db.session.commit()

    def get_learning(self, row, client=None):
        return (client or self.client).get(f'{BASE}/sessions/{row["id"]}/learning')

    def reflect(self, row, **data):
        return self.post(row, "learning/reflection", **data)

    def start(self, row, **data):
        return self.data(self.post(row, "learning/transfer", problem_id=TARGET, **data))

    def submission(
        self, *, username="student", problem=TARGET, language="python", seconds=1, **data
    ):
        with app.app_context():
            user = User.query.filter_by(username=username).first()
            row = Submission(
                user_id=user.id,
                problem_id=problem,
                language=language,
                timestamp=datetime.now(timezone.utc) + timedelta(seconds=seconds),
                code_submitted="ACTUAL_SUBMISSION",
                status="Accepted",
                **data,
            )
            db.session.add(row)
            db.session.commit()
            return row.id

    def attach(self, row, attempt, submission_id, **data):
        return self.post(
            row,
            f'learning/transfer/{attempt["id"]}/submission',
            submission_id=submission_id,
            **data,
        )

    def test_existing_record_is_lazily_read_without_revision_or_state_mutation(self):
        row = self.create("review", code="OK")
        result = self.data(self.get_learning(row))
        self.assertEqual(result["revision"], row["revision"])
        self.assertIsNone(result["learning"]["reflection"])
        self.assertEqual(result["learning"]["stage"], "verify")
        self.assertEqual([r["problem_id"] for r in result["related"]], [TARGET])
        self.assertEqual(result["attempts"], [])
        with app.app_context():
            self.assertNotIn("learning", db.session.get(CoCreateSession, row["id"]).state)

    def test_owner_and_csrf_scopes_all_endpoints(self):
        row = self.create("review", code="OK")
        opened = self.start(row)
        for suffix in ("learning", f'learning/transfer/{opened["attempt"]["id"]}'):
            self.assertEqual(
                self.other.get(f'{BASE}/sessions/{row["id"]}/{suffix}').status_code, 404
            )
        for suffix, body in (
            ("learning/reflection", {}),
            ("learning/transfer", {"problem_id": TARGET}),
            (f'learning/transfer/{opened["attempt"]["id"]}/submission', {"submission_id": 1}),
        ):
            self.assertEqual(
                self.other.post(
                    f'{BASE}/sessions/{row["id"]}/{suffix}',
                    json={"revision": 0, **body},
                    headers=self.other_headers,
                ).status_code,
                404,
            )
        self.assertIn(
            self.client.post(
                f'{BASE}/sessions/{row["id"]}/learning/reflection', json={"revision": 0}
            ).status_code,
            (400, 403),
        )

    def test_empty_explanations_remain_empty_not_ai_written(self):
        row = self.create("review", code="OK")
        result = self.data(
            self.reflect(row, candidate_id="review", reason="", boundary="", next_check="")
        )
        reflection = result["learning"]["reflection"]
        self.assertEqual(
            [reflection[k] for k in ("reason", "boundary", "next_check")], ["", "", ""]
        )
        self.assertEqual(reflection["code_hash"], hashlib.sha256(b"OK").hexdigest())
        self.assertFalse(reflection["stale"])
        self.provider.assert_not_called()

    def test_explanation_bound_to_matching_run_and_code_revision(self):
        row = self.create("review", code="OK")
        result = self.data(self.post(row, "review-run", input="3661\n"))
        row, run = result["session"], result["run"]
        result = self.data(
            self.reflect(
                row,
                reason="整除小时",
                boundary="零及整小时",
                next_check="最大输入",
                judgment="unsure",
            )
        )
        self.assertEqual(result["learning"]["reflection"]["run_ids"], [run["id"]])
        row = self.data(self.post(result["session"], "review", code="BAD"))["session"]
        old = self.data(self.get_learning(row))["learning"]["reflection"]
        self.assertTrue(old["stale"])
        self.assertEqual(old["reason"], "整除小时")
        second = self.data(self.reflect(row, reason="新的修订解释"))
        self.assertEqual(second["recap"]["reflection_history"][0]["reason"], "整除小时")
        self.assertEqual(second["recap"]["reflection_history"][0]["run_ids"], [run["id"]])

    def test_reflection_stale_revision_limits_and_enum_validation(self):
        row = self.create("review", code="OK")
        for data in (
            {"reason": "x" * 2001},
            {"boundary": None},
            {"next_check": []},
            {"judgment": "mastered"},
            {"candidate_id": "not-review"},
        ):
            self.assertIn(self.reflect(row, **data).status_code, (400, 409))
        self.data(self.reflect(row, reason="saved"))
        self.assertEqual(self.reflect(row, reason="late").status_code, 409)

    def test_candidates_explanation_becomes_stale_after_generation(self):
        row = self.generate(self.create(), ("AI_OK", "BAD"))
        candidate = row["state"]["generations"][-1]["candidates"][0]
        result = self.data(self.reflect(row, candidate_id=candidate["id"], reason="看过公开例子"))
        self.assertEqual(result["recap"]["chosen"]["source"], "ai")
        row = self.generate(result["session"], ("AI_OK", "BAD"))
        self.assertTrue(self.data(self.get_learning(row))["learning"]["reflection"]["stale"])
        self.assertEqual(self.reflect(row, candidate_id=candidate["id"]).status_code, 409)

    def test_second_current_candidate_explanation_is_bound_without_selecting(self):
        row = self.generate(self.create(), ("AI_OK", "BAD"))
        candidate = row["state"]["generations"][-1]["candidates"][1]
        result = self.data(self.reflect(row, candidate_id=candidate["id"], reason="检查候选B"))
        self.assertFalse(result["learning"]["reflection"]["stale"])
        self.assertFalse(result["learning"]["reflection"]["is_current_target"])
        self.assertIsNone(result["session"]["state"]["selected"])

    def test_source_edited_or_deleted_preserves_history_and_blocks_mutations(self):
        row = self.data(self.reflect(self.create("review", code="OK"), reason="我的解释"))[
            "session"
        ]
        with app.app_context():
            db.session.get(Problem, PID).description += "新版题目"
            db.session.commit()
        result = self.data(self.get_learning(row))
        self.assertTrue(result["learning"]["reflection"]["stale"])
        self.assertTrue(result["recap"]["session"]["problem_changed"])
        self.assertEqual(result["related"], [])
        self.assertEqual(self.reflect(row, reason="late").status_code, 409)
        with app.app_context():
            db.session.delete(db.session.get(Problem, PID))
            db.session.commit()
        self.assertEqual(self.get_learning(row).status_code, 200)
        self.assertEqual(self.post(row, "learning/transfer", problem_id=TARGET).status_code, 409)

    def test_transfer_context_does_not_copy_solution_or_create_fake_submission(self):
        row = self.create("review", language="cpp", code="ORIGINAL_CODE")
        result = self.start(row)
        attempt = result["attempt"]
        self.assertEqual(attempt["language"], "cpp")
        self.assertEqual(attempt["status"], "in_progress")
        self.assertEqual(attempt["existing_submission_count"], 0)
        self.assertIn("language=cpp", result["practice_url"])
        self.assertIn("transfer_attempt=" + attempt["id"], result["practice_url"])
        context = self.data(
            self.client.get(f'{BASE}/sessions/{row["id"]}/learning/transfer/{attempt["id"]}')
        )
        self.assertEqual(context["source"]["problem_id"], PID)
        self.assertIn("stage=recap", context["recap_url"])
        self.assertNotIn("code", attempt)
        with app.app_context():
            self.assertEqual(Submission.query.count(), 0)
            self.assertEqual(User.query.filter_by(username="student").first().points, 0)

    def test_target_edited_deleted_or_unrelated_cannot_be_started_or_attached(self):
        row = self.create("review", code="OK")
        self.assertEqual(self.post(row, "learning/transfer", problem_id=PID).status_code, 409)
        opened = self.start(row)
        with app.app_context():
            db.session.get(Problem, TARGET).title += "（修订）"
            db.session.commit()
        result = self.data(self.get_learning(opened["session"]))
        self.assertEqual(result["related"], [])
        self.assertEqual(result["attempts"][0]["status"], "target_changed")
        self.assertEqual(
            self.attach(opened["session"], opened["attempt"], self.submission()).status_code, 409
        )
        self.assertEqual(
            self.post(opened["session"], "learning/transfer", problem_id=TARGET).status_code, 409
        )
        with app.app_context():
            db.session.delete(db.session.get(Problem, TARGET))
            db.session.commit()
        self.assertEqual(
            self.data(self.get_learning(opened["session"]))["attempts"][0]["status"],
            "target_changed",
        )

    def test_submissions_owner_time_problem_language_and_attempt_scope(self):
        before = self.submission(seconds=-60)
        opened = self.start(self.create("review", code="OK"))
        row, attempt = opened["session"], opened["attempt"]
        for submission_id, status in (
            (before, 409),
            (self.submission(username="other"), 404),
            (self.submission(problem=PID), 404),
            (self.submission(language="cpp"), 404),
            (True, 400),
        ):
            self.assertEqual(self.attach(row, attempt, submission_id).status_code, status)
        self.assertEqual(
            self.post(row, "learning/transfer/unknown/submission", submission_id=1).status_code, 404
        )
        self.assertEqual(
            self.attach(
                row, attempt, self.submission(), help_usage="proved-independent"
            ).status_code,
            400,
        )

    def test_attach_idempotent_with_self_report_revision_changes_and_unique_event(self):
        opened = self.start(self.create("review", code="OK"))
        row, attempt, submission_id = opened["session"], opened["attempt"], self.submission()
        result = self.data(self.attach(row, attempt, submission_id, help_usage="none"))
        first_revision = result["revision"]
        saved = result["attempt"]["submissions"][0]
        self.assertEqual(saved["help_usage_source"], "student_self_report")
        self.assertEqual(saved["submission"]["id"], submission_id)
        self.assertEqual(result["attempt"]["status"], "submitted")
        replay = self.data(self.attach(row, attempt, submission_id, help_usage="none"))
        self.assertEqual(replay["revision"], first_revision)
        self.assertEqual(
            self.attach(row, attempt, submission_id, help_usage="hint").status_code, 409
        )
        revised = self.data(
            self.attach(result["session"], attempt, submission_id, help_usage="hint")
        )
        self.assertEqual(revised["attempt"]["submissions"][0]["help_usage"], "hint")
        with app.app_context():
            self.assertEqual(PracticeEvent.query.filter_by(kind="transfer_submission").count(), 1)
            self.assertEqual(Submission.query.count(), 1)

    def test_submission_cannot_be_claimed_by_two_attempts_or_sessions(self):
        opened = self.start(self.create("review", code="OK"))
        another = self.start(opened["session"])
        submission_id = self.submission()
        first = self.data(self.attach(another["session"], opened["attempt"], submission_id))
        response = self.attach(first["session"], another["attempt"], submission_id)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json["error"]["code"], "SUBMISSION_ALREADY_LINKED")

    def test_recorded_help_is_visible_without_claiming_independence(self):
        opened = self.start(self.create("review", code="OK"))
        submission_id = self.submission()
        with app.app_context():
            user = User.query.filter_by(username="student").first()
            db.session.add(
                LearningHelp(
                    user_id=user.id,
                    submission_id=submission_id,
                    source="panel",
                    mode="learning",
                    mode_revision=0,
                    requested_level=4,
                    returned_level=4,
                    state="ready",
                    request_snapshot={},
                    model="test",
                    prompt_version="test",
                    shown_at=datetime.now(timezone.utc),
                )
            )
            db.session.commit()
        result = self.data(
            self.attach(opened["session"], opened["attempt"], submission_id, help_usage="none")
        )
        saved = result["attempt"]["submissions"][0]
        self.assertEqual(saved["recorded_help"][0]["level"], 4)
        self.assertIn("不能证明", saved["help_note"])
        self.assertNotIn("mastery", json.dumps(result))

    def test_help_requested_after_attach_appears_on_next_read(self):
        opened = self.start(self.create("review", code="OK"))
        submission_id = self.submission()
        result = self.data(
            self.attach(opened["session"], opened["attempt"], submission_id, help_usage="none")
        )
        self.assertEqual(result["attempt"]["submissions"][0]["recorded_help"], [])
        with app.app_context():
            user = User.query.filter_by(username="student").first()
            db.session.add(
                LearningHelp(
                    user_id=user.id,
                    submission_id=submission_id,
                    source="panel",
                    mode="learning",
                    mode_revision=0,
                    requested_level=2,
                    returned_level=2,
                    state="ready",
                    request_snapshot={},
                    model="test",
                    prompt_version="test",
                )
            )
            db.session.commit()
        value = self.data(self.get_learning(result["session"]))["attempts"][0]["submissions"][0]
        self.assertEqual(value["help_usage"], "none")
        self.assertEqual(value["recorded_help"][0]["level"], 2)
        self.assertEqual(value["recorded_help_source"], "live_site_records")

    def test_atomic_failure_rolls_back_event_and_json(self):
        opened = self.start(self.create("review", code="OK"))
        submission_id = self.submission()
        with patch.object(
            db.session,
            "commit",
            side_effect=IntegrityError("test", {}, Exception("simulated duplicate")),
        ):
            response = self.attach(opened["session"], opened["attempt"], submission_id)
        self.assertEqual(response.status_code, 409)
        with app.app_context():
            row = db.session.get(CoCreateSession, opened["session"]["id"])
            self.assertEqual(row.revision, opened["revision"])
            self.assertEqual(row.state["learning"]["attempts"][0]["submissions"], [])
            self.assertEqual(PracticeEvent.query.filter_by(kind="transfer_submission").count(), 0)

    def test_storage_failure_is_reported_without_persisting_new_reflection(self):
        row = self.create("review", code="OK")
        with patch.object(
            db.session,
            "commit",
            side_effect=OperationalError("test", {}, Exception("storage unavailable")),
        ):
            response = self.reflect(row, reason="not saved")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["error"]["code"], "LEARNING_SAVE_FAILED")
        with app.app_context():
            saved = db.session.get(CoCreateSession, row["id"])
            self.assertEqual(saved.revision, row["revision"])
            self.assertNotIn("learning", saved.state)

    def test_recap_allowlist_excludes_hidden_values_and_event_payloads(self):
        row = self.create("review", code="OK")
        with app.app_context():
            saved = db.session.get(CoCreateSession, row["id"])
            state = copy.deepcopy(saved.state)
            state["runs"] = [
                {
                    "id": "run",
                    "kind": "verify",
                    "cases": [
                        {
                            "id": "hidden",
                            "is_public": False,
                            "status": "Wrong Answer",
                            "passed": False,
                            "input": "HIDDEN_INPUT_SECRET",
                            "expected": "HIDDEN_EXPECTED_SECRET",
                            "actual": "HIDDEN_ACTUAL_SECRET",
                            "error": "HIDDEN_ERROR_SECRET",
                        }
                    ],
                }
            ]
            saved.state = state
            user = User.query.filter_by(username="student").first()
            proposal = CodeProposal(
                user_id=user.id,
                source="co_create",
                co_create_session_id=row["id"],
                co_create_candidate_id="review:hash",
                problem_id=PID,
                language="python",
                base_code="BASE",
                candidate_code="OK",
                edits=[],
                state="accepted",
            )
            db.session.add(proposal)
            db.session.flush()
            submission = Submission(
                user_id=user.id,
                problem_id=PID,
                language="python",
                code_submitted="OK",
                status="Accepted",
                evidence_snapshot={
                    "total": 1,
                    "cases": [
                        {
                            "id": "hidden",
                            "is_public": False,
                            "status": "Accepted",
                            "passed": True,
                            "input": "HIDDEN_FORMAL_INPUT_SECRET",
                            "error": "HIDDEN_FORMAL_ERROR_SECRET",
                        }
                    ],
                },
            )
            db.session.add(submission)
            db.session.flush()
            db.session.add(
                PracticeEvent(
                    user_id=user.id,
                    problem_id=PID,
                    language="python",
                    proposal_id=proposal.id,
                    submission_id=submission.id,
                    kind="retest",
                    payload={"private": "HIDDEN_EVENT_SECRET"},
                )
            )
            db.session.commit()
        result = self.data(self.get_learning(row))
        self.assertNotIn("SECRET", json.dumps(result))
        case = result["recap"]["runs"][0]["cases"][0]
        self.assertEqual(set(case), {"id", "is_public", "status", "passed"})
        self.assertEqual(
            result["recap"]["proposals"][0]["formal_submissions"][0]["status"], "Accepted"
        )

    def test_legacy_record_readable_without_new_mutation(self):
        row = seed_legacy_record()
        result = self.data(self.get_learning(row))
        self.assertTrue(result["recap"]["session"]["legacy"])
        self.assertEqual(result["related"], [])
        self.assertIsNone(result["recap"]["chosen"])
        self.assertEqual(self.reflect(row).status_code, 400)


if __name__ == "__main__":
    unittest.main()

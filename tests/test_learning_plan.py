"""Persisted learning plans are private suggestions backed by real task evidence.

Questionnaire answers are self-reports, not proof of mastery. These tests use
the public API and real task-room transitions; only container transport is
stubbed, and every paid AI boundary is forbidden.
"""

import copy
import json
import os
import unittest
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["FLASK_SECRET_KEY"] = "learning-plan-test-secret"
os.environ["AUTO_CREATE_DATABASE"] = "0"

import models  # noqa: E402
from app import app  # noqa: E402
from models import User, db  # noqa: E402
from modules.task_room.catalog import reference_code  # noqa: E402
from modules.task_room.models import TaskProject, TaskRun  # noqa: E402
from services.rate_limiter import _MEMORY_BUCKETS  # noqa: E402

BASE = "/api/learning-plan"
ROOM = "/api/task-room"
QUESTION_IDS = {
    "experience",
    "coding",
    "preferred_language",
    "loops",
    "collections",
    "testing",
    "time",
    "interests",
    "goal",
}
EXISTING_SCENARIOS = {"signup_roster", "event_waitlist", "stock_orders"}


class LearningPlanTest(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        _MEMORY_BUCKETS.clear()
        self.client = app.test_client()
        self.other = app.test_client()
        self.anonymous = app.test_client()
        with app.app_context():
            db.drop_all()
            db.create_all()
            for username in ("plan-owner", "plan-other"):
                user = User(username=username, email=username + "@example.test")
                user.set_password("test-password")
                db.session.add(user)
            db.session.commit()
            self.owner_id = User.query.filter_by(username="plan-owner").one().id
            self.other_id = User.query.filter_by(username="plan-other").one().id
        self.headers = self.login(self.client, "plan-owner")
        self.other_headers = self.login(self.other, "plan-other")
        self.ai_boundaries = []
        for target in (
            "services.ai_client.chat_completion",
            "services.ai_client.stream_chat_deltas",
            "services.ai_client.requests.post",
            "modules.task_room.ai.chat_completion",
            "routes.analytics.stream_learning_analysis",
        ):
            guard = patch(
                target, side_effect=AssertionError("Learning plans must not call paid AI")
            )
            self.ai_boundaries.append(guard.start())
            self.addCleanup(guard.stop)
        runner = patch(
            "modules.task_room.service.run_code",
            side_effect=AssertionError("Unit tests must explicitly stub container execution"),
        )
        self.runner = runner.start()
        self.addCleanup(runner.stop)
        self.questions = self.data(self.anonymous.get(BASE + "/questions"))["questions"]
        self.answers = {
            question["id"]: (
                [question["options"][0]["value"]]
                if question["type"] == "multi"
                else question["options"][0]["value"]
            )
            for question in self.questions
        }

    def tearDown(self):
        for ai in self.ai_boundaries:
            ai.assert_not_called()

    def login(self, client, username):
        response = client.post(
            "/api/login", json={"username": username, "password": "test-password"}
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        return {"X-CSRF-Token": response.get_json()["csrf_token"]}

    def data(self, response, status=200):
        self.assertEqual(response.status_code, status, response.get_json())
        envelope = response.get_json()
        self.assertIs(envelope["success"], True)
        self.assertIn("data", envelope)
        self.assertIsNone(envelope.get("error"))
        return envelope["data"]

    def error(self, response, status):
        self.assertEqual(response.status_code, status, response.get_json())
        envelope = response.get_json()
        self.assertIs(envelope["success"], False)
        self.assertIn("data", envelope)
        self.assertIsInstance(envelope["error"], dict)
        self.assertTrue(envelope["error"]["code"])
        self.assertTrue(envelope["error"]["message"])

    def submit(self, answers=None, revision=0, client=None, headers=None):
        return (client or self.client).post(
            BASE,
            json={"answers": self.answers if answers is None else answers, "revision": revision},
            headers=self.headers if headers is None else headers,
        )

    def load(self, client=None):
        return self.data((client or self.client).get(BASE))

    def catalog(self):
        return self.data(self.anonymous.get(ROOM + "/catalog"))["scenarios"]

    def question(self, question_id):
        return next(question for question in self.questions if question["id"] == question_id)

    def recommendation(self, state, scenario_id):
        return next(
            item for item in state["plan"]["recommendations"] if item["scenario_id"] == scenario_id
        )

    def project_url(self, project, suffix=""):
        return ROOM + "/projects/" + project["id"] + suffix

    def create(self, scenario_id, client=None, headers=None):
        return self.data(
            (client or self.client).post(
                ROOM + "/projects",
                json={"scenario_id": scenario_id},
                headers=self.headers if headers is None else headers,
            ),
            201,
        )["project"]

    def freeze(self, project):
        rules = {group["key"]: group["recommended"] for group in project["scenario"]["rule_groups"]}
        return self.data(
            self.client.post(
                self.project_url(project, "/freeze"),
                json={"rules": rules, "revision": project["revision"]},
                headers=self.headers,
            )
        )["project"]

    def save(self, project, code):
        return self.data(
            self.client.patch(
                self.project_url(project),
                json={"code": code, "draft_revision": project["draft_revision"]},
                headers=self.headers,
            )
        )["project"]

    def run_task(self, project, kind="acceptance", wrong=False):
        cases = project["contract"]["cases"]
        selected = cases if kind == "acceptance" else cases[:1]
        self.runner.side_effect = None
        self.runner.return_value = {
            "success": True,
            "status": "Accepted",
            "output": json.dumps(
                {
                    "results": [
                        {
                            "index": index,
                            "actual": {"incorrect": True} if wrong else case["expected"],
                            "error": None,
                        }
                        for index, case in enumerate(selected)
                    ]
                },
                ensure_ascii=False,
            ),
            "error": "",
            "time": 0.1,
            "execution_backend": "docker",
            "output_truncated": False,
        }
        body = {"kind": kind, "code": project["code"], "contract_id": project["contract"]["id"]}
        if kind == "custom":
            body["input"] = selected[0]["input"]
        return self.data(
            self.client.post(self.project_url(project, "/run"), json=body, headers=self.headers)
        )["run"]

    def deliver(self, project):
        return self.data(
            self.client.post(
                self.project_url(project, "/deliver"),
                json={
                    "code": project["code"],
                    "contract_id": project["contract"]["id"],
                    "revision": project["revision"],
                },
                headers=self.headers,
            )
        )["project"]

    def delivered_project(self, scenario_id):
        project = self.freeze(self.create(scenario_id))
        project = self.save(project, reference_code(scenario_id, project["contract"]["rules"]))
        self.assertEqual(self.run_task(project)["status"], "passed")
        return self.deliver(project)

    def test_questions_are_public_complete_and_do_not_create_an_assessment(self):
        questionnaire = self.data(self.anonymous.get(BASE + "/questions"))
        self.assertEqual(questionnaire["version"], 2)
        self.assertEqual({question["id"] for question in questionnaire["questions"]}, QUESTION_IDS)
        self.assertEqual(len(questionnaire["questions"]), 9)
        for question in questionnaire["questions"]:
            self.assertTrue(question["title"])
            self.assertGreaterEqual(len(question["options"]), 2)
            values = [option["value"] for option in question["options"]]
            self.assertEqual(len(values), len(set(values)))
            self.assertTrue(all(isinstance(value, str) and value for value in values))
            self.assertTrue(all(option["label"] for option in question["options"]))
            self.assertEqual(
                question["type"], "multi" if question["id"] == "interests" else "single"
            )
        self.assertEqual(self.question("interests")["max_select"], 2)
        initial = self.load()
        self.assertIsNone(initial["assessment"])
        self.assertIsNone(initial["plan"])
        with app.app_context():
            self.assertEqual(models.LearningAssessment.query.count(), 0)
        self.runner.assert_not_called()

    def test_private_assessment_requires_login_and_csrf(self):
        self.error(self.anonymous.get(BASE), 401)
        self.error(self.anonymous.post(BASE, json={"answers": self.answers, "revision": 0}), 401)
        self.error(self.submit(headers={}), 403)
        self.error(self.submit(headers={"X-CSRF-Token": "wrong"}), 403)
        self.error(self.submit(headers=self.other_headers), 403)
        self.assertIsNone(self.load()["assessment"])

    def test_incomplete_unknown_or_wrongly_typed_answers_are_rejected_atomically(self):
        interest_options = [item["value"] for item in self.question("interests")["options"]]
        invalid = [None, [], "answers", {}, {**self.answers, "unexpected": "value"}]
        invalid.append({key: value for key, value in self.answers.items() if key != "goal"})
        for question_id in QUESTION_IDS - {"interests"}:
            for value in (True, 1, 1.0, None, [], {}, "not-a-valid-option"):
                invalid.append({**self.answers, question_id: value})
        for value in (
            "automation",
            None,
            {},
            [],
            [True],
            [1],
            ["not-a-valid-option"],
            [interest_options[0], interest_options[0]],
            interest_options[:3],
        ):
            invalid.append({**self.answers, "interests": value})
        self.assertGreaterEqual(len(interest_options), 3)
        for answers in invalid:
            with self.subTest(answers=answers):
                _MEMORY_BUCKETS.clear()
                response = self.client.post(
                    BASE, json={"answers": answers, "revision": 0}, headers=self.headers
                )
                self.error(response, 400)
        self.assertIsNone(self.load()["assessment"])
        with app.app_context():
            self.assertEqual(models.LearningAssessment.query.count(), 0)

    def test_revision_requires_an_integer_and_stale_initial_writes_do_not_create_data(self):
        for revision in (None, True, False, "0", 0.0, -1, [], {}):
            with self.subTest(revision=revision):
                self.error(self.submit(revision=revision), 400)
        self.error(
            self.client.post(BASE, json={"answers": self.answers}, headers=self.headers), 400
        )
        self.error(self.submit(revision=1), 409)
        self.assertIsNone(self.load()["assessment"])

    def test_saved_answers_restore_and_reassessment_is_revision_guarded(self):
        first = self.data(self.submit())
        self.assertEqual(first["assessment"]["answers"], self.answers)
        revision = first["assessment"]["revision"]
        self.assertEqual(revision, 1)
        self.assertTrue(first["assessment"]["updated_at"])
        self.assertEqual(self.load(), first)
        advanced = {
            question["id"]: (
                [question["options"][-1]["value"]]
                if question["type"] == "multi"
                else question["options"][-1]["value"]
            )
            for question in self.questions
        }
        updated = self.data(self.submit(advanced, revision))
        self.assertEqual(updated["assessment"]["answers"], advanced)
        self.assertEqual(updated["assessment"]["revision"], revision + 1)
        self.error(self.submit(self.answers, revision), 409)
        self.error(self.submit(self.answers, 0), 409)
        self.assertEqual(self.load(), updated)
        fresh_client = app.test_client()
        self.login(fresh_client, "plan-owner")
        self.assertEqual(self.load(fresh_client), updated)
        with app.app_context():
            self.assertEqual(
                models.LearningAssessment.query.filter_by(user_id=self.owner_id).count(), 1
            )
        self.runner.assert_not_called()

    def test_answers_and_project_evidence_are_scoped_to_the_signed_in_user(self):
        owner = self.data(self.submit())
        owner_scenario = owner["plan"]["recommendations"][0]["scenario_id"]
        project = self.delivered_project(owner_scenario)
        self.assertIsNone(self.load(self.other)["assessment"])
        other_answers = copy.deepcopy(self.answers)
        other_answers["goal"] = self.question("goal")["options"][-1]["value"]
        other_state = self.data(
            self.submit(other_answers, client=self.other, headers=self.other_headers)
        )
        self.assertEqual(other_state["assessment"]["answers"], other_answers)
        self.assertEqual(
            other_state["plan"]["stats"], {"projects": 0, "delivered": 0, "acceptance_runs": 0}
        )
        self.assertTrue(
            all(item["project_id"] is None for item in other_state["plan"]["recommendations"])
        )
        owner_state = self.load()
        self.assertEqual(owner_state["assessment"]["answers"], self.answers)
        self.assertEqual(owner_state["plan"]["stats"]["delivered"], 1)
        self.assertNotIn(project["id"], json.dumps(other_state))
        # Adding an identity to the URL never grants access to another profile.
        queried = self.data(self.other.get(BASE + "?user_id=" + str(self.owner_id)))
        self.assertEqual(queried, other_state)

    def test_plan_recommends_existing_tasks_and_self_reports_never_imply_completion(self):
        state = self.data(self.submit())
        catalog = {item["id"]: item for item in self.catalog()}
        plan = state["plan"]
        self.assertTrue(plan["summary"])
        self.assertTrue(plan["source"])
        self.assertEqual(set(plan["level"]), {"value", "label", "description"})
        recommendations = plan["recommendations"]
        self.assertGreaterEqual(len(recommendations), 3)
        self.assertEqual(
            len({item["scenario_id"] for item in recommendations}), len(recommendations)
        )
        self.assertEqual(
            [item["order"] for item in recommendations], list(range(1, len(recommendations) + 1))
        )
        for recommendation in recommendations:
            self.assertIn(recommendation["scenario_id"], catalog)
            self.assertEqual(
                recommendation["title"], catalog[recommendation["scenario_id"]]["title"]
            )
            for key in ("subtitle", "level", "duration", "learning_goal", "reason"):
                self.assertTrue(recommendation[key], key)
            self.assertIs(type(recommendation["estimated_minutes"]), int)
            self.assertGreater(recommendation["estimated_minutes"], 0)
            self.assertTrue(recommendation["skills"])
            self.assertEqual(recommendation["status"], "not_started")
            self.assertIsNone(recommendation["project_id"])
        self.assertEqual(plan["stats"], {"projects": 0, "delivered": 0, "acceptance_runs": 0})
        advanced = copy.deepcopy(self.answers)
        for question_id in ("experience", "coding", "loops", "collections", "testing"):
            advanced[question_id] = self.question(question_id)["options"][-1]["value"]
        reassessed = self.data(self.submit(advanced, state["assessment"]["revision"]))
        self.assertTrue(
            all(item["status"] == "not_started" for item in reassessed["plan"]["recommendations"])
        )
        self.assertEqual(reassessed["plan"]["stats"]["delivered"], 0)
        self.runner.assert_not_called()

    def test_novice_and_short_sessions_begin_with_small_starter_tasks(self):
        short = self.data(self.submit())
        self.assertEqual(short["plan"]["level"]["value"], "starter")
        quick = short["plan"]["recommendations"][0]
        self.assertNotIn(quick["scenario_id"], EXISTING_SCENARIOS)
        self.assertLessEqual(quick["estimated_minutes"], 30)
        longer = copy.deepcopy(self.answers)
        longer["time"] = self.question("time")["options"][-1]["value"]
        long = self.data(self.submit(longer, short["assessment"]["revision"]))
        self.assertLessEqual(
            quick["estimated_minutes"], long["plan"]["recommendations"][0]["estimated_minutes"]
        )

    def test_creating_a_recommended_task_updates_progress_without_changing_the_assessment(self):
        saved = self.data(self.submit())
        scenario_id = saved["plan"]["recommendations"][0]["scenario_id"]
        project = self.create(scenario_id)
        current = self.load()
        self.assertEqual(current["assessment"], saved["assessment"])
        recommendation = self.recommendation(current, scenario_id)
        self.assertEqual(recommendation["project_id"], project["id"])
        self.assertEqual(recommendation["status"], "in_progress")
        self.assertEqual(
            current["plan"]["stats"], {"projects": 1, "delivered": 0, "acceptance_runs": 0}
        )
        self.runner.assert_not_called()

    def test_only_explicit_delivery_of_matching_passed_acceptance_completes_a_task(self):
        saved = self.data(self.submit())
        scenario_id = saved["plan"]["recommendations"][0]["scenario_id"]
        project = self.freeze(self.create(scenario_id))
        project = self.save(project, reference_code(scenario_id, project["contract"]["rules"]))
        self.assertEqual(self.run_task(project, wrong=True)["status"], "failed")
        self.assertEqual(self.run_task(project, kind="custom")["status"], "passed")
        before_acceptance = self.load()
        self.assertEqual(
            before_acceptance["plan"]["stats"],
            {"projects": 1, "delivered": 0, "acceptance_runs": 1},
        )
        self.assertEqual(
            self.recommendation(before_acceptance, scenario_id)["status"], "in_progress"
        )
        self.assertEqual(self.run_task(project)["status"], "passed")
        self.assertEqual(self.recommendation(self.load(), scenario_id)["status"], "in_progress")
        project = self.deliver(project)
        completed = self.load()
        self.assertEqual(self.recommendation(completed, scenario_id)["status"], "delivered")
        self.assertEqual(
            completed["plan"]["stats"], {"projects": 1, "delivered": 1, "acceptance_runs": 2}
        )
        self.save(project, project["code"] + "\n# New draft needs fresh acceptance.\n")
        reopened = self.load()
        self.assertEqual(self.recommendation(reopened, scenario_id)["status"], "in_progress")
        self.assertEqual(reopened["plan"]["stats"]["delivered"], 0)

    def test_old_contract_acceptance_does_not_complete_changed_requirements(self):
        advanced = copy.deepcopy(self.answers)
        for question_id in ("experience", "coding", "loops", "collections", "testing"):
            advanced[question_id] = self.question(question_id)["options"][-1]["value"]
        self.data(self.submit(advanced))
        project = self.delivered_project("signup_roster")
        old_contract = project["contract"]["id"]
        change = next(
            item
            for item in project["scenario"]["changes"]
            if any(
                project["contract"]["rules"][key] != value for key, value in item["patch"].items()
            )
        )
        project = self.data(
            self.client.post(
                self.project_url(project, "/changes"),
                json={"change_id": change["id"], "revision": project["revision"]},
                headers=self.headers,
            )
        )["project"]
        self.assertNotEqual(project["contract"]["id"], old_contract)
        current = self.load()
        self.assertEqual(self.recommendation(current, "signup_roster")["status"], "in_progress")
        self.assertEqual(current["plan"]["stats"]["delivered"], 0)
        self.assertEqual(current["plan"]["stats"]["acceptance_runs"], 1)

    def test_archived_deliveries_keep_learning_progress(self):
        saved = self.data(self.submit())
        scenario_id = saved["plan"]["recommendations"][0]["scenario_id"]
        project = self.delivered_project(scenario_id)
        self.data(
            self.client.patch(
                self.project_url(project),
                json={"archived": True, "revision": project["revision"]},
                headers=self.headers,
            )
        )
        current = self.load()
        self.assertEqual(current["plan"]["stats"]["delivered"], 1)
        self.assertEqual(self.recommendation(current, scenario_id)["status"], "delivered")

    def test_legacy_or_inconsistent_delivery_badges_do_not_replace_real_evidence(self):
        state = self.data(self.submit())
        scenario_id = state["plan"]["recommendations"][0]["scenario_id"]
        project = self.delivered_project(scenario_id)
        with app.app_context():
            record = db.session.get(TaskProject, project["id"])
            delivery = copy.deepcopy(record.delivery)
            run_id = delivery["run_id"]
        for field, invalid_value in (
            ("code_hash", "not-current-code"),
            ("contract_id", "old-contract"),
            ("run_id", "missing-run"),
        ):
            with self.subTest(delivery_field=field), app.app_context():
                record = db.session.get(TaskProject, project["id"])
                record.delivery = {**delivery, field: invalid_value}
                db.session.commit()
                inconsistent = self.load()
                self.assertEqual(
                    self.recommendation(inconsistent, scenario_id)["status"], "in_progress"
                )
                self.assertEqual(inconsistent["plan"]["stats"]["delivered"], 0)
        with app.app_context():
            record = db.session.get(TaskProject, project["id"])
            record.delivery = delivery
            run = db.session.get(TaskRun, run_id)
            run.kind = "custom"
            db.session.commit()
        custom_only = self.load()
        self.assertEqual(self.recommendation(custom_only, scenario_id)["status"], "in_progress")
        self.assertEqual(custom_only["plan"]["stats"]["delivered"], 0)

    def test_version_one_python_answers_restore_without_rewriting_history(self):
        legacy = copy.deepcopy(self.answers)
        legacy["python"] = legacy.pop("coding")
        del legacy["preferred_language"]
        self.data(self.submit(legacy))
        with app.app_context():
            row = models.LearningAssessment.query.filter_by(user_id=self.owner_id).one()
            row.answers = legacy
            row.version = 1
            db.session.commit()
        restored = self.load()
        self.assertEqual(restored["assessment"]["version"], 1)
        self.assertEqual(restored["assessment"]["original_answers"], legacy)
        self.assertEqual(restored["assessment"]["answers"]["coding"], legacy["python"])
        self.assertEqual(restored["plan"]["preferred_language"], "python")
        with app.app_context():
            row = models.LearningAssessment.query.filter_by(user_id=self.owner_id).one()
            self.assertEqual(row.answers, legacy)
            self.assertEqual(row.version, 1)

    def test_preferred_language_never_reuses_other_language_delivery_evidence(self):
        initial = self.data(self.submit())
        scenario_id = initial["plan"]["recommendations"][0]["scenario_id"]
        project = self.delivered_project(scenario_id)
        self.assertEqual(self.recommendation(self.load(), scenario_id)["status"], "delivered")
        answers = {**self.answers, "preferred_language": "java"}
        switched = self.data(self.submit(answers, initial["assessment"]["revision"]))
        recommendation = self.recommendation(switched, scenario_id)
        self.assertEqual(recommendation["language"], "java")
        self.assertEqual(recommendation["status"], "not_started")
        self.assertIsNone(recommendation["project_id"])
        self.assertEqual(switched["plan"]["stats"]["delivered"], 1)
        java = self.data(
            self.client.post(
                ROOM + "/projects",
                json={"scenario_id": scenario_id, "language": "java"},
                headers=self.headers,
            ),
            201,
        )["project"]
        recommendation = self.recommendation(self.load(), scenario_id)
        self.assertEqual(recommendation["project_id"], java["id"])
        self.assertNotEqual(recommendation["project_id"], project["id"])


if __name__ == "__main__":
    unittest.main()

"""Problem-linked evidence tests; isolated SQLite, stubbed Docker and paid provider."""

import json
import os
import unittest
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["FLASK_SECRET_KEY"] = "problem-co-create-test-secret"
os.environ["AUTO_CREATE_DATABASE"] = "0"
os.environ["SILICONFLOW_API_KEY"] = ""
os.environ["SUPPORTED_LANGUAGES"] = "python,cpp,java"

from app import app
from models import Problem, Submission, TestCase, User, db
from modules.co_create import ai
from modules.co_create.models import CoCreateSession
from services.ai_client import AIClientError
from services.problem_library import load_library
from services.rate_limiter import _MEMORY_BUCKETS

BASE = "/api/co-create"
PID = "CL-BASICS-01"


def transport(code, language="python", input_text=None):
    """Declared test behavior, no eval/exec of either submitted or reference source."""
    if code == "ERROR":
        return {
            "success": False,
            "status": "Runtime Error",
            "error": "runtime failure",
            "execution_backend": "docker",
        }
    if code == "PRIVATE_ERROR":
        return {
            "success": False,
            "status": "Runtime Error",
            "output": input_text,
            "error": "PRIVATE_SOURCE_LINE " + input_text,
            "execution_backend": "docker",
        }
    if code in {"OK", "BASE", "AI_OK"} or code.startswith("t=int(input())"):
        value = int(input_text.strip())
        output = f"{value // 3600} {value // 60 % 60} {value % 60}\n"
    else:
        output = "wrong\n"
    return {
        "success": True,
        "status": "Accepted",
        "output": output,
        "error": "",
        "execution_backend": "docker",
        "time": 1,
    }


class ProblemCoCreateTest(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        for target in (
            "modules.co_create.problem_service.SUPPORTED_LANGUAGES",
            "modules.co_create.routes.SUPPORTED_LANGUAGES",
        ):
            language_patch = patch(target, {"python", "cpp", "java"})
            language_patch.start()
            self.addCleanup(language_patch.stop)
        _MEMORY_BUCKETS.clear()
        self.client, self.other = app.test_client(), app.test_client()
        with app.app_context():
            db.drop_all()
            db.create_all()
            for name in ("student", "other"):
                user = User(username=name, email=name + "@example.test")
                user.set_password("test-password")
                db.session.add(user)
            record = next(p for p in load_library() if p["id"] == PID)
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
                        problem_id=PID,
                        input_data=case["input"],
                        expected_output=case["output"],
                        is_public=case["public"],
                    )
                )
            db.session.commit()
        self.headers = self.login(self.client, "student")
        self.other_headers = self.login(self.other, "other")
        self.runner_patch = patch("modules.co_create.service.run_code", side_effect=transport)
        self.runner = self.runner_patch.start()
        self.addCleanup(self.runner_patch.stop)
        self.provider_patch = patch(
            "modules.co_create.ai.chat_completion",
            side_effect=AssertionError("No paid AI in unit tests"),
        )
        self.provider = self.provider_patch.start()
        self.addCleanup(self.provider_patch.stop)

    def login(self, client, username):
        response = client.post(
            "/api/login", json={"username": username, "password": "test-password"}
        )
        self.assertEqual(response.status_code, 200)
        return {"X-CSRF-Token": response.json["csrf_token"]}

    def data(self, response, status=200):
        self.assertEqual(response.status_code, status, response.get_json())
        return response.get_json()["data"]

    def create(self, mode="examples", **kwargs):
        return self.data(
            self.client.post(
                BASE + "/sessions",
                json={"mode": mode, "problem_id": PID, "language": "python", **kwargs},
                headers=self.headers,
            ),
            201,
        )["session"]

    def post(self, row, action, **kwargs):
        return self.client.post(
            BASE + "/sessions/" + row["id"] + "/" + action,
            json={"revision": row["revision"], **kwargs},
            headers=self.headers,
        )

    def generate(self, row, codes=("AI_OK", "BAD")):
        with patch(
            "modules.co_create.ai.generate_problem",
            return_value=(
                [{"code": code, "label": "候选", "explanation": "测试候选"} for code in codes],
                "test-model",
            ),
        ):
            return self.data(
                self.post(
                    row, "generate" if row["mode"] == "examples" else "review-generate", source="ai"
                )
            )["session"]

    def test_public_snapshot_languages_and_private_reference_not_exposed(self):
        catalog = self.data(self.client.get(BASE + "/catalog"))
        self.assertEqual({x["id"] for x in catalog["languages"]}, {"python", "cpp", "java"})
        for language in ("python", "cpp", "java"):
            row = self.create(language=language)
            self.assertFalse(row["legacy"])
            self.assertEqual(row["language"], language)
            self.assertEqual(len(row["problem"]["public_examples"]), 2)
            self.assertTrue(row["problem"]["reference_available"])
            self.assertNotIn("t=int(input())", json.dumps(row))
            self.assertEqual(row["state"]["practice_context"]["code"], "")

    def test_three_language_verification_uses_runner_without_formal_submission(self):
        for language in ("python", "cpp", "java"):
            row = self.create("review", language=language, code="OK")
            run = self.data(self.post(row, "verify"))["run"]
            self.assertTrue(run["passed"])
            self.assertEqual(run["passed_count"], 6)
            self.assertEqual(self.runner.call_args.args[1], language)
        with app.app_context():
            self.assertEqual(Submission.query.count(), 0)
            self.assertEqual(User.query.filter_by(username="student").first().points, 0)

    def test_malformed_custom_example_returns_validation_error(self):
        row = self.create()
        for value in ("bad", ["bad"], 1):
            response = self.client.patch(
                BASE + "/sessions/" + row["id"],
                json={"revision": row["revision"], "action": "upsert_example", "example": value},
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 400)

    def test_auth_csrf_ownership_and_context_submission(self):
        self.assertEqual(
            app.test_client()
            .post(BASE + "/sessions", json={"mode": "review", "problem_id": PID})
            .status_code,
            401,
        )
        self.assertEqual(
            self.client.post(
                BASE + "/sessions", json={"mode": "review", "problem_id": PID}
            ).status_code,
            403,
        )
        row = self.create("review", code="BASE", input_text="1")
        self.assertEqual(self.other.get(BASE + "/sessions/" + row["id"]).status_code, 404)
        with app.app_context():
            other = User.query.filter_by(username="other").first()
            submission = Submission(
                user_id=other.id,
                problem_id=PID,
                code_submitted="OK",
                language="python",
                status="Accepted",
            )
            db.session.add(submission)
            db.session.commit()
            sid = submission.id
        response = self.client.post(
            BASE + "/sessions",
            json={"mode": "review", "problem_id": PID, "submission_id": sid},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 404)

    def test_official_examples_immutable_and_user_claims_not_official(self):
        row = self.create()
        key = row["state"]["examples"][0]["id"]
        for data in (
            {"action": "delete_example", "example_id": key},
            {"action": "upsert_example", "example": {"id": key, "input": "1", "expected": "fake"}},
        ):
            response = self.client.patch(
                BASE + "/sessions/" + row["id"],
                json={"revision": row["revision"], **data},
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 400)
        response = self.client.patch(
            BASE + "/sessions/" + row["id"],
            json={
                "revision": row["revision"],
                "action": "upsert_example",
                "example": {"input": "9", "expected": "wrong"},
            },
            headers=self.headers,
        )
        row = self.data(response)["session"]
        self.assertEqual(row["state"]["examples"][-1]["source"], "user")

    def test_unknown_agreement_never_claims_correctness(self):
        row = self.generate(self.create(), ("AI_OK", "AI_OK"))
        result = self.data(self.post(row, "compare", input="123"))
        run = result["run"]
        self.assertFalse(run["different"])
        self.assertFalse(run["correctness_verified"])
        self.assertEqual(run["expected_source"], "unknown")
        self.assertTrue(
            all(r["passed"] is None and r["verdict"] == "unverified" for r in run["results"])
        )
        self.assertEqual(self.runner.call_count, 6)

    def test_failed_candidate_remains_comparable_selectable(self):
        row = self.generate(self.create())
        generation = row["state"]["generations"][-1]
        self.assertEqual(generation["status"], "ready")
        self.assertFalse(generation["candidates"][1]["verified"])
        row = self.data(
            self.post(
                row,
                "select",
                generation_id=generation["id"],
                candidate_id=generation["candidates"][1]["id"],
            )
        )["session"]
        self.assertTrue(row["state"]["selected"]["requires_formal_submission"])
        result = self.data(self.post(row, "compare", input="3661\n", expected="wrong"))
        self.assertEqual(result["run"]["expected_source"], "official")
        self.assertEqual([r["passed"] for r in result["run"]["results"]], [True, False])

    def test_user_expected_is_explicit_even_when_matched(self):
        row = self.generate(self.create(), ("BAD", "BAD"))
        run = self.data(self.post(row, "compare", input="987", expected="wrong"))["run"]
        self.assertEqual(run["expected_source"], "user")
        self.assertFalse(run["correctness_verified"])
        self.assertTrue(all(r["verdict"] == "matches_user" for r in run["results"]))

    def test_reference_requires_input_confirmation_and_matching_problem_version(self):
        row = self.generate(self.create(), ("AI_OK", "BAD"))
        run = self.data(self.post(row, "compare", input="123", input_validated=True))["run"]
        self.assertEqual(run["expected_source"], "reference")
        self.assertEqual(run["expected"].strip(), "0 2 3")
        self.assertNotIn("t=int(input())", json.dumps(run))
        with app.app_context():
            problem = db.session.get(Problem, PID)
            problem.description += "管理员已更新题意"
            db.session.commit()
        restored = self.data(self.client.get(BASE + "/sessions/" + row["id"]))["session"]
        self.assertFalse(restored["problem"]["reference_available"])
        self.assertTrue(restored["problem"]["changed"])
        self.assertEqual(
            self.post(
                restored,
                "verify",
                candidate_id=restored["state"]["generations"][-1]["candidates"][0]["id"],
            ).status_code,
            409,
        )
        fresh = self.create()
        self.assertFalse(fresh["problem"]["reference_available"])

    def test_reference_error_never_exposes_private_stderr(self):
        row = self.generate(self.create())
        with patch("modules.co_create.problem_service._reference", return_value="PRIVATE_ERROR"):
            run = self.data(self.post(row, "compare", input="123", input_validated=True))["run"]
        self.assertEqual(run["expected_source"], "unknown")
        self.assertNotIn("PRIVATE_SOURCE_LINE", json.dumps(run))

    def test_verify_no_submission_points_or_hidden_inputs_outputs(self):
        with app.app_context():
            problem = db.session.get(Problem, PID)
            secret = problem.test_cases.filter_by(is_public=False).first()
            secret.input_data, secret.expected_output = (
                "HIDDEN_SECRET_INPUT",
                "PRIVATE_EXPECTED_SECRET",
            )
            db.session.commit()
        row = self.create("review", code="PRIVATE_ERROR")
        result = self.data(self.post(row, "verify"))
        self.assertFalse(result["run"]["passed"])
        self.assertEqual(result["run"]["hidden_total"], 4)
        raw = json.dumps(result)
        self.assertNotIn("HIDDEN_SECRET_INPUT", raw)
        self.assertNotIn("PRIVATE_EXPECTED_SECRET", raw)
        for case in result["run"]["cases"]:
            if not case["is_public"]:
                self.assertEqual(set(case), {"id", "index", "is_public", "status", "passed"})
        with app.app_context():
            self.assertEqual(Submission.query.count(), 0)
            self.assertEqual(User.query.filter_by(username="student").first().points, 0)

    def test_review_prediction_bound_to_code_and_input_with_unknown_or_user_oracle(self):
        row = self.create("review", code="OK")
        row = self.data(
            self.post(row, "review", judgment="correct", prediction="0 2 3", prediction_input="123")
        )["session"]
        self.assertEqual(self.post(row, "review-run", input="124").status_code, 409)
        result = self.data(self.post(row, "review-run", input="123"))
        self.assertIsNone(result["run"]["passed"])
        self.assertTrue(result["run"]["prediction_matched"])
        row = self.data(self.post(result["session"], "review", code="BAD"))["session"]
        self.assertFalse(row["state"]["review"]["prediction_saved"])
        run = self.data(self.post(row, "review-run", input="123"))["run"]
        self.assertIsNone(run["prediction_matched"])

    def test_review_optional_prediction_and_explicit_clear(self):
        row = self.create("review", code="OK")
        result = self.data(self.post(row, "review-run", input="3661\n"))
        self.assertTrue(result["run"]["passed"])
        self.assertIsNone(result["run"]["prediction_matched"])
        row = self.data(
            self.post(result["session"], "review", prediction="0 0 1", prediction_input="1")
        )["session"]
        row = self.data(self.post(row, "review", clear_prediction=True))["session"]
        self.assertFalse(row["state"]["review"]["prediction_saved"])
        run = self.data(self.post(row, "review-run", input="2"))["run"]
        self.assertIsNone(run["prediction_matched"])

    def test_stale_completion_cannot_overwrite_newer_edit(self):
        row = self.create()

        def supersede(*args, **kwargs):
            with app.app_context():
                stored = db.session.get(CoCreateSession, row["id"])
                stored.revision += 1
                state = dict(stored.state)
                state["concurrent_edit"] = "preserved"
                stored.state = state
                db.session.commit()
            return [{"code": "OK"}, {"code": "BAD"}], "test"

        with patch("modules.co_create.ai.generate_problem", side_effect=supersede):
            response = self.post(row, "generate", source="ai")
        self.assertEqual(response.status_code, 409)
        restored = self.data(self.client.get(BASE + "/sessions/" + row["id"]))["session"]
        self.assertEqual(restored["state"]["concurrent_edit"], "preserved")

    def test_ai_failure_no_fake_fallback_and_baseline_source(self):
        row = self.create(code="BASE")
        with patch("modules.co_create.ai.generate_problem", side_effect=AIClientError("failed")):
            row = self.data(self.post(row, "generate", source="ai"))["session"]
        self.assertEqual(row["state"]["generations"][-1]["candidates"], [])
        row = self.generate(row, ("AI_OK",))
        candidates = row["state"]["generations"][-1]["candidates"]
        self.assertEqual([c["source"] for c in candidates], ["student", "ai"])
        self.assertIsNone(candidates[0]["model"])

    def test_explicit_resume_reuses_only_matching_original_context(self):
        row = self.create(code="BASE", input_text="3661", reuse=True)
        again = self.create(code="BASE", input_text="3661", reuse=True)
        self.assertEqual(row["id"], again["id"])
        changed = self.create(code="OK", input_text="3661", reuse=True)
        self.assertNotEqual(row["id"], changed["id"])
        other_language = self.create(code="BASE", input_text="3661", reuse=True, language="java")
        self.assertNotEqual(row["id"], other_language["id"])
        explicit_new = self.create(code="BASE", input_text="3661")
        self.assertNotEqual(row["id"], explicit_new["id"])

    def test_provider_protocol_only_public_data_and_no_intentional_error(self):
        row = self.create()
        with patch("modules.co_create.ai.available", return_value=True):
            self.provider.side_effect = None
            self.provider.return_value = (
                '{"candidates":[{"code":"OK","verified":true,"source":"reference"},{"code":"BAD"}]}'
            )
            candidates, _ = ai.generate_problem(row["problem"], "cpp", row["state"]["examples"])
        self.assertNotIn("verified", candidates[0])
        self.assertNotIn("source", candidates[0])
        payload = self.provider.call_args.args[0]
        self.assertNotIn("t=int(input())", json.dumps(payload))
        self.assertIn("不故意制造错误", payload["messages"][0]["content"])
        self.assertNotIn("reference_available", payload["messages"][1]["content"])


if __name__ == "__main__":
    unittest.main()

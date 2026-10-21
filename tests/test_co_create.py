"""Revision, ownership and evidence regressions in an isolated database.

Container and provider transports are stubbed; these tests never run code on
the host and never call a paid AI API. Real Docker smoke coverage is separate.
"""

import base64
import json
import os
import re
import unittest
from datetime import timedelta
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["FLASK_SECRET_KEY"] = "co-create-test-secret"
os.environ["AUTO_CREATE_DATABASE"] = "0"

from app import app
from models import User, db
from modules.co_create import service
from modules.co_create.catalog import IMPLEMENTATIONS, evaluate
from modules.co_create.models import CoCreateSession
from services.ai_client import AIClientError
from services.rate_limiter import _MEMORY_BUCKETS

BASE = "/api/co-create"


def teaching_transport(wrapper, language="Python", input_text=None):
    """Model the finite trusted rules without evaluating the candidate source."""
    encoded = re.search(r"base64.b64decode\('([^']+)'\)", wrapper).group(1)
    code = base64.b64decode(encoded).decode()
    family_rule = next((pair for pair, value in IMPLEMENTATIONS.items() if value == code), None)
    if family_rule is None:
        raise AssertionError("Test must declare transport behavior for unknown code")
    marker = re.search(r"CO_CREATE_RESULT_[a-f0-9]+:", wrapper).group(0)
    outcomes = [
        {"success": True, "output": evaluate(*family_rule, value)}
        for value in json.loads(input_text)
    ]
    return {
        "success": True,
        "status": "Accepted",
        "execution_backend": "docker",
        "time": 1,
        "output": marker + json.dumps(outcomes),
        "error": "",
    }


class CoCreateTest(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        _MEMORY_BUCKETS.clear()
        self.client, self.other = app.test_client(), app.test_client()
        with app.app_context():
            db.drop_all()
            db.create_all()
            for name in ("creator", "other-creator"):
                user = User(username=name, email=name + "@example.test")
                user.set_password("test-password")
                db.session.add(user)
            db.session.commit()
        self.headers = self.login(self.client, "creator")
        self.other_headers = self.login(self.other, "other-creator")
        self.runner_patch = patch(
            "modules.co_create.service.run_code", side_effect=teaching_transport
        )
        self.runner = self.runner_patch.start()
        self.addCleanup(self.runner_patch.stop)
        self.ai_patch = patch(
            "modules.co_create.ai.chat_completion",
            side_effect=AssertionError("No paid API in tests"),
        )
        self.provider = self.ai_patch.start()
        self.addCleanup(self.ai_patch.stop)

    def login(self, client, username):
        response = client.post(
            "/api/login", json={"username": username, "password": "test-password"}
        )
        self.assertEqual(response.status_code, 200)
        headers = {"X-CSRF-Token": response.json["csrf_token"]}
        # Provider transport is mocked; explicitly opt this fixture into AI access.
        self.assertEqual(
            client.put(
                "/api/profile/ai-settings",
                headers=headers,
                json={"mode": "custom", "api_key": "sk-unit-test-placeholder"},
            ).status_code,
            200,
        )
        return headers

    def data(self, response, status=200):
        self.assertEqual(response.status_code, status, response.get_json())
        return response.get_json()["data"]

    def create(self, mode="examples", scenario="dedupe"):
        return self.data(
            self.client.post(
                BASE + "/sessions",
                json={"mode": mode, "scenario_id": scenario},
                headers=self.headers,
            ),
            201,
        )["session"]

    def post(self, row, action, **data):
        return self.client.post(
            BASE + "/sessions/" + row["id"] + "/" + action,
            json={"revision": row["revision"], **data},
            headers=self.headers,
        )

    def generate(self, row):
        return self.data(self.post(row, "generate", source="teaching"))["session"]

    def test_catalog_is_public_and_three_scenarios(self):
        data = self.data(app.test_client().get(BASE + "/catalog"))
        self.assertEqual(len(data["scenarios"]), 3)
        self.assertNotIn("api_key", data)

    def test_login_and_csrf_required(self):
        self.assertEqual(app.test_client().get(BASE + "/sessions").status_code, 401)
        response = self.client.post(
            BASE + "/sessions", json={"mode": "examples", "scenario_id": "dedupe"}
        )
        self.assertEqual(response.status_code, 403)

    def test_owner_isolation(self):
        row = self.create()
        url = BASE + "/sessions/" + row["id"]
        self.assertEqual(self.other.get(url).status_code, 404)
        self.assertEqual(
            self.other.post(
                url + "/generate",
                json={"revision": 0, "source": "teaching"},
                headers=self.other_headers,
            ).status_code,
            404,
        )
        self.assertEqual(self.data(self.other.get(BASE + "/sessions"))["sessions"], [])

    def test_examples_generate_compare_add_example_select_restore(self):
        row = self.create()
        self.assertEqual(len(row["state"]["examples"]), 1)
        row = self.generate(row)
        generation = row["state"]["generations"][-1]
        self.assertEqual(generation["status"], "verified")
        self.assertTrue(generation["behavior_difference"]["different"])
        self.assertTrue(
            all(c["verified"] and c["source"] == "teaching" for c in generation["candidates"])
        )
        self.assertEqual(self.runner.call_count, 2)
        data = self.data(self.post(row, "compare", input=["A", "B", "A"]))
        self.assertTrue(data["run"]["different"])
        row = data["session"]
        response = self.client.patch(
            BASE + "/sessions/" + row["id"],
            json={
                "revision": row["revision"],
                "action": "upsert_example",
                "example": {"input": ["A", "B", "A"], "expected": ["A", "B"]},
            },
            headers=self.headers,
        )
        row = self.data(response)["session"]
        self.assertIsNone(row["state"]["current_generation_id"])
        self.assertEqual(len(row["state"]["generations"]), 1)
        stale = self.post(
            row,
            "select",
            generation_id=generation["id"],
            candidate_id=generation["candidates"][0]["id"],
        )
        self.assertEqual(stale.status_code, 409)
        row = self.generate(row)
        generation = row["state"]["generations"][-1]
        self.assertEqual(len(generation["candidates"]), 1)
        row = self.data(
            self.post(
                row,
                "select",
                generation_id=generation["id"],
                candidate_id=generation["candidates"][0]["id"],
            )
        )["session"]
        restored = self.data(self.client.get(BASE + "/sessions/" + row["id"]))["session"]
        self.assertEqual(restored["state"]["selected"]["rule_id"], "first")
        self.provider.assert_not_called()

    def test_stale_revision_rejected(self):
        row = self.create()
        generated = self.generate(row)
        response = self.post(row, "generate", source="teaching")
        self.assertEqual(response.status_code, 409)
        self.assertGreater(generated["revision"], row["revision"])

    def test_docker_unavailable_never_verifies(self):
        self.runner.side_effect = None
        self.runner.return_value = {
            "success": False,
            "status": "Environment Error",
            "error": "Docker unavailable",
        }
        row = self.generate(self.create())
        generation = row["state"]["generations"][-1]
        self.assertEqual(generation["status"], "failed")
        self.assertTrue(all(not c["verified"] for c in generation["candidates"]))
        self.assertEqual(
            self.post(
                row,
                "select",
                generation_id=generation["id"],
                candidate_id=generation["candidates"][0]["id"],
            ).status_code,
            409,
        )

    def test_ai_failure_is_not_teaching_fallback(self):
        with patch(
            "modules.co_create.ai.generate",
            side_effect=AIClientError("secret-provider-detail"),
        ):
            row = self.data(self.post(self.create(), "generate", source="ai"))["session"]
        generation = row["state"]["generations"][-1]
        self.assertEqual(generation["source"], "ai")
        self.assertEqual(generation["status"], "failed")
        self.assertEqual(generation["candidates"], [])
        self.assertNotIn("secret-provider-detail", generation["error"])
        self.runner.assert_not_called()

    def test_model_label_does_not_override_real_behavior(self):
        candidates = [
            {
                "rule_id": rule,
                "code": IMPLEMENTATIONS[("dedupe", "first")],
                "explanation": "Claimed correct",
            }
            for rule in ("first", "last")
        ]
        with patch("modules.co_create.ai.generate", return_value=(candidates, "stub-model")):
            row = self.data(self.post(self.create(), "generate", source="ai"))["session"]
        generation = row["state"]["generations"][-1]
        self.assertEqual(generation["status"], "failed")
        self.assertFalse(generation["candidates"][1]["verified"])
        self.assertTrue(generation["candidates"][1]["verification"]["cases"][0]["passed"])
        self.assertFalse(generation["candidates"][1]["verification"]["cases"][-1]["passed"])

    def test_boolean_output_cannot_pass_integer_contract(self):
        self.assertFalse(service.same_output([True], [1]))
        self.assertFalse(service.same_output([1.0], [1]))
        self.assertTrue(service.same_output([1], [1]))

    def test_review_prediction_counterexample_revision_and_reflection(self):
        row = self.create("review")
        self.assertFalse(row["state"]["review"]["verified"])
        self.assertEqual(self.post(row, "review-run", input=["A", "B", "A"]).status_code, 400)
        row = self.data(
            self.post(
                row,
                "review",
                judgment="incorrect",
                prediction=["B", "A"],
                prediction_input=["A", "B", "A"],
                reflection="先检查重复项的顺序",
            )
        )["session"]
        data = self.data(self.post(row, "review-run", input=["A", "B", "A"]))
        self.assertTrue(data["run"]["success"])
        self.assertFalse(data["run"]["passed"])
        self.assertTrue(data["run"]["prediction_matched"])
        self.assertEqual(data["run"]["expected"], ["A", "B"])
        row = data["session"]
        row = self.data(
            self.post(
                row,
                "review",
                code=IMPLEMENTATIONS[("dedupe", "first")],
                prediction=["A", "B"],
                prediction_input=["A", "B", "A"],
                reflection="已改为首次出现顺序",
            )
        )["session"]
        self.assertEqual(row["state"]["review"]["source"], "student")
        self.assertEqual(row["state"]["review"]["code_revision"], 1)
        self.assertEqual(len(row["state"]["review"]["evidence"]), 1)
        data = self.data(self.post(row, "review-run", input=["A", "B", "A"]))
        self.assertTrue(data["run"]["passed"])
        self.assertEqual(data["run"]["code_revision"], 1)
        self.assertFalse(data["session"]["state"]["review"]["verified"])
        self.assertEqual(len(data["session"]["state"]["review"]["history"]), 1)

    def test_invalid_review_counterexample_never_executes(self):
        row = self.create("review", "threshold")
        row = self.data(
            self.post(
                row,
                "review",
                judgment="incorrect",
                prediction=[80],
                prediction_input={"values": [60, 80], "threshold": 60},
            )
        )["session"]
        self.assertEqual(
            self.post(row, "review-run", input={"values": [True], "threshold": 60}).status_code,
            400,
        )
        self.runner.assert_not_called()

    def test_mode_mismatch_and_invalid_json(self):
        row = self.create("review")
        self.assertEqual(self.post(row, "generate", source="teaching").status_code, 400)
        response = self.client.post(BASE + "/sessions", json=[], headers=self.headers)
        self.assertEqual(response.status_code, 400)

    def test_contradictory_examples_fail_without_fake_candidates(self):
        row = self.create()
        response = self.client.patch(
            BASE + "/sessions/" + row["id"],
            json={
                "revision": row["revision"],
                "action": "upsert_example",
                "example": {
                    "id": "seed-1",
                    "input": ["A", "A", "B"],
                    "expected": ["B"],
                },
            },
            headers=self.headers,
        )
        row = self.generate(self.data(response)["session"])
        self.assertEqual(row["state"]["generations"][-1]["status"], "failed")
        self.runner.assert_not_called()

    def test_edit_delete_limits_and_old_candidate_rejection(self):
        row = self.create()
        response = self.client.patch(
            BASE + "/sessions/" + row["id"],
            json={"revision": 0, "action": "delete_example", "example_id": "seed-1"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(
            BASE + "/sessions/" + row["id"],
            json={
                "revision": 0,
                "action": "upsert_example",
                "example": {"input": ["A", "A", "B"], "expected": ["A", "B"]},
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)

    def test_superseded_long_generation_cannot_overwrite_edit(self):
        row = self.create()
        count = 0

        def interrupted_transport(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 1:
                stored = CoCreateSession.query.filter_by(id=row["id"]).first()
                service.update_examples(
                    stored,
                    stored.revision,
                    {
                        "action": "upsert_example",
                        "example": {"input": ["A", "B", "A"], "expected": ["A", "B"]},
                    },
                )
            return teaching_transport(*args, **kwargs)

        self.runner.side_effect = interrupted_transport
        response = self.post(row, "generate", source="teaching")
        self.assertEqual(response.status_code, 409)
        restored = self.data(self.client.get(BASE + "/sessions/" + row["id"]))["session"]
        self.assertEqual(len(restored["state"]["examples"]), 2)
        self.assertIsNone(restored["state"]["current_generation_id"])

    def test_teaching_all_three_families(self):
        for scenario in ("dedupe", "threshold", "ordering"):
            row = self.generate(self.create(scenario=scenario))
            self.assertEqual(row["state"]["generations"][-1]["status"], "verified")
            self.assertTrue(row["state"]["generations"][-1]["behavior_difference"]["different"])

    def test_ai_adapter_validates_reply(self):
        from modules.co_create import ai
        from modules.co_create.catalog import get_scenario

        scenario = get_scenario("dedupe")
        with patch("modules.co_create.ai.available", return_value=True):
            self.provider.side_effect = None
            self.provider.return_value = '{"candidates": []}'
            with self.assertRaises(AIClientError):
                ai.generate(scenario, scenario["rule_options"], scenario["seed_examples"])

    def test_prediction_is_bound_to_input_and_code_version(self):
        row = self.create("review")
        row = self.data(
            self.post(
                row,
                "review",
                judgment="incorrect",
                prediction=["B", "A"],
                prediction_input=["A", "B", "A"],
            )
        )["session"]
        self.assertEqual(self.post(row, "review-run", input=["A", "B"]).status_code, 409)
        row = self.data(self.post(row, "review", code=IMPLEMENTATIONS[("dedupe", "first")]))[
            "session"
        ]
        self.assertFalse(row["state"]["review"]["prediction_saved"])
        self.assertEqual(self.post(row, "review-run", input=["A", "B", "A"]).status_code, 400)
        self.runner.assert_not_called()

    def test_interrupted_generation_recovers_to_failed(self):
        row = self.create()
        with app.app_context():
            stored = CoCreateSession.query.filter_by(id=row["id"]).first()
            from modules.co_create.models import now

            state = dict(stored.state)
            state["generations"] = [
                {
                    "id": "interrupted",
                    "status": "running",
                    "created_at": service.stamp(now() - timedelta(minutes=6)),
                    "candidates": [],
                }
            ]
            state["current_generation_id"] = "interrupted"
            stored.state = state
            db.session.commit()
        restored = self.data(self.client.get(BASE + "/sessions/" + row["id"]))["session"]
        self.assertEqual(restored["state"]["generations"][-1]["status"], "failed")
        self.assertEqual(restored["revision"], row["revision"] + 1)


if __name__ == "__main__":
    unittest.main()

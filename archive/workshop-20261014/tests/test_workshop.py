"""Creation boundaries, version ownership, and AI proposals without paid calls."""

import json
import os
import unittest
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["AUTO_CREATE_DATABASE"] = "0"
os.environ["FLASK_SECRET_KEY"] = "workshop-test"

from app import app
from models import User, WorkshopRun, WorkshopSuggestion, db
from services.rate_limiter import _MEMORY_BUCKETS
from services.workshop import parse_trace, validate_trace
from services.workshop_catalog import normalize_params, scene_spec

TRACE = {"scene": "ocean", "frames": [[[100, 200], [120, 230]], [[110, 205], [125, 234]]]}


class WorkshopTest(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        _MEMORY_BUCKETS.clear()
        self.client = app.test_client()
        with app.app_context():
            db.drop_all()
            db.create_all()
            for name in ("creator", "other"):
                user = User(username=name, email=name + "@example.test")
                user.set_password("workshop-test-password")
                db.session.add(user)
            db.session.commit()
        self.headers = self.login("creator")

    def login(self, name):
        response = self.client.post(
            "/api/login",
            json={"username": name, "password": "workshop-test-password"},
            headers=getattr(self, "headers", {}),
        )
        self.assertEqual(response.status_code, 200)
        return {"X-CSRF-Token": response.json["data"]["csrf_token"]}

    def post(self, path, data):
        return self.client.post("/api/workshop/" + path, json=data, headers=self.headers)

    def payload(self):
        return {
            "scene": "ocean",
            "code": scene_spec("ocean")["code"],
            "params": normalize_params("ocean", {}),
            "title": "我的鱼群",
        }

    def create_run(self, **changes):
        with patch(
            "routes.workshop.run_code",
            return_value={
                "success": True,
                "output": json.dumps(TRACE),
                "execution_backend": "docker",
                "time": 30,
            },
        ):
            response = self.post("run", {**self.payload(), **changes})
        self.assertEqual(response.status_code, 201, response.json)
        return response.json["data"]["run"]

    def test_public_catalog_and_session_boundaries(self):
        self.assertEqual(len(self.client.get("/api/workshop/catalog").json["data"]["scenes"]), 3)
        self.assertEqual(
            self.client.post("/api/workshop/run", json=self.payload()).status_code, 403
        )
        guest = app.test_client()
        self.assertEqual(guest.post("/api/workshop/run", json=self.payload()).status_code, 401)
        self.assertEqual(guest.get("/api/workshop/projects").status_code, 401)

    def test_real_run_snapshot_cannot_be_rewritten_on_save(self):
        run = self.create_run()
        response = self.post(
            "projects",
            {"run_id": run["id"], "title": "保存的名称", "code": "forged", "palette": "sunrise"},
        )
        self.assertEqual(response.status_code, 201)
        pid = response.json["data"]["project"]["id"]
        data = self.client.get(f"/api/workshop/projects/{pid}").json["data"]
        self.assertEqual(data["run"]["code"], self.payload()["code"])
        self.assertEqual(data["run"]["trace"], TRACE)
        self.assertEqual(data["palette"], "sunrise")
        self.assertEqual(data["versions"][0]["number"], 1)

    def test_owner_isolation_for_runs_projects_versions_and_suggestions(self):
        run = self.create_run()
        project = self.post("projects", {"run_id": run["id"], "title": "私有作品"}).json["data"][
            "project"
        ]
        detail = self.client.get(f"/api/workshop/projects/{project['id']}").json["data"]
        with app.app_context():
            suggestion = WorkshopSuggestion(
                user_id=1, scene="ocean", prompt="私有", base_fingerprint="x" * 64, result={}
            )
            db.session.add(suggestion)
            db.session.commit()
            sid = suggestion.id
        self.headers = self.login("other")
        self.assertEqual(self.client.get("/api/workshop/projects").json["data"]["projects"], [])
        self.assertEqual(
            self.client.get(f"/api/workshop/projects/{project['id']}").status_code, 404
        )
        self.assertEqual(
            self.client.get(
                f"/api/workshop/projects/{project['id']}/versions/{detail['versions'][0]['id']}"
            ).status_code,
            404,
        )
        self.assertEqual(
            self.post("projects", {"run_id": run["id"], "title": "越权"}).status_code, 404
        )
        self.assertEqual(
            self.post("run", {**self.payload(), "suggestion_id": sid}).status_code, 404
        )

    def test_concurrent_save_conflict_keeps_both_versions(self):
        run = self.create_run()
        project = self.post("projects", {"run_id": run["id"], "title": "作品"}).json["data"][
            "project"
        ]
        payload = {
            "run_id": run["id"],
            "title": "版本二",
            "project_id": project["id"],
            "revision": 1,
        }
        self.assertEqual(self.post("projects", payload).status_code, 201)
        self.assertEqual(self.post("projects", payload).status_code, 409)
        detail = self.client.get(f"/api/workshop/projects/{project['id']}").json["data"]
        self.assertEqual([v["number"] for v in detail["versions"]], [2, 1])

    def test_invalid_parameters_and_execution_output_never_create_run(self):
        with patch("routes.workshop.run_code") as runner:
            for params in [{"count": 100}, {"count": True}, {"speed": float("inf")}, {"extra": 1}]:
                self.assertEqual(
                    self.post("run", {**self.payload(), "params": params}).status_code, 400
                )
            runner.assert_not_called()
        for output in [
            '{"scene":"ocean","frames":[[[NaN,0]]]}',
            "print debug\n{}",
            '{"scene":"ocean","frames":[]}',
        ]:
            with patch(
                "routes.workshop.run_code", return_value={"success": True, "output": output}
            ):
                self.assertEqual(self.post("run", self.payload()).status_code, 422)
        with patch(
            "routes.workshop.run_code",
            return_value={
                "success": False,
                "status": "Environment Error",
                "error": "Docker 未启动",
            },
        ):
            self.assertEqual(self.post("run", self.payload()).status_code, 503)
        with app.app_context():
            self.assertEqual(WorkshopRun.query.count(), 0)

    def test_trace_contract_rejects_impossible_sort_and_paths(self):
        with self.assertRaises(ValueError):
            validate_trace(
                "sorting",
                {
                    "scene": "sorting",
                    "frames": [
                        {"values": [1], "focus": [], "swapped": False},
                        {"values": [2], "focus": [], "swapped": False},
                    ],
                },
            )
        for path in [[[0, 9], [13, 0]], [[1, 1], [1, 2]]]:
            with self.assertRaises(ValueError):
                validate_trace(
                    "route",
                    {
                        "scene": "route",
                        "width": 14,
                        "height": 10,
                        "walls": [],
                        "visited": [],
                        "path": path,
                    },
                )
        self.assertEqual(parse_trace("ocean", json.dumps(TRACE)), TRACE)
        with self.assertRaises(ValueError):
            parse_trace("ocean", "[" * 1100 + "0" + "]" * 1100)

    def test_ai_candidate_is_recorded_but_never_auto_executed(self):
        candidate = {
            "title": "慢潮",
            "summary": "降低速度",
            "params": {**self.payload()["params"], "speed": 1},
            "code": self.payload()["code"],
        }
        with (
            patch("services.workshop.chat_completion", return_value=json.dumps(candidate)) as model,
            patch("routes.workshop.run_code") as runner,
        ):
            result = self.post("suggest", {**self.payload(), "prompt": "慢一点"})
        self.assertEqual(result.status_code, 201, result.json)
        runner.assert_not_called()
        self.assertIn("慢一点", model.call_args.args[0]["messages"][1]["content"])
        suggestion = result.json["data"]["suggestion"]
        self.assertNotIn("response_model", suggestion["generation"])
        run = self.create_run(params=candidate["params"], suggestion_id=suggestion["id"])
        self.assertEqual(run["provenance"]["kind"], "ai_candidate")
        edited = self.create_run(
            params=candidate["params"],
            code=candidate["code"] + "\n",
            suggestion_id=suggestion["id"],
        )
        self.assertEqual(edited["provenance"]["kind"], "edited_ai_candidate")

    def test_bad_ai_response_and_large_request_fail_without_records(self):
        with patch("services.workshop.chat_completion", return_value='{"code":"oops"}'):
            self.assertEqual(
                self.post("suggest", {**self.payload(), "prompt": "调整"}).status_code, 502
            )
        self.assertEqual(
            self.post("run", {**self.payload(), "code": "x" * 100000}).status_code, 413
        )
        with app.app_context():
            self.assertEqual(WorkshopSuggestion.query.count(), 0)


if __name__ == "__main__":
    unittest.main()

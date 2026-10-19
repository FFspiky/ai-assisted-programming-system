"""Task-room contracts, ownership and evidence in an isolated database.

AI and container transport are mocked here; the acceptance oracle still runs on
the host, so a provider's claims cannot make an incorrect result pass.
"""

import io
import json
import os
import unittest
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["FLASK_SECRET_KEY"] = "task-room-test-secret"
os.environ["AUTO_CREATE_DATABASE"] = "0"

from app import app  # noqa: E402
from models import User, db  # noqa: E402
from modules.task_room import service as room_service  # noqa: E402
from modules.task_room.models import TaskContract, TaskMessage, TaskProject, TaskRun  # noqa: E402
from services.ai_client import AIClientError  # noqa: E402
from services.rate_limiter import _MEMORY_BUCKETS  # noqa: E402

BASE = "/api/task-room"


class TaskRoomTest(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        _MEMORY_BUCKETS.clear()
        self.client = app.test_client()
        self.other = app.test_client()
        with app.app_context():
            db.drop_all()
            db.create_all()
            for username in ("task-owner", "task-other"):
                user = User(username=username, email=username + "@example.test")
                user.set_password("test-password")
                db.session.add(user)
            db.session.commit()
        self.headers = self.login(self.client, "task-owner")
        self.other_headers = self.login(self.other, "task-other")
        self.ai_patch = patch(
            "modules.task_room.ai.chat_completion",
            return_value=json.dumps({"reply": "请明确重复记录的处理规则。", "code": None}),
        )
        self.ai = self.ai_patch.start()
        self.addCleanup(self.ai_patch.stop)
        self.runner_patch = patch(
            "modules.task_room.service.run_code",
            side_effect=AssertionError("This unit test must explicitly stub container execution"),
        )
        self.runner = self.runner_patch.start()
        self.addCleanup(self.runner_patch.stop)
        self.scenario = self.data(self.client.get(BASE + "/catalog"))["scenarios"][0]
        self.rules = {group["key"]: group["recommended"] for group in self.scenario["rule_groups"]}

    def login(self, client, username):
        response = client.post(
            "/api/login", json={"username": username, "password": "test-password"}
        )
        self.assertEqual(response.status_code, 200)
        return {"X-CSRF-Token": response.json["csrf_token"]}

    def data(self, response, status=200):
        self.assertEqual(response.status_code, status, response.get_json())
        return response.get_json()["data"]

    def create(self):
        return self.data(
            self.client.post(
                BASE + "/projects",
                json={"scenario_id": self.scenario["id"]},
                headers=self.headers,
            ),
            201,
        )["project"]

    def url(self, project, suffix=""):
        return BASE + "/projects/" + project["id"] + suffix

    def load(self, project):
        return self.data(self.client.get(self.url(project)))["project"]

    def freeze(self, project):
        return self.data(
            self.client.post(
                self.url(project, "/freeze"),
                json={"rules": self.rules, "revision": project["revision"]},
                headers=self.headers,
            )
        )["project"]

    def save(self, project, code):
        return self.data(
            self.client.patch(
                self.url(project),
                json={"code": code, "draft_revision": project["draft_revision"]},
                headers=self.headers,
            )
        )["project"]

    def message(self, project, intent="customer", operation_id=None):
        return self.client.post(
            self.url(project, "/messages"),
            json={
                "intent": intent,
                "message": "请解释当前任务的边界规则。",
                "code": project["code"],
                "operation_id": operation_id or str(uuid.uuid4()),
            },
            headers=self.headers,
        )

    def execution(self, project, wrong=False):
        cases = project["contract"]["cases"]
        return {
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
                        for index, case in enumerate(cases)
                    ]
                },
                ensure_ascii=False,
            ),
            "error": "",
            "time": 0.1,
            "execution_backend": "docker",
            "output_truncated": False,
        }

    def accept(self, project, wrong=False):
        self.runner.side_effect = None
        self.runner.return_value = self.execution(project, wrong)
        return self.data(
            self.client.post(
                self.url(project, "/run"),
                json={
                    "kind": "acceptance",
                    "code": project["code"],
                    "contract_id": project["contract"]["id"],
                },
                headers=self.headers,
            )
        )

    def deliver(self, project):
        return self.client.post(
            self.url(project, "/deliver"),
            json={
                "revision": project["revision"],
                "code": project["code"],
                "contract_id": project["contract"]["id"],
            },
            headers=self.headers,
        )

    def test_public_catalog_and_authenticated_mutations(self):
        anonymous = app.test_client()
        catalog = self.data(anonymous.get(BASE + "/catalog"))
        self.assertGreaterEqual(len(catalog["scenarios"]), 3)
        self.assertIsInstance(catalog["ai_available"], bool)
        self.assertEqual(anonymous.get(BASE + "/projects").status_code, 401)
        self.assertEqual(
            anonymous.post(
                BASE + "/projects", json={"scenario_id": self.scenario["id"]}
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(
                BASE + "/projects", json={"scenario_id": self.scenario["id"]}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                BASE + "/projects", json={"scenario_id": "missing"}, headers=self.headers
            ).status_code,
            400,
        )

    def test_projects_are_private_for_all_read_and_write_paths(self):
        project = self.freeze(self.create())
        self.data(self.message(project, "coach"))
        project = self.load(project)
        assistant = next(item for item in project["messages"] if item["role"] == "assistant")
        self.assertEqual(self.data(self.other.get(BASE + "/projects"))["projects"], [])
        for suffix in ("", "/export"):
            self.assertEqual(self.other.get(self.url(project, suffix)).status_code, 404)
        for suffix, body in (
            ("/freeze", {"rules": self.rules, "revision": project["revision"]}),
            (
                "/messages",
                {"intent": "customer", "message": "hello", "operation_id": str(uuid.uuid4())},
            ),
            (
                "/run",
                {
                    "kind": "acceptance",
                    "code": project["code"],
                    "contract_id": project["contract"]["id"],
                },
            ),
            ("/changes", {"change_id": "missing", "revision": project["revision"]}),
            (
                "/deliver",
                {
                    "code": project["code"],
                    "contract_id": project["contract"]["id"],
                    "revision": project["revision"],
                },
            ),
            (
                "/messages/" + assistant["id"] + "/apply",
                {"draft_revision": project["draft_revision"]},
            ),
            (
                "/messages/" + assistant["id"] + "/undo",
                {"draft_revision": project["draft_revision"]},
            ),
        ):
            self.assertEqual(
                self.other.post(
                    self.url(project, suffix), json=body, headers=self.other_headers
                ).status_code,
                404,
                suffix,
            )
        self.assertEqual(
            self.other.patch(
                self.url(project),
                json={"code": "def solve(data): return data", "draft_revision": 0},
                headers=self.other_headers,
            ).status_code,
            404,
        )

    def test_contract_rules_are_strict_and_freezing_is_revision_guarded(self):
        project = self.create()
        for rules in ({}, {**self.rules, "unexpected": "yes"}):
            self.assertEqual(
                self.client.post(
                    self.url(project, "/freeze"),
                    json={"rules": rules, "revision": project["revision"]},
                    headers=self.headers,
                ).status_code,
                400,
            )
        bad = dict(self.rules)
        bad[next(iter(bad))] = "unrecognized-option"
        self.assertEqual(
            self.client.post(
                self.url(project, "/freeze"),
                json={"rules": bad, "revision": project["revision"]},
                headers=self.headers,
            ).status_code,
            400,
        )
        frozen = self.freeze(project)
        self.assertEqual(frozen["state"], "development")
        self.assertEqual(frozen["contract"]["version"], 1)
        self.assertTrue(frozen["contract"]["cases"])
        self.assertEqual(
            self.client.post(
                self.url(project, "/freeze"),
                json={"rules": self.rules, "revision": project["revision"]},
                headers=self.headers,
            ).status_code,
            409,
        )
        with app.app_context():
            self.assertEqual(TaskContract.query.filter_by(project_id=project["id"]).count(), 1)

    def test_saving_stale_draft_cannot_overwrite_new_work(self):
        project = self.create()
        saved = self.save(project, "def solve(data):\n    return {'new': True}\n")
        self.assertGreater(saved["draft_revision"], project["draft_revision"])
        self.assertEqual(
            self.client.patch(
                self.url(project),
                json={"code": "old tab", "draft_revision": project["draft_revision"]},
                headers=self.headers,
            ).status_code,
            409,
        )
        self.assertEqual(self.load(project)["code"], saved["code"])

    def test_customer_reply_does_not_freeze_rules_and_retries_are_idempotent(self):
        project = self.create()
        operation = str(uuid.uuid4())
        self.data(self.message(project, operation_id=operation))
        self.data(self.message(project, operation_id=operation))
        self.assertEqual(self.ai.call_count, 1)
        loaded = self.load(project)
        self.assertEqual(loaded["state"], "discovery")
        self.assertIsNone(loaded["contract"])
        self.assertEqual(len([m for m in loaded["messages"] if m["role"] == "assistant"]), 1)

    def test_ai_failure_is_visible_and_does_not_invent_a_successful_reply(self):
        project = self.create()
        self.ai.side_effect = AIClientError("模型服务暂不可用")
        response = self.message(project)
        self.assertGreaterEqual(response.status_code, 400)
        with app.app_context():
            completed = TaskMessage.query.filter_by(
                project_id=project["id"], role="assistant"
            ).all()
            self.assertFalse(any(item.payload.get("state") == "complete" for item in completed))
            self.assertIsNone(TaskProject.query.filter_by(id=project["id"]).one().delivery)

    def test_unexpected_provider_error_does_not_leave_request_running_forever(self):
        project = self.create()
        self.ai.side_effect = RuntimeError("provider internal error must not reach the browser")
        response = self.message(project)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("provider internal error", response.get_data(as_text=True))
        loaded = self.load(project)
        assistant = next(item for item in loaded["messages"] if item["role"] == "assistant")
        self.assertEqual(assistant["payload"]["state"], "failed")
        self.ai.side_effect = None
        self.assertEqual(self.message(loaded).status_code, 200)

    def test_failed_ai_operation_replay_stays_failed_until_a_new_request(self):
        project = self.create()
        operation = str(uuid.uuid4())
        self.ai.side_effect = AIClientError("模型服务暂不可用")
        self.assertEqual(self.message(project, operation_id=operation).status_code, 503)
        self.ai.side_effect = None
        replay = self.message(project, operation_id=operation)
        self.assertEqual(replay.status_code, 503)
        self.assertEqual(self.ai.call_count, 1)
        self.assertEqual(self.message(project, operation_id=str(uuid.uuid4())).status_code, 200)
        self.assertEqual(self.ai.call_count, 2)

    def test_candidate_is_explicit_reversible_and_stale_protected(self):
        project = self.freeze(self.create())
        original = project["code"]
        candidate = "def solve(data):\n    return {'candidate': True}\n"
        self.ai.return_value = json.dumps({"reply": "这是待验证的候选代码。", "code": candidate})
        self.data(self.message(project, "coach"))
        project = self.load(project)
        proposal = next(m for m in reversed(project["messages"]) if m["role"] == "assistant")
        self.assertEqual(project["code"], original)
        applied = self.data(
            self.client.post(
                self.url(project, "/messages/" + proposal["id"] + "/apply"),
                json={"draft_revision": project["draft_revision"]},
                headers=self.headers,
            )
        )["project"]
        self.assertEqual(applied["code"], candidate)
        undone = self.data(
            self.client.post(
                self.url(project, "/messages/" + proposal["id"] + "/undo"),
                json={"draft_revision": applied["draft_revision"]},
                headers=self.headers,
            )
        )["project"]
        self.assertEqual(undone["code"], original)
        changed = self.save(undone, "def solve(data):\n    return {'my_work': True}\n")
        self.assertEqual(
            self.client.post(
                self.url(project, "/messages/" + proposal["id"] + "/apply"),
                json={"draft_revision": changed["draft_revision"]},
                headers=self.headers,
            ).status_code,
            409,
        )
        self.assertEqual(self.load(project)["code"], changed["code"])

    def test_container_success_does_not_override_wrong_acceptance_output(self):
        project = self.freeze(self.create())
        data = self.accept(project, wrong=True)
        self.assertEqual(data["run"]["status"], "failed")
        self.assertEqual(data["run"]["passed"], 0)
        self.assertEqual(self.deliver(self.load(project)).status_code, 409)
        self.assertEqual(self.ai.call_count, 0)

    def test_contract_mismatch_and_unconfirmed_work_cannot_be_run_or_delivered(self):
        discovery = self.create()
        self.assertEqual(
            self.deliver({**discovery, "contract": {"id": "missing"}}).status_code, 409
        )
        project = self.freeze(discovery)
        self.assertEqual(self.deliver(project).status_code, 409)
        response = self.client.post(
            self.url(project, "/run"),
            json={"kind": "acceptance", "code": project["code"], "contract_id": "missing"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 409)
        self.assertFalse(self.runner.called)

    def test_delivery_binds_exact_saved_code_and_current_acceptance(self):
        project = self.freeze(self.create())
        run = self.accept(project)["run"]
        self.assertEqual(run["status"], "passed")
        self.assertEqual(run["passed"], run["total"])
        changed = self.save(project, "def solve(data):\n    return {'edited_after_test': True}\n")
        self.assertEqual(self.deliver(changed).status_code, 409)
        self.accept(changed)
        delivered = self.data(self.deliver(self.load(project)))["project"]
        self.assertEqual(delivered["state"], "delivered")
        self.assertTrue(delivered["delivery"])

    def test_editing_delivered_code_reopens_project_and_invalidates_delivery(self):
        project = self.freeze(self.create())
        self.accept(project)
        delivered = self.data(self.deliver(self.load(project)))["project"]
        same = self.save(delivered, delivered["code"])
        self.assertEqual(same["state"], "delivered")
        self.assertEqual(same["delivery"], delivered["delivery"])
        changed = self.save(same, "def solve(data):\n    return {'reopened': True}\n")
        self.assertEqual(changed["state"], "development")
        self.assertIsNone(changed["delivery"])
        self.assertGreater(changed["revision"], delivered["revision"])
        self.assertEqual(self.deliver(changed).status_code, 409)
        self.accept(changed)
        self.assertEqual(
            self.data(self.deliver(self.load(changed)))["project"]["state"], "delivered"
        )

    def test_draft_changed_during_delivery_cannot_be_marked_as_delivered(self):
        project = self.freeze(self.create())
        self.accept(project)
        original_transition = room_service.transition
        other_code = "def solve(data):\n    return {'other_window': True}\n"

        def concurrent_save(record, revision, **kwargs):
            # Commit an independent tab's save between the delivery precheck and
            # its atomic transition, without changing the workflow revision.
            TaskProject.query.filter_by(id=record.id).update(
                {"code": other_code, "draft_revision": record.draft_revision + 1},
                synchronize_session=False,
            )
            db.session.commit()
            return original_transition(record, revision, **kwargs)

        with patch("modules.task_room.service.transition", side_effect=concurrent_save):
            self.assertEqual(self.deliver(project).status_code, 409)
        current = self.load(project)
        self.assertEqual(current["code"], other_code)
        self.assertEqual(current["state"], "development")
        self.assertIsNone(current["delivery"])

    def test_interrupted_old_run_recovers_without_unlocking_delivery(self):
        project = self.freeze(self.create())
        with app.app_context():
            run = TaskRun(
                project_id=project["id"],
                contract_id=project["contract"]["id"],
                contract_version=1,
                kind="acceptance",
                code=project["code"],
                code_hash="unfinished",
                total=len(project["contract"]["cases"]),
                status="running",
                created_at=datetime.now(timezone.utc) - timedelta(minutes=3),
            )
            db.session.add(run)
            db.session.commit()
        recovered = self.load(project)
        self.assertEqual(recovered["runs"][0]["status"], "error")
        self.assertEqual(self.deliver(recovered).status_code, 409)
        self.assertEqual(self.accept(recovered)["run"]["status"], "passed")

    def test_archive_is_reversible_without_deleting_history(self):
        project = self.freeze(self.create())
        archived = self.data(
            self.client.patch(
                self.url(project),
                json={"archived": True, "revision": project["revision"]},
                headers=self.headers,
            )
        )["project"]
        self.assertEqual(self.data(self.client.get(BASE + "/projects"))["projects"], [])
        self.assertEqual(
            len(self.data(self.client.get(BASE + "/projects?archived=1"))["projects"]), 1
        )
        self.assertEqual(self.load(project)["contract"]["id"], project["contract"]["id"])
        restored = self.data(
            self.client.patch(
                self.url(project),
                json={"archived": False, "revision": archived["revision"]},
                headers=self.headers,
            )
        )["project"]
        self.assertFalse(restored["archived"])
        self.assertEqual(len(self.data(self.client.get(BASE + "/projects"))["projects"]), 1)

    def test_change_preserves_old_contract_and_requires_fresh_acceptance(self):
        project = self.freeze(self.create())
        change = next(
            item
            for item in self.scenario["changes"]
            if {**self.rules, **item["patch"]} != self.rules
        )
        self.assertEqual(
            self.client.post(
                self.url(project, "/changes"),
                json={"change_id": change["id"], "revision": project["revision"]},
                headers=self.headers,
            ).status_code,
            409,
        )
        original_contract = project["contract"]
        self.accept(project)
        project = self.data(self.deliver(self.load(project)))["project"]
        changed = self.data(
            self.client.post(
                self.url(project, "/changes"),
                json={"change_id": change["id"], "revision": project["revision"]},
                headers=self.headers,
            )
        )["project"]
        self.assertEqual(changed["state"], "development")
        self.assertIsNone(changed["delivery"])
        self.assertEqual(changed["contract"]["version"], 2)
        self.assertNotEqual(changed["contract"]["id"], original_contract["id"])
        self.assertEqual(changed["contracts"][0], original_contract)
        self.assertEqual(changed["contract"]["rules"], {**self.rules, **change["patch"]})
        self.assertEqual(self.deliver(changed).status_code, 409)
        self.assertEqual(
            self.client.post(
                self.url(changed, "/run"),
                json={
                    "kind": "acceptance",
                    "code": changed["code"],
                    "contract_id": original_contract["id"],
                },
                headers=self.headers,
            ).status_code,
            409,
        )
        self.accept(changed)
        delivered = self.data(self.deliver(self.load(changed)))["project"]
        self.assertEqual(delivered["delivery"]["contract_id"], changed["contract"]["id"])
        self.assertEqual(
            self.client.post(
                self.url(delivered, "/changes"),
                json={"change_id": change["id"], "revision": delivered["revision"]},
                headers=self.headers,
            ).status_code,
            409,
        )

    def test_custom_run_and_malformed_runner_output_cannot_authorize_delivery(self):
        project = self.freeze(self.create())
        sample = project["contract"]["cases"][0]
        self.runner.side_effect = None
        self.runner.return_value = {
            **self.execution(project),
            "output": json.dumps(
                {"results": [{"index": 0, "actual": sample["expected"], "error": None}]}
            ),
        }
        data = self.data(
            self.client.post(
                self.url(project, "/run"),
                json={
                    "kind": "custom",
                    "code": project["code"],
                    "contract_id": project["contract"]["id"],
                    "input": sample["input"],
                },
                headers=self.headers,
            )
        )
        self.assertEqual(data["run"]["status"], "passed")
        self.assertEqual(self.deliver(self.load(project)).status_code, 409)
        self.runner.return_value = {**self.execution(project), "output": '{"results": []}'}
        result = self.data(
            self.client.post(
                self.url(project, "/run"),
                json={
                    "kind": "acceptance",
                    "code": project["code"],
                    "contract_id": project["contract"]["id"],
                },
                headers=self.headers,
            )
        )
        self.assertEqual(result["run"]["status"], "error")
        self.assertEqual(self.deliver(self.load(project)).status_code, 409)

    def test_export_contains_contract_source_and_real_evidence(self):
        project = self.freeze(self.create())
        self.accept(project)
        response = self.client.get(self.url(project, "/export"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/zip", response.content_type)
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            names = archive.namelist()
            self.assertTrue(any(name.endswith(".py") for name in names))
            self.assertTrue(any(name.endswith(".json") for name in names))
            self.assertTrue(any(name.endswith(".md") for name in names))
            content = "\n".join(archive.read(name).decode("utf-8") for name in names)
            self.assertIn(project["contract"]["id"], content)
            self.assertIn(project["code"].splitlines()[0], content)
            self.assertNotIn("SILICONFLOW_API_KEY", content)
            self.assertNotIn("password_hash", content)

    def test_disabled_languages_cannot_create_projects(self):
        with patch("config.SUPPORTED_LANGUAGES", {"python"}):
            catalog = self.data(self.client.get(BASE + "/catalog"))
            self.assertEqual([row["id"] for row in catalog["languages"]], ["python"])
            for language in ("cpp", "java", "Java17"):
                response = self.client.post(
                    BASE + "/projects",
                    json={
                        "scenario_id": self.scenario["id"],
                        "language": language,
                    },
                    headers=self.headers,
                )
                self.assertEqual(response.status_code, 400)

    def test_all_tasks_offer_two_languages_with_separate_projects(self):
        from modules.task_room.languages import validate_solution

        catalog = self.data(self.client.get(BASE + "/catalog"))
        self.assertEqual({x["id"] for x in catalog["languages"]}, {"python", "cpp"})
        projects = []
        for language in ("python", "cpp"):
            for scenario in catalog["scenarios"]:
                _MEMORY_BUCKETS.clear()
                project = self.data(
                    self.client.post(
                        BASE + "/projects",
                        json={"scenario_id": scenario["id"], "language": language},
                        headers=self.headers,
                    ),
                    201,
                )["project"]
                self.assertEqual(project["language"], language)
                validate_solution(project["code"], language)
                self.assertIn("solve", project["language_guide"])
                projects.append(project)
        self.assertEqual(len({p["id"] for p in projects}), len(projects))
        python = next(p for p in projects if p["language"] == "python")
        saved = self.save(python, "def solve(data):\n    return {'keep': 'my Python draft'}\n")
        cpp = next(p for p in projects if p["language"] == "cpp")
        self.save(cpp, "Json solve(const Json& data) { return Json::object(); }")
        self.assertEqual(self.load(python)["code"], saved["code"])
        self.assertEqual(
            self.client.patch(
                self.url(python), json={"language": "cpp"}, headers=self.headers
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.post(
                BASE + "/projects",
                json={"scenario_id": self.scenario["id"], "language": "rust"},
                headers=self.headers,
            ).status_code,
            400,
        )

    def test_multilang_ai_candidates_exports_and_run_snapshots_are_language_bound(self):
        for language, source, filename, driver in (
            (
                "cpp",
                "Json solve(const Json& data) { return Json::object(); }",
                "solution.cpp",
                "main.cpp",
            ),
        ):
            with self.subTest(language=language):
                project = self.data(
                    self.client.post(
                        BASE + "/projects",
                        json={"scenario_id": self.scenario["id"], "language": language},
                        headers=self.headers,
                    ),
                    201,
                )["project"]
                project = self.freeze(project)
                self.assertEqual(project["contract"]["language"], language)
                self.ai.return_value = json.dumps({"reply": "待运行的候选", "code": source})
                self.data(self.message(project, "coach"))
                candidate = next(
                    m for m in reversed(self.load(project)["messages"]) if m["role"] == "assistant"
                )
                self.assertEqual(candidate["payload"]["language"], language)
                context = json.loads(
                    self.ai.call_args.args[0]["messages"][1]["content"].split("\n用户请求：")[0]
                )
                self.assertEqual(context["language"], language)
                project = self.save(project, source)
                accepted = self.accept(project)
                self.assertEqual(accepted["run"]["language"], language)
                self.assertEqual(self.runner.call_args.args[1], language)
                self.assertEqual(
                    len(json.loads(self.runner.call_args.kwargs["input_text"])),
                    len(project["contract"]["cases"]),
                )
                self.assertNotIn('"expected"', self.runner.call_args.kwargs["input_text"])
                response = self.client.get(self.url(project, "/export"))
                with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
                    self.assertIn(filename, archive.namelist())
                    self.assertIn(driver, archive.namelist())
                    self.assertNotIn("solution.py", archive.namelist())
                    self.assertEqual(archive.read(filename).decode("utf-8"), source)
                    self.assertIn("inputs.json", archive.read("README.md").decode("utf-8"))
                self.ai.return_value = json.dumps(
                    {"reply": "wrong language", "code": "def solve(data):\n    return {}\n"}
                )
                self.assertEqual(self.message(project, "coach").status_code, 503)

    def test_mismatched_language_evidence_cannot_authorize_delivery(self):
        project = self.freeze(self.create())
        accepted = self.accept(project)
        with app.app_context():
            run = db.session.get(TaskRun, accepted["run"]["id"])
            run.language = "cpp"
            db.session.commit()
        self.assertEqual(self.deliver(self.load(project)).status_code, 409)


if __name__ == "__main__":
    unittest.main()

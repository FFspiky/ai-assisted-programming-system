"""Taxonomy, import preservation, filtering and ownership in an isolated database."""

import io
import os
import unittest
from collections import Counter

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["FLASK_SECRET_KEY"] = "library-test-secret"
os.environ["AUTO_CREATE_DATABASE"] = "0"

from app import app
from models import Problem, Submission, TestCase, User, db
from services.problem_library import load_library, seed_library
from services.rate_limiter import _MEMORY_BUCKETS


class ProblemLibraryTest(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        _MEMORY_BUCKETS.clear()
        self.client = app.test_client()
        with app.app_context():
            db.drop_all()
            db.create_all()
            seed_library()

    def login(self, username="student", admin=False):
        with app.app_context():
            user = User(username=username, email=username + "@example.test", is_admin=admin)
            user.set_password("test-password")
            db.session.add(user)
            db.session.commit()
            uid = user.id
        result = self.client.post(
            "/api/login", json={"username": username, "password": "test-password"}
        )
        self.assertEqual(result.status_code, 200)
        return uid, {"X-CSRF-Token": result.json["csrf_token"]}

    def test_catalog_shape_and_idempotence(self):
        records = load_library()
        self.assertEqual(len(records), 60)
        self.assertEqual(set(Counter(p["category"] for p in records).values()), {6})
        self.assertEqual(
            Counter(p["difficulty"] for p in records), {"简单": 30, "中等": 24, "困难": 6}
        )
        self.assertEqual(len({p["title"] for p in records}), 60)
        self.assertTrue(all(sum(c["public"] for c in p["cases"]) == 2 for p in records))
        with app.app_context():
            problem = db.session.get(Problem, records[0]["id"])
            problem.title = "管理员已修改"
            db.session.commit()
            result = seed_library()
            self.assertEqual(len(result["skipped"]), 60)
            self.assertEqual(problem.title, "管理员已修改")
            self.assertEqual(TestCase.query.count(), 360)

    def test_filters_pagination_and_no_solution_leak(self):
        data = self.client.get("/api/problems?page=1").json["data"]
        self.assertEqual(data["total"], 60)
        self.assertEqual(data["pages"], 5)
        self.assertEqual(len(data["problems"]), 12)
        result = self.client.get("/api/problems?category=search&difficulty=困难&page=99").json[
            "data"
        ]
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["page"], 1)
        self.assertEqual(result["problems"][0]["id"], "CL-SEARCH-06")
        self.assertEqual(self.client.get("/api/problems?q=CL-STRINGS").json["data"]["total"], 6)
        self.assertEqual(self.client.get("/api/problems?q=不存在").json["data"]["total"], 0)
        for url in [
            "/api/problems?category=bad",
            "/api/problems?page=no",
            "/api/problems?state=bad",
        ]:
            self.assertEqual(self.client.get(url).status_code, 400)
        self.assertEqual(self.client.get("/api/problems?state=accepted").status_code, 401)
        detail = self.client.get("/api/problems/CL-BASICS-01").json["problem"]
        self.assertNotIn("cases", detail)
        self.assertNotIn("reference_python", detail)
        self.assertNotIn("test_cases", detail)
        self.assertEqual(detail["category"], "basics")

    def test_status_filters_are_personal(self):
        uid, _ = self.login()
        with app.app_context():
            other = User(username="other", email="other@example.test")
            other.set_password("test-password")
            db.session.add(other)
            db.session.flush()
            for owner, pid, status in [
                (uid, "CL-BASICS-01", "Accepted"),
                (uid, "CL-BASICS-02", "Wrong Answer"),
                (other.id, "CL-BASICS-03", "Accepted"),
            ]:
                db.session.add(
                    Submission(
                        user_id=owner,
                        problem_id=pid,
                        code_submitted="print(1)",
                        language="python",
                        status=status,
                    )
                )
            db.session.commit()
        for state, ids in [("accepted", ["CL-BASICS-01"]), ("attempted", ["CL-BASICS-02"])]:
            data = self.client.get("/api/problems?state=" + state).json["data"]
            self.assertEqual(data["ids"], ids)
        data = self.client.get("/api/problems?state=unattempted").json["data"]
        self.assertEqual(data["total"], 58)
        self.assertIn("CL-BASICS-03", data["ids"])

    def test_admin_metadata_edit_and_import_validation(self):
        _, headers = self.login("admin", True)
        data = self.client.get("/api/admin/problems").json["data"]["problems"][0]
        payload = {
            k: data[k] for k in ["title", "description", "difficulty", "judge_mode", "test_cases"]
        }
        payload.update(category="dp", tags=["状态转移", "状态转移"], source="自编题")
        result = self.client.put("/api/admin/problems/" + data["id"], json=payload, headers=headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["problem"]["tags"], ["状态转移"])
        payload["test_cases"][0]["input_data"] = "\n"
        result = self.client.put("/api/admin/problems/" + data["id"], json=payload, headers=headers)
        self.assertEqual(result.json["problem"]["test_cases"][0]["input_data"], "\n")
        payload["category"] = "invalid"
        self.assertEqual(
            self.client.put(
                "/api/admin/problems/" + data["id"], json=payload, headers=headers
            ).status_code,
            400,
        )
        html = '<div class="problem-item"><h2 data-id="IMPORT-1">导入分类题</h2><div class="category">strings</div><div class="tags">字符串,索引</div><div class="source">测试自编</div><div class="description"><p>输出ok</p></div><div class="test-case"><pre class="input">1</pre><pre class="output">ok</pre></div></div>'
        result = self.client.post(
            "/api/admin/problems/upload",
            data={"file": (io.BytesIO(html.encode()), "test.html")},
            headers=headers,
        )
        self.assertEqual(result.json["data"]["imported_count"], 1)
        self.assertEqual(
            self.client.get("/api/problems/IMPORT-1").json["problem"]["category"], "strings"
        )


if __name__ == "__main__":
    unittest.main()

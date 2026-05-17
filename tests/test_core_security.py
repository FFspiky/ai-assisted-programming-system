import os
import tempfile
import unittest

db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
db_file.close()
os.environ["DATABASE_URL"] = "sqlite:///" + db_file.name
os.environ["FLASK_SECRET_KEY"] = "test-secret"

from app import app
from models import Problem, TestCase, User, db
from routes.guards import _RATE_BUCKETS
from services.ai_code_checker import parse_ai_code_response
from services.execute_runner import run_code
from services.judge import outputs_match


class CoreSecurityTest(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(db_file.name)
        except OSError:
            pass

    def setUp(self):
        _RATE_BUCKETS.clear()
        app.config["TESTING"] = True
        self.client = app.test_client()
        with app.app_context():
            db.drop_all()
            db.create_all()

    def test_register_requires_strong_password(self):
        response = self.client.post(
            "/api/register",
            json={"username": "alice", "email": "alice@example.com", "password": "123456"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("密码长度", response.get_json()["error"])

    def test_login_returns_current_user_payload(self):
        self.client.post(
            "/api/register",
            json={
                "username": "loginuser",
                "email": "loginuser@example.com",
                "password": "strongpass",
            },
        )

        login_response = self.client.post(
            "/api/login",
            json={"username": "loginuser", "password": "strongpass"},
        )
        current_user_response = self.client.get("/api/current_user")

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(current_user_response.status_code, 200)
        self.assertEqual(current_user_response.get_json()["user"]["username"], "loginuser")

    def test_run_code_requires_login(self):
        response = self.client.post(
            "/api/run-code",
            json={"language": "Python", "code": "print('hello')"},
        )

        self.assertEqual(response.status_code, 401)

    def test_python_runner_executes_basic_code(self):
        result = run_code("print('hello')", "Python")

        self.assertTrue(result["success"])
        self.assertEqual(result["output"].strip(), "hello")

    def test_repeated_accept_does_not_add_points_twice(self):
        with app.app_context():
            problem = Problem(
                id="p1",
                title="Echo",
                description="Print the input",
                difficulty="简单",
            )
            db.session.add(problem)
            db.session.add(TestCase(input_data="hello\n", expected_output="hello", problem_id="p1"))
            db.session.commit()

        self.client.post(
            "/api/register",
            json={
                "username": "coder",
                "email": "coder@example.com",
                "password": "strongpass",
            },
        )
        self.client.post(
            "/api/login",
            json={"username": "coder", "password": "strongpass"},
        )

        payload = {
            "problem_id": "p1",
            "language": "Python",
            "code": "print(input())",
        }
        first = self.client.post("/api/check-solution", json=payload)
        second = self.client.post("/api/check-solution", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        with app.app_context():
            user = User.query.filter_by(username="coder").first()
            self.assertEqual(user.points, 10)

    def test_judge_ignores_trailing_line_whitespace(self):
        self.assertTrue(outputs_match("hello  \nworld\t\n", "hello\nworld"))

    def test_judge_accepts_float_tolerance(self):
        self.assertTrue(outputs_match("3.1415927 2.0000001", "3.1415926 2.0000000"))

    def test_solution_checker_accepts_whitespace_tolerant_output(self):
        with app.app_context():
            db.session.add(Problem(id="p-space", title="Space", description="Space", difficulty="简单"))
            db.session.add(TestCase(input_data="", expected_output="hello\nworld", problem_id="p-space"))
            db.session.commit()

        self.client.post(
            "/api/register",
            json={
                "username": "spaceuser",
                "email": "spaceuser@example.com",
                "password": "strongpass",
            },
        )
        self.client.post("/api/login", json={"username": "spaceuser", "password": "strongpass"})

        response = self.client.post(
            "/api/check-solution",
            json={
                "problem_id": "p-space",
                "language": "python",
                "code": "print('hello  '); print('world\\t')",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "Accepted")

    def test_solution_checker_reports_compile_error(self):
        with app.app_context():
            db.session.add(Problem(id="p-compile", title="Compile", description="Compile", difficulty="简单"))
            db.session.add(TestCase(input_data="", expected_output="ok", problem_id="p-compile"))
            db.session.commit()

        self.client.post(
            "/api/register",
            json={
                "username": "compileuser",
                "email": "compileuser@example.com",
                "password": "strongpass",
            },
        )
        self.client.post("/api/login", json={"username": "compileuser", "password": "strongpass"})

        response = self.client.post(
            "/api/check-solution",
            json={
                "problem_id": "p-compile",
                "language": "cpp",
                "code": "int main() { syntax error }",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "Compile Error")

    def test_learning_overview_counts_submissions(self):
        with app.app_context():
            db.session.add(Problem(id="p2", title="Echo 2", description="Echo", difficulty="简单"))
            db.session.add(TestCase(input_data="hello\n", expected_output="hello", problem_id="p2"))
            db.session.commit()

        self.client.post(
            "/api/register",
            json={
                "username": "overview",
                "email": "overview@example.com",
                "password": "strongpass",
            },
        )
        self.client.post("/api/login", json={"username": "overview", "password": "strongpass"})
        self.client.post(
            "/api/check-solution",
            json={"problem_id": "p2", "language": "python", "code": "print(input())"},
        )

        response = self.client.get("/api/learning_overview")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["total_solved"], 1)
        self.assertEqual(response.get_json()["data"]["accuracy"], 100)

    def test_leaderboard_returns_public_rankings(self):
        self.client.post(
            "/api/register",
            json={
                "username": "ranked",
                "email": "ranked@example.com",
                "password": "strongpass",
            },
        )

        response = self.client.get("/api/leaderboard")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        self.assertEqual(response.get_json()["data"][0]["username"], "ranked")

    def test_ai_code_response_prefers_structured_json(self):
        parsed = parse_ai_code_response(
            """
            {
              "feedback": "整体不错",
              "optimizedVersions": [
                {"description": "更清晰", "code": "print('ok')"}
              ]
            }
            """
        )

        self.assertTrue(parsed["success"])
        self.assertEqual(parsed["feedback"], "整体不错")
        self.assertEqual(parsed["optimizedVersions"][0]["code"], "print('ok')")

    def test_ai_code_response_falls_back_to_markdown_code_blocks(self):
        parsed = parse_ai_code_response(
            "#### 版本1：直接输出\n```python\nprint('ok')\n```"
        )

        self.assertTrue(parsed["success"])
        self.assertEqual(parsed["optimizedVersions"][0]["code"], "print('ok')")

    def test_ai_optimize_reports_missing_api_key(self):
        self.client.post(
            "/api/register",
            json={
                "username": "aiuser",
                "email": "aiuser@example.com",
                "password": "strongpass",
            },
        )
        self.client.post("/api/login", json={"username": "aiuser", "password": "strongpass"})

        response = self.client.post(
            "/api/optimize-code",
            json={"language": "python", "code": "print('hello')"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["success"])
        self.assertIn("SILICONFLOW_API_KEY", response.get_json()["error"])

    def test_run_code_is_rate_limited(self):
        self.client.post(
            "/api/register",
            json={
                "username": "runner",
                "email": "runner@example.com",
                "password": "strongpass",
            },
        )
        self.client.post(
            "/api/login",
            json={"username": "runner", "password": "strongpass"},
        )

        payload = {"language": "Python", "code": "print('ok')"}
        last_response = None
        for _ in range(21):
            last_response = self.client.post("/api/run-code", json=payload)

        self.assertEqual(last_response.status_code, 429)

    def test_run_code_rejects_unsupported_language(self):
        self.client.post(
            "/api/register",
            json={
                "username": "languser",
                "email": "languser@example.com",
                "password": "strongpass",
            },
        )
        self.client.post(
            "/api/login",
            json={"username": "languser", "password": "strongpass"},
        )

        response = self.client.post(
            "/api/run-code",
            json={"language": "javascript", "code": "console.log('bad')"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("不支持的语言", response.get_json()["error"])

    def test_run_code_rejects_large_payload(self):
        self.client.post(
            "/api/register",
            json={
                "username": "largeuser",
                "email": "largeuser@example.com",
                "password": "strongpass",
            },
        )
        self.client.post(
            "/api/login",
            json={"username": "largeuser", "password": "strongpass"},
        )

        response = self.client.post(
            "/api/run-code",
            json={"language": "python", "code": "x" * 20001},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("代码长度", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()

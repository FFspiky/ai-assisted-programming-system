import os
import tempfile
import unittest

db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
db_file.close()
os.environ["DATABASE_URL"] = "sqlite:///" + db_file.name
os.environ["FLASK_SECRET_KEY"] = "test-secret"

from app import app
from models import Problem, TestCase, User, db
from services.ai_code_checker import parse_ai_code_response
from services.execute_runner import run_code


class CoreSecurityTest(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(db_file.name)
        except OSError:
            pass

    def setUp(self):
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


if __name__ == "__main__":
    unittest.main()

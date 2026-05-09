import os
import tempfile
import unittest

os.environ["DATABASE_URL"] = "sqlite:///" + tempfile.NamedTemporaryFile(suffix=".db").name
os.environ["FLASK_SECRET_KEY"] = "test-secret"

from app import app
from models import db
from services.execute_runner import run_code


class CoreSecurityTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

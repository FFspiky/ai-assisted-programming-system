"""Isolated credential, access-control and provider-routing regression checks."""

import os
import unittest
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["FLASK_SECRET_KEY"] = "settings-test-secret"

from app import app
from models import User, UserAISettings, db
from services.ai_client import chat_completion, stream_chat_events
from services.ai_settings import resolve_key
from services.rate_limiter import _MEMORY_BUCKETS


class AISettingsTest(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        _MEMORY_BUCKETS.clear()
        with app.app_context():
            db.drop_all()
            db.create_all()
            for name in ("alice", "bob"):
                user = User(username=name, email=f"{name}@example.com")
                user.set_password("password123")
                db.session.add(user)
            db.session.commit()
        self.client = app.test_client()
        self.login("alice")

    def login(self, name):
        self.client = app.test_client()
        self.assertEqual(
            self.client.post(
                "/api/login", json={"username": name, "password": "password123"}
            ).status_code,
            200,
        )
        self.headers = {"X-CSRF-Token": self.client.get("/api/csrf-token").json["csrf_token"]}

    def save(self, mode, key=""):
        return self.client.put(
            "/api/profile/ai-settings", json={"mode": mode, "api_key": key}, headers=self.headers
        )

    def test_auth_and_csrf(self):
        self.assertEqual(app.test_client().get("/api/profile/ai-settings").status_code, 401)
        self.assertEqual(
            self.client.put("/api/profile/ai-settings", json={"mode": "test"}).status_code, 403
        )

    def test_all_ai_routes_require_explicit_configuration(self):
        for path in (
            "/api/ai-chat-stream",
            "/api/optimize-code",
            "/api/ai-inline-complete-stream",
            "/api/assess-learning-path",
            "/api/submissions/1/help",
            "/api/submissions/1/diagnosis",
            "/api/co-create/sessions/example/generate",
            "/api/co-create/sessions/example/review-generate",
            "/api/task-room/projects/example/messages",
        ):
            with self.subTest(path=path):
                response = self.client.post(path, json={}, headers=self.headers)
                self.assertEqual(response.status_code, 428)
                self.assertEqual(response.json["error"]["code"], "AI_KEY_REQUIRED")
        self.assertEqual(self.client.get("/api/ai_learning_analysis_stream").status_code, 428)
        self.assertEqual(self.client.get("/api/problems").status_code, 200)

    def test_encryption_no_echo_isolation_and_clear(self):
        key = "sk-private-alice-123456789"
        response = self.save("custom", key)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(key, response.text)
        self.assertTrue(response.json["data"]["configured"])
        with app.app_context():
            row = db.session.get(UserAISettings, 1)
            self.assertNotIn(key.encode(), row.encrypted_key)
            self.assertEqual(resolve_key(1), key)
            self.assertEqual(resolve_key(2), "")
        self.login("bob")
        self.assertFalse(self.client.get("/api/profile/ai-settings").json["data"]["configured"])
        self.login("alice")
        self.assertTrue(self.save("custom").json["data"]["configured"])
        self.assertFalse(self.save("none").json["data"]["configured"])
        with app.app_context():
            self.assertIsNone(db.session.get(UserAISettings, 1).encrypted_key)

    def test_test_key_availability_and_validation(self):
        with patch("services.ai_client.API_KEY", ""):
            self.assertEqual(self.save("test").status_code, 409)
        with patch("services.ai_client.API_KEY", "server-test-key"):
            self.assertEqual(self.save("test").status_code, 200)
            with app.app_context():
                self.assertEqual(resolve_key(1), "server-test-key")
        for key in ("short", "key with spaces", "sk-abc\r\nX-Header: secret", 123):
            self.assertEqual(self.save("custom", key).status_code, 400)

    def test_provider_receives_current_user_key_for_sync_and_stream(self):
        self.save("custom", "sk-account-specific")
        response = MagicMock()
        response.__enter__.return_value = response
        response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        response.iter_lines.return_value = [
            b'data: {"choices":[{"delta":{"content":"ok"}}]}',
            b"data: [DONE]",
        ]
        with app.test_request_context():
            from flask_login import login_user

            login_user(db.session.get(User, 1))
            with patch("services.ai_client.requests.post", return_value=response) as post:
                self.assertEqual(chat_completion({"model": "test"}), "ok")
                self.assertEqual(list(stream_chat_events({"model": "test"}))[0]["text"], "ok")
                for call in post.call_args_list:
                    self.assertEqual(call.args[0], "https://api.deepseek.com/chat/completions")
                    self.assertIn("thinking", call.kwargs["json"])
                    self.assertNotIn("enable_thinking", call.kwargs["json"])
                    self.assertEqual(
                        call.kwargs["headers"]["Authorization"], "Bearer sk-account-specific"
                    )

    def test_catalog_and_teaching_example_remain_available(self):
        self.assertFalse(self.client.get("/api/co-create/catalog").json["data"]["ai_available"])
        response = self.client.post(
            "/api/co-create/sessions/missing/generate",
            json={"source": "teaching"},
            headers=self.headers,
        )
        self.assertNotEqual(response.status_code, 428)

    def test_stream_uses_request_key_after_user_session_teardown(self):
        self.save("custom", "sk-stream-session-test")
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_lines.return_value = [
            b'data: {"choices":[{"delta":{"content":"ok"}}]}',
            b"data: [DONE]",
        ]
        with app.test_request_context("/api/ai_learning_analysis_stream"):
            from flask_login import login_user

            login_user(db.session.get(User, 1))
            self.assertIsNone(app.preprocess_request())
            db.session.expire_all()
            db.session.remove()
            with patch("services.ai_client.requests.post", return_value=response) as post:
                self.assertEqual(list(stream_chat_events({"model": "test"}))[0]["text"], "ok")
                self.assertEqual(
                    post.call_args.kwargs["headers"]["Authorization"],
                    "Bearer sk-stream-session-test",
                )


if __name__ == "__main__":
    unittest.main()

"""Dedicated reviewer balance checks never make paid calls in these tests."""

import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

import requests
from flask import Flask

from services import ai_client
from services import reviewer_access as reviewer


class ReviewerAccessTest(unittest.TestCase):
    def setUp(self):
        self.key = "sk-fake-reviewer-unit-test"
        for target, value in (
            ("services.ai_client.API_KEY", self.key),
            ("services.reviewer_access.REVIEWER_TEST_KEY_ENABLED", True),
        ):
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.get_patcher = patch("services.reviewer_access.requests.get")
        self.get = self.get_patcher.start()
        self.addCleanup(self.get_patcher.stop)
        self.response = self.get.return_value.__enter__.return_value
        self.response.status_code = 200
        self.response.json.return_value = {
            "is_available": True,
            "balance_infos": [{"currency": "CNY", "total_balance": "9.99"}],
        }
        self.post_patcher = patch("services.ai_client.requests.post")
        self.post = self.post_patcher.start()
        self.addCleanup(self.post_patcher.stop)
        result = self.post.return_value.__enter__.return_value
        result.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        result.iter_lines.return_value = [
            b'data: {"choices":[{"delta":{"content":"ok"}}]}',
            b"data: [DONE]",
        ]

    def test_balance_is_official_read_only_request(self):
        self.assertEqual(reviewer.check_balance(self.key), Decimal("9.99"))
        args = self.get.call_args
        self.assertEqual(args.args[0], "https://api.deepseek.com/user/balance")
        self.assertFalse(args.kwargs["allow_redirects"])
        self.assertEqual(args.kwargs["headers"]["Authorization"], f"Bearer {self.key}")
        self.post.assert_not_called()

    def test_every_sync_and_stream_call_checks_before_post(self):
        calls = MagicMock()
        calls.attach_mock(self.get, "balance")
        calls.attach_mock(self.post, "model")
        self.assertEqual(ai_client.chat_completion({}), "ok")
        self.assertEqual(list(ai_client.stream_chat_events({}))[0]["text"], "ok")
        self.assertEqual(
            [c[0] for c in calls.mock_calls if c[0] in {"balance", "model"}],
            ["balance", "model", "balance", "model"],
        )

    def test_exhausted_unavailable_or_invalid_balance_never_calls_model(self):
        for packet in (
            {"is_available": False},
            {"is_available": True, "balance_infos": [{"currency": "CNY", "total_balance": "0"}]},
            {
                "is_available": True,
                "balance_infos": [{"currency": "CNY", "total_balance": "-0.01"}],
            },
            {"is_available": True, "balance_infos": [{"currency": "CNY", "total_balance": "NaN"}]},
            {"is_available": True, "balance_infos": [{"currency": "USD", "total_balance": "10"}]},
            {"is_available": "true", "balance_infos": []},
            [],
        ):
            self.response.json.return_value = packet
            for invoke in (
                lambda: ai_client.chat_completion({}),
                lambda: list(ai_client.stream_chat_events({})),
            ):
                with self.subTest(packet=packet), self.assertRaises(ai_client.AIClientError):
                    invoke()
        self.post.assert_not_called()

    def test_network_failure_is_not_reported_as_debt_and_does_not_echo_key(self):
        self.get.side_effect = requests.Timeout(self.key)
        with self.assertRaises(ai_client.AIClientError) as error:
            ai_client.chat_completion({})
        self.assertIn("网络", str(error.exception))
        self.assertNotIn("余额不足", str(error.exception))
        self.assertNotIn(self.key, str(error.exception))
        self.post.assert_not_called()

    def test_status_codes_are_distinguished(self):
        for status, code in (
            (401, "REVIEWER_KEY_INVALID"),
            (402, "REVIEWER_BALANCE_EXHAUSTED"),
            (429, "REVIEWER_RATE_LIMIT"),
            (503, "REVIEWER_BALANCE_UNAVAILABLE"),
        ):
            self.response.status_code = status
            with (
                self.subTest(status=status),
                self.assertRaises(reviewer.ReviewerAccessError) as error,
            ):
                reviewer.check_balance(self.key)
            self.assertEqual(error.exception.code, code)

    def test_personal_key_and_regular_server_mode_bypass_reviewer_check(self):
        with patch.object(ai_client, "ensure_ai_configured", return_value="sk-personal"):
            ai_client.chat_completion({})
            list(ai_client.stream_chat_events({}))
        with patch.object(reviewer, "REVIEWER_TEST_KEY_ENABLED", False):
            ai_client.chat_completion({})
        self.get.assert_not_called()

    def test_preflight_is_consumed_once_and_next_model_call_checks_again(self):
        with (
            Flask(__name__).test_request_context(),
            patch.object(ai_client, "ensure_ai_configured", return_value=self.key),
        ):
            reviewer.preflight(self.key)
            ai_client.chat_completion({})
            self.assertEqual(self.get.call_count, 1)
            list(ai_client.stream_chat_events({}))
            self.assertEqual(self.get.call_count, 2)

    def test_balance_depleted_between_check_and_model_returns_actionable_error(self):
        response = requests.Response()
        response.status_code = 402
        self.post.return_value.__enter__.return_value.raise_for_status.side_effect = (
            requests.HTTPError(response=response)
        )
        with self.assertRaises(ai_client.AIClientError) as error:
            ai_client.chat_completion({})
        self.assertIn("自己的 DeepSeek Key", str(error.exception))


if __name__ == "__main__":
    unittest.main()

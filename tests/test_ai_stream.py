import json
import unittest
from unittest.mock import MagicMock, patch

from services.ai_client import (
    AIClientError,
    _provider_payload,
    stream_chat_deltas,
    stream_chat_events,
)
from services.ai_helper import stream_code_from_prompt


class AIStreamTest(unittest.TestCase):
    def mock_response(self, packets):
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_lines.return_value = iter(packets)
        return response

    def test_reasoning_and_answer_are_separate_with_nulls_and_usage(self):
        packets = [
            b": keepalive",
            b'data: {"choices":[{"delta":{"content":null,"reasoning_content":"step"}}]}',
            b'data:{"choices":[{"delta":{"content":"answer","reasoning_content":null}}]}',
            b'data: {"choices":[],"usage":{"total_tokens":12}}',
            b"data: [DONE]",
        ]
        with (
            patch("services.ai_client.API_KEY", "test-key"),
            patch(
                "services.ai_client.requests.post", return_value=self.mock_response(packets)
            ) as post,
        ):
            self.assertEqual(
                list(stream_chat_events({"model": "test"})),
                [{"type": "reasoning", "text": "step"}, {"type": "content", "text": "answer"}],
            )
            self.assertTrue(post.call_args.kwargs["stream"])
        with patch(
            "services.ai_client.stream_chat_events",
            return_value=iter(
                [{"type": "reasoning", "text": "step"}, {"type": "content", "text": "answer"}]
            ),
        ):
            self.assertEqual(list(stream_chat_deltas({})), ["answer"])

    def test_chat_enables_thinking_but_completion_can_disable_it(self):
        with patch("services.ai_client.API_URL", "https://api.deepseek.com/chat/completions"):
            self.assertEqual(
                _provider_payload({"enable_thinking": True})["thinking"], {"type": "enabled"}
            )
            completion = _provider_payload({"enable_thinking": False})
            self.assertEqual(completion["thinking"], {"type": "disabled"})
            self.assertNotIn("enable_thinking", completion)
        event = {"type": "reasoning", "text": "分析"}
        with patch("services.ai_helper.stream_chat_events", return_value=iter([event])) as call:
            self.assertEqual(
                list(stream_code_from_prompt("问题", "python", structured=True)), [event]
            )
            self.assertTrue(call.call_args.args[0]["enable_thinking"])
            self.assertIn("达菲郁", call.call_args.args[0]["messages"][0]["content"])

    def test_provider_failure_is_a_structured_error(self):
        with patch("services.ai_helper.stream_chat_events", side_effect=AIClientError("超时")):
            self.assertEqual(
                list(stream_code_from_prompt("问题", "python", structured=True)),
                [{"type": "error", "text": "超时"}],
            )
        packets = [b"data: " + json.dumps({"error": {"message": "failed"}}).encode()]
        with (
            patch("services.ai_client.API_KEY", "test-key"),
            patch("services.ai_client.requests.post", return_value=self.mock_response(packets)),
            self.assertRaises(AIClientError),
        ):
            list(stream_chat_events({}))

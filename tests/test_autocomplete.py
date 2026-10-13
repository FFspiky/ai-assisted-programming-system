import unittest
from unittest.mock import patch

from services.ai_autocomplete import clean_completion_stream, stream_inline_completion
from services.ai_client import AIClientError


class AutocompleteTest(unittest.TestCase):
    def test_split_reasoning_and_fences_never_enter_code(self):
        chunks = ["<thi", "nk>private", "</thi", "nk>`", "``py", "thon\n    ret", "urn 1\n`", "``"]
        self.assertEqual("".join(clean_completion_stream(chunks)), "    return 1\n")

    def test_indentation_operators_and_four_line_limit(self):
        self.assertEqual("".join(clean_completion_stream(["    x ", "<", "= 3"])), "    x <= 3")
        self.assertEqual("".join(clean_completion_stream(["a\nb\nc\nd\ne\nf"])), "a\nb\nc\nd")

    def test_failure_does_not_offer_error_text_as_code(self):
        with patch(
            "services.ai_autocomplete.stream_chat_deltas", side_effect=AIClientError("failed")
        ):
            self.assertEqual(list(stream_inline_completion("print(", "", "python")), [])

    def test_completion_disables_thinking_and_uses_short_budget(self):
        with patch(
            "services.ai_autocomplete.stream_chat_deltas", return_value=iter(["1)"])
        ) as call:
            self.assertEqual(list(stream_inline_completion("print(", "", "python")), ["1)"])
        payload = call.call_args.args[0]
        self.assertFalse(payload["enable_thinking"])
        self.assertEqual(payload["max_tokens"], 96)
        self.assertEqual(call.call_args.kwargs["timeout"], 15)

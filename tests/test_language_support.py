"""Language contracts and mocked AI requests; never contact a model provider."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from routes.validators import validate_language
from services.ai_autocomplete import stream_inline_completion
from services.ai_code_checker import check_code
from services.ai_helper import stream_code_from_prompt
from services.language_support import (
    LANGUAGE_IDS,
    language_options,
    language_prompt,
    language_spec,
    normalize_language,
    starter_code,
)
from services.learning_help import generate_code_help
from services.tutor_service import diagnose_submission


class LanguageSupportTest(unittest.TestCase):
    def test_aliases_metadata_and_options_share_canonical_identity(self):
        for value, expected in (("Python3", "python"), (" C++ ", "cpp")):
            self.assertEqual(normalize_language(value), expected)
            with patch("routes.validators.SUPPORTED_LANGUAGES", set(LANGUAGE_IDS)):
                language, response, status = validate_language(value)
                self.assertEqual(language, expected)
                self.assertIsNone(response)
                self.assertIsNone(status)
        self.assertEqual(normalize_language(3), "")
        self.assertEqual([row["id"] for row in language_options()], list(LANGUAGE_IDS))
        self.assertEqual([row["id"] for row in language_options(["java", "C++"])], ["cpp"])
        spec = language_spec("cpp")
        spec["filename"] = "changed.cpp"
        self.assertEqual(language_spec("cpp")["filename"], "main.cpp")
        with self.assertRaises(ValueError):
            language_spec("java")

    def test_entrypoints_and_templates_match_runtime_contracts(self):
        self.assertIn("if __name__ == '__main__'", starter_code("python"))
        self.assertIn("int main()", starter_code("cpp"))
        for language in LANGUAGE_IDS:
            self.assertIn(language_spec(language)["version"], language_prompt(language))

    def test_completion_optimizer_and_chat_keep_selected_language(self):
        for language in LANGUAGE_IDS:
            with self.subTest(language=language):
                version = language_spec(language)["version"]
                with patch(
                    "services.ai_autocomplete.stream_chat_deltas", return_value=iter(["x"])
                ) as call:
                    self.assertEqual(list(stream_inline_completion("", "", language)), ["x"])
                    self.assertIn(version, call.call_args.args[0]["messages"][0]["content"])
                with patch(
                    "services.ai_code_checker.chat_completion",
                    return_value='{"feedback":"ok","optimizedVersions":[]}',
                ) as call:
                    self.assertTrue(check_code("test", language)["success"])
                    self.assertIn(version, call.call_args.args[0]["messages"][0]["content"])
                with patch(
                    "services.ai_helper.stream_chat_deltas", return_value=iter(["hint"])
                ) as call:
                    self.assertEqual(list(stream_code_from_prompt("help", language)), ["hint"])
                    self.assertIn(version, call.call_args.args[0]["messages"][0]["content"])

    def test_complete_learning_reference_keeps_selected_language(self):
        response = json.dumps(
            {
                "status": "supported",
                "summary": "候选待验证",
                "explanation": "仅依据代码",
                "lines": [],
                "evidence_ids": [],
                "code": "candidate",
            }
        )
        for language in LANGUAGE_IDS:
            with (
                self.subTest(language=language),
                patch("services.learning_help.chat_completion", return_value=response) as call,
            ):
                self.assertEqual(generate_code_help("test", language, 4)["code"], "candidate")
                self.assertIn(
                    language_spec(language)["version"],
                    call.call_args.args[0]["messages"][0]["content"],
                )

    def test_submission_diagnosis_keeps_actual_submission_language(self):
        response = json.dumps(
            {"status": "insufficient_evidence", "summary": "需更多公开证据", "findings": []}
        )
        case = {
            "id": "case-1",
            "input": "1",
            "expected_output": "1",
            "actual_output": "2",
            "status": "Wrong Answer",
        }
        for language in LANGUAGE_IDS:
            submission = SimpleNamespace(
                evidence_snapshot={
                    "problem": {"title": "测试", "description": "<p>标准输入输出</p>"}
                },
                language=language,
                code_submitted="source",
                status="Wrong Answer",
            )
            with (
                self.subTest(language=language),
                patch("services.tutor_service.diagnosis_cases", return_value=[case]),
                patch("services.tutor_service.chat_completion", return_value=response) as call,
            ):
                self.assertEqual(diagnose_submission(submission)["status"], "insufficient_evidence")
                self.assertIn(
                    language_spec(language)["version"],
                    call.call_args.args[0]["messages"][0]["content"],
                )


if __name__ == "__main__":
    unittest.main()

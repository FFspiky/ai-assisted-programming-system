import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.ai_client import AIClientError
from services.tutor_service import _validate_diagnosis, diagnose_submission, safe_saved_diagnosis


def submission(cases):
    return SimpleNamespace(
        code_submitted="print(0)",
        language="python",
        status="Wrong Answer",
        diagnosis=None,
        evidence_snapshot={"problem": {"title": "测试", "description": "输出1"}, "cases": cases},
    )


class EvidenceLimitsTest(unittest.TestCase):
    def test_passed_public_and_failed_hidden_do_not_invoke_ai_or_restore_old_claim(self):
        sub = submission(
            [
                {"id": "case-1", "is_public": True, "status": "Accepted", "passed": True},
                {"id": "case-2", "is_public": False, "status": "Wrong Answer", "input": "SECRET"},
            ]
        )
        with patch("services.tutor_service.chat_completion") as ai:
            result = diagnose_submission(sub)
        ai.assert_not_called()
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["findings"], [])
        self.assertEqual(sub.status, "Wrong Answer")
        sub.diagnosis = {"summary": "old unsupported claim", "findings": [{}]}
        self.assertEqual(safe_saved_diagnosis(sub)["status"], "insufficient_evidence")

    def test_no_public_failure_and_truncated_evidence_are_not_used(self):
        for case in [
            {"status": "Not Run", "passed": False},
            {"status": "Runtime Error", "error_truncated": True},
            {"status": "Wrong Answer", "input": "x" * 2501},
            {"status": "Wrong Answer", "input": "1", "expected_output": "1"},
            {"status": "Runtime Error", "input": "1", "error": ""},
        ]:
            with patch("services.tutor_service.chat_completion") as ai:
                result = diagnose_submission(submission([{**case, "id": "c", "is_public": True}]))
            ai.assert_not_called()
            self.assertEqual(result["findings"], [])

    def test_model_can_abstain_and_normal_diagnosis_still_validates_references(self):
        sub = submission(
            [
                {
                    "id": "c",
                    "status": "Wrong Answer",
                    "is_public": True,
                    "input": "",
                    "expected_output": "1",
                    "actual_output": "0",
                }
            ]
        )
        empty = {"status": "insufficient_evidence", "summary": "无法确定", "findings": []}
        with patch("services.tutor_service.chat_completion", return_value=json.dumps(empty)):
            self.assertEqual(diagnose_submission(sub)["status"], "insufficient_evidence")
        finding = {
            "title": "检查",
            "explanation": "疑似",
            "next_check": "复测",
            "lines": [1],
            "evidence_ids": ["c"],
        }
        valid = {"summary": "检查输出", "findings": [finding]}
        self.assertEqual(_validate_diagnosis(valid, {"c"}, 1)["status"], "supported")
        with self.assertRaises(AIClientError):
            _validate_diagnosis(valid, {"other"}, 1)
        with self.assertRaises(AIClientError):
            _validate_diagnosis({**empty, "findings": [finding]}, {"c"}, 1)

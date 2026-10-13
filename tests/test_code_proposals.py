import unittest

from services.ai_client import AIClientError
from services.code_proposals import apply_edits, code_diff


class ExactEditsTest(unittest.TestCase):
    def test_preserves_untouched_lines_indentation_and_final_newline(self):
        base = "n = 3\nfor i in range(1, n):\n    print(i)\n"
        edits = [
            {
                "start_line": 2,
                "end_line": 2,
                "before": "for i in range(1, n):",
                "after": "for i in range(1, n + 1):",
            }
        ]
        candidate, _ = apply_edits(base, edits)
        self.assertEqual(candidate, base.replace("range(1, n)", "range(1, n + 1)"))
        self.assertIn("-for i in range(1, n):", code_diff(base, candidate))
        self.assertIn("+for i in range(1, n + 1):", code_diff(base, candidate))

    def test_rejects_ambiguous_wrong_overlapping_or_excessive_edits(self):
        valid = {"start_line": 1, "end_line": 1, "before": "x", "after": "y"}
        for edits in (
            None,
            [],
            [dict(valid, before="wrong")],
            [dict(valid, start_line=True)],
            [valid, valid],
            [dict(valid, end_line=3)],
            [dict(valid, after="x")],
            [dict(valid, after="y\n" * 9)],
        ):
            with self.subTest(edits=edits), self.assertRaises(AIClientError):
                apply_edits("x\nz\n", edits)

    def test_deletion_only_hint_keeps_exact_edit(self):
        from services.learning_help import validate_help

        context = {"code": "print(1)\nprint(0)\n", "requires_evidence": False}
        raw = {
            "status": "supported",
            "summary": "删除额外输出",
            "explanation": "输出应保持一致",
            "lines": [2],
            "evidence_ids": [],
            "code": "",
            "edits": [{"start_line": 2, "end_line": 2, "before": "print(0)", "after": ""}],
        }
        result = validate_help(raw, 3, context)
        self.assertEqual(apply_edits(context["code"], result["edits"])[0], "print(1)\n")

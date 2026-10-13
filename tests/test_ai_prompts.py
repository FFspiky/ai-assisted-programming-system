import json
import unittest
from unittest.mock import patch

from services.ai_code_checker import check_code
from services.ai_helper import stream_code_from_prompt
from services.learning_analysis import stream_learning_analysis
from services.learning_path_service import generate_learning_path


class PromptContextTest(unittest.TestCase):
    def test_chat_transmits_history_and_editor_without_execution_claims(self):
        history = [
            {"role": "user", "content": "上一条问题"},
            {"role": "assistant", "content": "上一条回答"},
        ]
        context = {"editor_code": "print(1)", "problem": {"title": "求和"}}
        with patch("services.ai_helper.stream_chat_deltas", return_value=iter(["建议"])) as call:
            self.assertEqual(
                list(stream_code_from_prompt("为什么", "python", context=context, history=history)),
                ["建议"],
            )
        messages = call.call_args.args[0]["messages"]
        self.assertEqual(messages[1:3], history)
        data = json.loads(messages[-1]["content"])
        self.assertEqual(data["current_context"], context)
        self.assertEqual(data["question"], "为什么")
        self.assertIn("未提供知识截止日期", messages[0]["content"])
        self.assertIn("请求模型标识", messages[0]["content"])

    def test_optimizer_keeps_empty_versions_when_no_change_is_needed(self):
        with patch(
            "services.ai_code_checker.chat_completion",
            return_value='{"feedback":"无需修改","optimizedVersions":[]}',
        ):
            result = check_code("print(1)", "python")
        self.assertTrue(result["success"])
        self.assertEqual(result["optimizedVersions"], [])

    def test_analysis_has_records_and_path_has_actual_answers(self):
        records = [{"problem_id": "p1", "status": "Accepted"}]
        with patch(
            "services.learning_analysis.stream_chat_deltas", return_value=iter(["分析"])
        ) as call:
            self.assertEqual(list(stream_learning_analysis("小林", records)), ["分析"])
        payload = call.call_args.args[0]
        self.assertEqual(json.loads(payload["messages"][1]["content"])["records"], records)
        self.assertIn("不能评价代码风格", payload["messages"][0]["content"])
        answers = [{"question": "目标", "answer": "学习Python"}]
        with patch(
            "services.learning_path_service.stream_chat_deltas", return_value=iter(["计划"])
        ) as call:
            self.assertIn("计划", "".join(generate_learning_path(answers)))
        self.assertIn("学习Python", call.call_args.args[0]["messages"][1]["content"])

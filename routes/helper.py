import json

from bs4 import BeautifulSoup
from flask import Blueprint, Response, request, stream_with_context
from flask_login import current_user, login_required

from config import MAX_CODE_CHARS
from models import LearningHelp, Problem, Submission, db
from routes.api_response import api_error, api_success
from routes.guards import rate_limit
from routes.validators import validate_ai_prompt, validate_language, validate_text_size
from services.ai_client import AIClientError
from services.ai_helper import stream_code_from_prompt
from services.learning_help import begin_help, fail_help, finish_help

generate_blueprint = Blueprint("generate", __name__)


# 新增：流式响应接口
@generate_blueprint.route("/api/ai-chat-stream", methods=["POST", "OPTIONS"])
@login_required
@rate_limit(max_calls=10, window_seconds=60)
def generate_code_stream():
    if request.method == "OPTIONS":
        return api_success({"status": "ok"}, status="ok")

    data = request.get_json(silent=True) or {}
    prompt, error_response, status = validate_ai_prompt((data.get("message") or "").strip())
    if error_response:
        return error_response, status
    language, error_response, status = validate_language(data.get("language", "python"))
    if error_response:
        return error_response, status

    if not prompt:
        return api_error("EMPTY_MESSAGE", "消息内容不能为空", 400)

    code, response, status = validate_text_size(data.get("code"), MAX_CODE_CHARS, "代码")
    if response:
        return response, status
    history = data.get("history", [])
    if not isinstance(history, list) or len(history) > 10:
        return api_error("INVALID_HISTORY", "对话历史最多保留 10 条消息", 400)
    for item in history:
        if (
            not isinstance(item, dict)
            or item.get("role") not in {"user", "assistant"}
            or not isinstance(item.get("content"), str)
            or len(item["content"]) > 8000
        ):
            return api_error("INVALID_HISTORY", "对话历史格式不正确", 400)
    history = [{"role": item["role"], "content": item["content"]} for item in history]
    context = {}
    problem_id = data.get("problem_id")
    include_context = data.get("include_context", False)
    if not isinstance(include_context, bool):
        return api_error("INVALID_CONTEXT", "附带上下文选项必须是布尔值", 400)
    if include_context:
        context["editor_code"] = code
        input_text, response, status = validate_text_size(data.get("input_text"), 8000, "当前输入")
        if response:
            return response, status
        context["custom_input"] = input_text
        if not isinstance(problem_id, str) or len(problem_id) > 50:
            return api_error("INVALID_PROBLEM", "题号格式不正确", 400)
        problem = db.session.get(Problem, problem_id)
        if problem is None:
            return api_error("PROBLEM_NOT_FOUND", "题目不存在", 404)
        context["problem"] = {
            "id": problem.id,
            "title": problem.title,
            "description": BeautifulSoup(problem.description, "html.parser").get_text()[:6000],
        }
        submission = (
            Submission.query.filter_by(
                user_id=current_user.id, problem_id=problem_id, language=language
            )
            .order_by(Submission.id.desc())
            .first()
        )
        context["latest_submission"] = None
        if submission:
            context["latest_submission"] = {
                "id": submission.id,
                "status": submission.status,
                "submitted_code": submission.code_submitted,
                "matches_editor": submission.code_submitted == code,
                "public_cases": [
                    {
                        key: (value[:2500] if isinstance(value, str) else value)
                        for key, value in case.items()
                        if key
                        in {"id", "input", "expected_output", "actual_output", "error", "status"}
                    }
                    for case in (submission.evidence_snapshot or {}).get("cases", [])
                    if case.get("is_public")
                ][:3],
            }

    sid = (
        context.get("latest_submission", {}).get("id") if context.get("latest_submission") else None
    )
    record = begin_help(
        current_user,
        "chat",
        4,
        {"question": prompt, "language": language, "context": context},
        sid,
    )

    record_id = record.id

    @stream_with_context
    def generate():
        record = db.session.get(LearningHelp, record_id)
        answer = ""
        try:
            kwargs = {"context": context, "history": history, "structured": True}
            for chunk in stream_code_from_prompt(prompt, language, **kwargs):
                event = chunk if isinstance(chunk, dict) else {"type": "content", "text": chunk}
                if event["type"] == "error":
                    raise AIClientError(event.get("text", "生成失败"))
                if event["type"] == "content":
                    answer += event.get("text", "")
                yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
            if not answer.strip():
                raise AIClientError("模型未返回回答，请重试")
            finish_help(record, {"text": answer})
            yield "data: " + json.dumps({"type": "help_record", "id": record.id}) + "\n\n"
            yield 'data: {"type": "done"}\n\n'
        except AIClientError as exc:
            if record.state == "pending":
                fail_help(record)
            yield "data: " + json.dumps(
                {"type": "error", "text": str(exc)}, ensure_ascii=False
            ) + "\n\n"
            yield 'data: {"type": "done"}\n\n'
        finally:
            if record.state == "pending":
                fail_help(record, "cancelled")

    return Response(
        generate(),
        content_type="text/event-stream; charset=utf-8",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )

from flask import Blueprint, request
from flask_login import current_user, login_required

from routes.api_response import api_error, api_success
from routes.guards import rate_limit
from routes.validators import validate_ai_prompt, validate_language
from services.ai_client import AIClientError
from services.ai_code_checker import check_code
from services.learning_help import (
    begin_help,
    fail_help,
    finish_help,
    generate_code_help,
    help_payload,
    parse_level,
)

ai_checker_blueprint = Blueprint("ai_checker", __name__)


@ai_checker_blueprint.route(
    "/api/optimize-code", methods=["POST", "OPTIONS"]
)  # 修改为 /api/optimize-code
@login_required
@rate_limit(max_calls=10, window_seconds=60)
def ai_check_code():
    if request.method == "OPTIONS":
        return api_success({"status": "ok"}, status="ok")

    data = request.get_json(silent=True) or {}
    code, error_response, status = validate_ai_prompt(data.get("code", ""))
    if error_response:
        return error_response, status
    language, error_response, status = validate_language(data.get("language", "python"))
    if error_response:
        return error_response, status

    try:
        level = (
            parse_level(data.get("help_level", 1)) if current_user.help_mode == "learning" else 4
        )
    except ValueError as exc:
        return api_error("INVALID_HELP_LEVEL", str(exc), 400)
    record = begin_help(current_user, "optimize", level, {"code": code, "language": language})
    if current_user.help_mode == "learning":
        try:
            result = generate_code_help(code, language, level)
            finish_help(record, result)
            return api_success(
                {"learning_help": help_payload(record)}, learning_help=help_payload(record)
            )
        except AIClientError as exc:
            if record.state == "pending":
                fail_help(record)
            return api_error("HELP_UNAVAILABLE", str(exc), 503)
    try:
        report = check_code(code, language)
        if not report.get("success", True):
            fail_help(record)
            message = report.get("error") or "AI代码检查失败"
            return api_error("AI_CHECK_FAILED", message, 200)
        finish_help(record, report)
        report["help_id"] = record.id
        return api_success(report, **report)
    except Exception as e:
        if record.state == "pending":
            fail_help(record)
        return api_error("AI_CHECK_FAILED", f"AI代码检查失败: {str(e)}", 500)

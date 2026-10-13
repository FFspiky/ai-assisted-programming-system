from flask import Blueprint, Response, request, stream_with_context
from flask_login import current_user, login_required

from models import LearningHelp, db
from routes.api_response import api_error, api_success
from routes.guards import rate_limit
from routes.validators import trim_autocomplete_context, validate_language
from services.ai_autocomplete import stream_inline_completion
from services.ai_client import AIClientError
from services.learning_help import begin_help, fail_help, finish_help, mode_is_current

autocomplete_blueprint = Blueprint("autocomplete", __name__)


@autocomplete_blueprint.route("/api/ai-inline-complete-stream", methods=["POST", "OPTIONS"])
@login_required
@rate_limit(max_calls=60, window_seconds=60)
def ai_inline_complete_stream():
    if request.method == "OPTIONS":
        return api_success({"status": "ok"}, status="ok")

    if current_user.help_mode == "learning":
        return api_error("LEARNING_MODE", "学习模式默认关闭自动补全；需要时请选择自由辅助", 409)
    data = request.get_json(silent=True) or {}
    prefix, suffix = trim_autocomplete_context(data.get("prefix"), data.get("suffix"))
    language, error_response, status = validate_language(data.get("language", "python"))
    if error_response:
        return error_response, status
    try:
        max_tokens = int(data.get("max_tokens", 96))
    except (TypeError, ValueError):
        max_tokens = 96
    max_tokens = max(32, min(max_tokens, 256))

    if not prefix:
        return Response("", content_type="text/plain; charset=utf-8")

    record = begin_help(
        current_user, "autocomplete", 4, {"language": language, "prefix": prefix, "suffix": suffix}
    )

    record_id = record.id

    @stream_with_context
    def generate():
        record = db.session.get(LearningHelp, record_id)
        answer = ""
        try:
            for chunk in stream_inline_completion(prefix, suffix, language, max_tokens=max_tokens):
                if not mode_is_current(record):
                    raise AIClientError("帮助模式已改变")
                answer += chunk
                yield chunk
            if answer:
                finish_help(record, {"code": answer})
            else:
                fail_help(record)
        except AIClientError:
            if record.state == "pending":
                fail_help(record)
        finally:
            if record.state == "pending":
                fail_help(record, "cancelled")

    return Response(
        generate(),
        content_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-store, no-transform",
            "X-Accel-Buffering": "no",
            "X-Help-Id": str(record_id),
        },
    )

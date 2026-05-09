from flask import Blueprint, request, jsonify, Response
from flask_login import login_required
from routes.guards import rate_limit
from routes.validators import trim_autocomplete_context, validate_language
from services.ai_autocomplete import stream_inline_completion

autocomplete_blueprint = Blueprint("autocomplete", __name__)


@autocomplete_blueprint.route("/api/ai-inline-complete-stream", methods=["POST", "OPTIONS"])
@login_required
@rate_limit(max_calls=60, window_seconds=60)
def ai_inline_complete_stream():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    data = request.get_json(silent=True) or {}
    prefix, suffix = trim_autocomplete_context(data.get("prefix"), data.get("suffix"))
    language, error_response, status = validate_language(data.get("language", "python"))
    if error_response:
        return error_response, status
    try:
        max_tokens = int(data.get("max_tokens", 128))
    except (TypeError, ValueError):
        max_tokens = 128
    max_tokens = max(32, min(max_tokens, 256))

    if not prefix:
        return Response("", content_type="text/plain; charset=utf-8")

    def generate():
        for chunk in stream_inline_completion(prefix, suffix, language, max_tokens=max_tokens):
            yield chunk

    return Response(generate(), content_type="text/plain; charset=utf-8")

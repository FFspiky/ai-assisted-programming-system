from flask import Blueprint, request, jsonify, Response
from flask_login import login_required
from services.ai_autocomplete import stream_inline_completion

autocomplete_blueprint = Blueprint("autocomplete", __name__)


@autocomplete_blueprint.route("/api/ai-inline-complete-stream", methods=["POST", "OPTIONS"])
@login_required
def ai_inline_complete_stream():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    data = request.get_json(silent=True) or {}
    prefix = (data.get("prefix") or "").strip("\x00")
    suffix = data.get("suffix") or ""
    language = (data.get("language") or "python").strip()
    max_tokens = int(data.get("max_tokens", 128))
    max_tokens = max(32, min(max_tokens, 256))

    if not prefix:
        return Response("", content_type="text/plain; charset=utf-8")

    def generate():
        for chunk in stream_inline_completion(prefix, suffix, language, max_tokens=max_tokens):
            yield chunk

    return Response(generate(), content_type="text/plain; charset=utf-8")

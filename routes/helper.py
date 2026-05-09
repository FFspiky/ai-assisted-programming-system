from flask import Blueprint, request, jsonify, Response
from flask_login import login_required
from routes.guards import rate_limit
from routes.validators import validate_ai_prompt, validate_language
from services.ai_helper import  stream_code_from_prompt

generate_blueprint = Blueprint('generate', __name__)

# 新增：流式响应接口
@generate_blueprint.route("/api/ai-chat-stream", methods=["POST", "OPTIONS"])
@login_required
@rate_limit(max_calls=10, window_seconds=60)
def generate_code_stream():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.get_json(silent=True) or {}
    prompt, error_response, status = validate_ai_prompt((data.get("message") or "").strip())
    if error_response:
        return error_response, status
    language, error_response, status = validate_language(data.get("language", "python"))
    if error_response:
        return error_response, status

    if not prompt:
        return jsonify({"success": False, "error": "消息内容不能为空"}), 400

    def generate():
        for chunk in stream_code_from_prompt(prompt, language):
            yield chunk

    return Response(generate(), content_type='text/plain; charset=utf-8')

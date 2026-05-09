from flask import Blueprint, request, jsonify, Response
from services.ai_helper import  stream_code_from_prompt

generate_blueprint = Blueprint('generate', __name__)

# 新增：流式响应接口
@generate_blueprint.route("/api/ai-chat-stream", methods=["POST", "OPTIONS"])
def generate_code_stream():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.get_json()
    prompt = data.get("message", "").strip()
    language = data.get("language", "Python").strip()

    if not prompt:
        return jsonify({"success": False, "error": "消息内容不能为空"}), 400

    def generate():
        for chunk in stream_code_from_prompt(prompt, language):
            yield chunk

    return Response(generate(), content_type='text/plain; charset=utf-8')

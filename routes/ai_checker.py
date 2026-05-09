from flask import Blueprint, request, jsonify
from flask_login import login_required
from routes.guards import rate_limit
from routes.validators import validate_ai_prompt, validate_language
from services.ai_code_checker import check_code

ai_checker_blueprint = Blueprint("ai_checker", __name__)

@ai_checker_blueprint.route("/api/optimize-code", methods=["POST", "OPTIONS"]) # 修改为 /api/optimize-code
@login_required
@rate_limit(max_calls=10, window_seconds=60)
def ai_check_code():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.get_json(silent=True) or {}
    code, error_response, status = validate_ai_prompt(data.get("code", ""))
    if error_response:
        return error_response, status
    language, error_response, status = validate_language(data.get("language", "python"))
    if error_response:
        return error_response, status

    try:
        report = check_code(code, language)
        return jsonify(report)
    except Exception as e:
        return jsonify({'success': False, 'error': f'AI代码检查失败: {str(e)}'}), 500

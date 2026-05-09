# routes/execute.py

from flask import Blueprint, request, jsonify
from flask_login import login_required
from services.execute_runner import run_code

execute_blueprint = Blueprint("execute", __name__)

@execute_blueprint.route("/api/run-code", methods=["POST", "OPTIONS"])
@login_required
def execute_code():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    language = data.get("language", "Python")
    # 新增: 从请求中获取 input_text
    input_text = data.get("input_text", None) 

    # 将 input_text 传递给 run_code 函数
    result = run_code(code, language, input_text=input_text)
    return jsonify(result)

# routes/execute.py

from flask import Blueprint, request, jsonify
from flask_login import login_required
from routes.guards import rate_limit
from routes.validators import validate_code_payload
from services.execute_runner import run_code

execute_blueprint = Blueprint("execute", __name__)

@execute_blueprint.route("/api/run-code", methods=["POST", "OPTIONS"])
@login_required
@rate_limit(max_calls=20, window_seconds=60)
def execute_code():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.get_json(silent=True) or {}
    code, language, input_text, error_response = validate_code_payload(data)
    if error_response:
        return error_response

    result = run_code(code, language, input_text=input_text)
    return jsonify(result)

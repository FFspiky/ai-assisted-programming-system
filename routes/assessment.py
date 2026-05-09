# routes/assessment.py
from flask import Blueprint, request, jsonify, Response # <-- 1. 从 flask 导入 Response
from flask_login import login_required
from routes.guards import rate_limit
from services.learning_path_service import generate_learning_path

assessment_blueprint = Blueprint('assessment', __name__)

@assessment_blueprint.route('/api/assess-learning-path', methods=['POST'])
@login_required
@rate_limit(max_calls=5, window_seconds=60)
def assess_learning_path():
    data = request.get_json(silent=True) or {}
    answers = data.get('answers', [])
    
    if not answers:
        return jsonify({"success": False, "error": "未提供问卷答案"}), 400

    try:
        # 2. 返回一个流式 Response 对象
        # mimetype='text/event-stream' 是流式响应的标准类型
        return Response(generate_learning_path(answers), mimetype='text/event-stream')
    except Exception as e:
        # 这个异常捕获现在主要处理非流式部分的错误
        return jsonify({
            "success": False,
            "error": f"生成学习路径失败: {str(e)}"
        }), 500

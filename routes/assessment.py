# routes/assessment.py
import json

from flask import Blueprint, Response, request, stream_with_context
from flask_login import current_user, login_required

from routes.api_response import api_error, api_success
from routes.guards import rate_limit
from services import learning_plan
from services.learning_path_service import generate_learning_path

assessment_blueprint = Blueprint("assessment", __name__)


@assessment_blueprint.get("/api/learning-plan/questions")
def plan_questions():
    return api_success(
        {"questions": learning_plan.public_questions(), "version": learning_plan.VERSION}
    )


@assessment_blueprint.get("/api/learning-plan")
@login_required
def read_plan():
    return api_success(learning_plan.payload(current_user.id))


@assessment_blueprint.post("/api/learning-plan")
@login_required
@rate_limit(max_calls=15, window_seconds=60)
def save_plan():
    data = request.get_json(silent=True) or {}
    try:
        return api_success(
            learning_plan.save(current_user.id, data.get("answers"), data.get("revision"))
        )
    except learning_plan.PlanError as exc:
        return api_error(exc.code, exc.message, exc.status)


@assessment_blueprint.route("/api/assess-learning-path", methods=["POST"])
@login_required
@rate_limit(max_calls=5, window_seconds=60)
def assess_learning_path():
    data = request.get_json(silent=True) or {}
    answers = data.get("answers", [])

    if not answers:
        return api_error("ANSWERS_MISSING", "未提供问卷答案", 400)
    if (
        not isinstance(answers, list)
        or len(answers) > 50
        or len(json.dumps(answers, ensure_ascii=False)) > 16000
    ):
        return api_error("INVALID_ANSWERS", "问卷答案必须是最多 50 项的列表，且内容不能过长", 400)

    try:
        # 2. 返回一个流式 Response 对象
        # mimetype='text/event-stream' 是流式响应的标准类型
        return Response(
            stream_with_context(generate_learning_path(answers)), mimetype="text/event-stream"
        )
    except Exception as e:
        # 这个异常捕获现在主要处理非流式部分的错误
        return api_error("LEARNING_PATH_FAILED", f"生成学习路径失败: {str(e)}", 500)

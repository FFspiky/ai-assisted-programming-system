from flask import Blueprint, current_app, request
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from models import Problem, Submission, User, db
from routes.api_response import api_error, api_success
from routes.guards import rate_limit
from routes.validators import validate_code_payload
from services.execute_runner import run_code
from services.judge import outputs_match
from services.practice_history import PracticeConflict, prepare_submission, record_submission
from services.tutor_service import serialize_submission

solution_checker_blueprint = Blueprint("solution_checker", __name__)


@solution_checker_blueprint.route("/check-solution", methods=["POST"])
@login_required
@rate_limit(max_calls=30, window_seconds=60)
def check_solution():
    data = request.get_json(silent=True) or {}
    code, language, _, error_response = validate_code_payload(data)
    if error_response:
        return error_response
    if not code.strip():
        return api_error("EMPTY_CODE", "请输入代码", 400)
    problem = db.session.get(Problem, data.get("problem_id", ""))
    if not problem:
        return api_error("PROBLEM_NOT_FOUND", "题目不存在", 404)
    cases = problem.test_cases.order_by("id").all()
    if not cases:
        return api_error("TEST_CASES_MISSING", "该题目还没有测试用例", 400)
    try:
        context = prepare_submission(current_user.id, data, code, language, problem.id)
    except PracticeConflict as exc:
        return api_error("PRACTICE_CONFLICT", str(exc), exc.status)
    if context.get("replay"):
        return submission_response(context["replay"])
    results, details, final_status = [], [], "Accepted"
    for index, case in enumerate(cases, 1):
        run = run_code(code, language, input_text=case.input_data)
        if not run.get("success"):
            status = run.get("status", "Runtime Error")
        elif outputs_match(run.get("output", ""), case.expected_output, problem.judge_mode):
            status = "Accepted"
        else:
            status = "Wrong Answer"
        result = {
            "id": f"case-{index}",
            "index": index,
            "is_public": case.is_public,
            "input": case.input_data,
            "expected_output": case.expected_output,
            "actual_output": run.get("output", ""),
            "error": run.get("error", ""),
            "status": status,
            "passed": status == "Accepted",
            "time": run.get("time"),
            "compile_time": run.get("compile_time"),
            "run_time": run.get("run_time"),
            "output_truncated": run.get("output_truncated", False),
            "error_truncated": run.get("error_truncated", False),
        }
        results.append(result)
        message = f"测试用例 {index}：{status}"
        if case.is_public and status != "Accepted":
            message += f"\n输入：{case.input_data}\n预期：{case.expected_output}\n实际：{result['actual_output']}\n{result['error']}"
        elif not case.is_public:
            message += "（隐藏验证用例）"
        details.append(message)
        if status != "Accepted":
            final_status = status
            break
    snapshot = {
        "version": 1,
        "problem": {
            "id": problem.id,
            "title": problem.title,
            "description": problem.description,
            "judge_mode": problem.judge_mode,
        },
        "cases": results,
        "total": len(cases),
        "executed": len(results),
        "not_run": len(cases) - len(results),
        "backend": "docker",
    }
    already_accepted = Submission.query.filter_by(
        user_id=current_user.id, problem_id=problem.id, status="Accepted"
    ).first()
    submission = Submission(
        code_submitted=code,
        language=language,
        status=final_status,
        feedback="\n".join(details),
        user_id=current_user.id,
        problem_id=problem.id,
        evidence_snapshot=snapshot,
    )
    db.session.add(submission)
    if final_status == "Accepted" and already_accepted is None:
        user = db.session.get(User, current_user.id)
        user.points += 10
    try:
        record_submission(context, submission)
        db.session.commit()
    except PracticeConflict as exc:
        db.session.rollback()
        return api_error("PRACTICE_CONFLICT", str(exc), exc.status)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not save judged submission and practice event")
        return api_error(
            "PRACTICE_SAVE_FAILED",
            "判题已完成，但提交与过程未确认保存；请重试读取或刷新查看记录",
            503,
        )
    return submission_response(submission)


def submission_response(submission):
    result = serialize_submission(submission)
    result.update(
        details=submission.feedback,
        new_points=current_user.points,
        test_results=result["evidence"]["cases"],
    )
    return api_success(result, **result)

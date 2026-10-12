from flask import Blueprint, request
from flask_login import current_user, login_required

from models import Submission, db
from routes.api_response import api_error, api_success
from routes.guards import rate_limit
from services.ai_client import AIClientError
from services.tutor_service import diagnose_submission, serialize_submission

tutoring_blueprint = Blueprint("tutoring", __name__)


def owned_submission(submission_id):
    return Submission.query.filter_by(id=submission_id, user_id=current_user.id).first()


@tutoring_blueprint.get("/submissions/<int:submission_id>")
@login_required
def submission_details(submission_id):
    submission = owned_submission(submission_id)
    if not submission:
        return api_error("SUBMISSION_NOT_FOUND", "提交不存在", 404)
    return api_success(serialize_submission(submission))


@tutoring_blueprint.get("/problems/<problem_id>/latest-submission")
@login_required
def latest_submission(problem_id):
    submission = (
        Submission.query.filter_by(
            user_id=current_user.id,
            problem_id=problem_id,
            language=request.args.get("language", "python"),
        )
        .order_by(Submission.id.desc())
        .first()
    )
    return api_success(serialize_submission(submission) if submission else None)


@tutoring_blueprint.post("/submissions/<int:submission_id>/diagnosis")
@login_required
@rate_limit(max_calls=6, window_seconds=60)
def submission_diagnosis(submission_id):
    submission = owned_submission(submission_id)
    if not submission:
        return api_error("SUBMISSION_NOT_FOUND", "提交不存在", 404)
    if not submission.evidence_snapshot:
        return api_error("EVIDENCE_MISSING", "历史提交没有证据快照，请重新提交代码", 409)
    if submission.status not in {"Wrong Answer", "Runtime Error", "Compile Error"}:
        return api_error("DIAGNOSIS_NOT_APPLICABLE", "此状态无需错因诊断，请先处理运行状态", 409)
    if submission.diagnosis:
        return api_success(serialize_submission(submission))
    try:
        diagnosis = diagnose_submission(submission)
    except AIClientError as exc:
        return api_error("DIAGNOSIS_UNAVAILABLE", str(exc), 503)
    submission.diagnosis = diagnosis
    db.session.commit()
    return api_success(serialize_submission(submission))

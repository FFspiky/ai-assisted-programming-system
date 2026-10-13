from flask import Blueprint, request
from flask_login import current_user, login_required

from models import Submission, db
from routes.api_response import api_error, api_success
from routes.guards import rate_limit
from services.ai_client import AIClientError
from services.tutor_service import diagnose_submission, safe_saved_diagnosis, serialize_submission

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
    if current_user.help_mode == "learning":
        return api_error("HELP_LEVEL_REQUIRED", "请在运行结果中选择帮助程度", 409)
    if submission.diagnosis:
        submission.diagnosis = safe_saved_diagnosis(submission)
        db.session.commit()
        return api_success(serialize_submission(submission))
    try:
        diagnosis = diagnose_submission(submission)
    except AIClientError as exc:
        return api_error("DIAGNOSIS_UNAVAILABLE", str(exc), 503)
    submission.diagnosis = diagnosis
    db.session.commit()
    return api_success(serialize_submission(submission))


@tutoring_blueprint.get("/help-settings")
@login_required
def help_settings():
    return api_success({"mode": current_user.help_mode, "revision": current_user.help_revision})


@tutoring_blueprint.post("/help-settings")
@login_required
def change_help_settings():
    from config import MODEL_NAME
    from models import LearningHelp
    from services.learning_help import PROMPT_VERSION

    mode = (request.get_json(silent=True) or {}).get("mode")
    if mode not in {"learning", "free"}:
        return api_error("INVALID_MODE", "请选择学习模式或自由辅助", 400)
    if current_user.help_mode != mode:
        current_user.help_mode = mode
        current_user.help_revision += 1
        db.session.add(
            LearningHelp(
                user_id=current_user.id,
                source="mode",
                mode=mode,
                mode_revision=current_user.help_revision,
                requested_level=0,
                returned_level=0,
                state="ready",
                request_snapshot={"mode": mode},
                result={"mode": mode},
                model=MODEL_NAME,
                prompt_version=PROMPT_VERSION,
            )
        )
        db.session.commit()
    return api_success({"mode": current_user.help_mode, "revision": current_user.help_revision})


@tutoring_blueprint.get("/submissions/<int:submission_id>/help")
@login_required
def submission_help_history(submission_id):
    from models import LearningHelp
    from services.learning_help import help_payload

    if not owned_submission(submission_id):
        return api_error("SUBMISSION_NOT_FOUND", "提交不存在", 404)
    records = (
        LearningHelp.query.filter_by(
            user_id=current_user.id,
            submission_id=submission_id,
            mode=current_user.help_mode,
            source="panel",
            state="ready",
        )
        .order_by(LearningHelp.id)
        .all()
    )
    return api_success({"records": [help_payload(record) for record in records]})


@tutoring_blueprint.post("/submissions/<int:submission_id>/help")
@login_required
@rate_limit(max_calls=8, window_seconds=60)
def request_submission_help(submission_id):
    from models import LearningHelp
    from services.learning_help import (
        PROMPT_VERSION,
        begin_help,
        fail_help,
        finish_help,
        generate_help,
        help_payload,
        parse_level,
    )

    submission = owned_submission(submission_id)
    if not submission:
        return api_error("SUBMISSION_NOT_FOUND", "提交不存在", 404)
    if not submission.evidence_snapshot:
        return api_error("EVIDENCE_MISSING", "这次提交没有执行快照，请重新提交", 409)
    try:
        level = parse_level((request.get_json(silent=True) or {}).get("level"))
    except ValueError as exc:
        return api_error("INVALID_HELP_LEVEL", str(exc), 400)
    if submission.status not in {"Wrong Answer", "Runtime Error", "Compile Error"}:
        return api_error("HELP_NOT_APPLICABLE", "当前判题状态无需错因提示", 409)
    cached = (
        LearningHelp.query.filter_by(
            user_id=current_user.id,
            submission_id=submission_id,
            mode=current_user.help_mode,
            source="panel",
            state="ready",
            requested_level=level,
            prompt_version=PROMPT_VERSION,
        )
        .order_by(LearningHelp.id.desc())
        .first()
    )
    if cached:
        return api_success(help_payload(cached))
    record = begin_help(
        current_user,
        "panel",
        level,
        {"code": submission.code_submitted, "language": submission.language},
        submission_id,
    )
    try:
        result = generate_help(submission, level)
        finish_help(record, result)
    except AIClientError as exc:
        if record.state == "pending":
            fail_help(record)
        return api_error("HELP_UNAVAILABLE", str(exc), 503)
    return api_success(help_payload(record))


@tutoring_blueprint.post("/help/<int:help_id>/shown")
@login_required
def mark_help_shown(help_id):
    from datetime import datetime, timezone

    from models import LearningHelp

    record = (
        LearningHelp.query.filter_by(id=help_id, user_id=current_user.id, state="ready")
        .filter((LearningHelp.source == "chat") | (LearningHelp.mode == current_user.help_mode))
        .first()
    )
    if not record:
        return api_error("HELP_NOT_FOUND", "帮助记录不存在或当前模式已改变", 404)
    if record.shown_at is None:
        record.shown_at = datetime.now(timezone.utc)
        db.session.commit()
    return api_success({"id": record.id})

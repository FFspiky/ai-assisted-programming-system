from flask import Blueprint, current_app, request
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from models import db
from routes.api_response import api_error, api_success
from services.practice_history import PracticeConflict, action

practice_history_blueprint = Blueprint("practice_history", __name__)


@practice_history_blueprint.errorhandler(SQLAlchemyError)
def practice_storage_error(exc):
    db.session.rollback()
    current_app.logger.exception("Practice storage operation was not confirmed")
    return api_error(
        "PRACTICE_SAVE_FAILED", "操作未确认保存，原代码没有改变；请读取记录或重试", 503
    )


@practice_history_blueprint.post("/co-create/sessions/<session_id>/handoff")
@login_required
def co_create_handoff(session_id):
    """Prepare an owned suggestion; this never changes a draft or creates a submission."""
    import hashlib

    from config import MAX_CODE_CHARS
    from models import CodeProposal, PracticeEvent, Submission
    from modules.co_create import problem_service, service
    from modules.co_create.models import CoCreateSession
    from services.code_proposals import proposal_payload

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return api_error("INVALID_INPUT", "请求须为 JSON 对象", 400)
    try:
        row = service.owned(session_id, current_user.id)
        service.check_revision(row, data.get("revision"))
        if problem_service.is_problem(row):
            problem_service.live_problem(row)
    except service.CreationError as exc:
        return api_error(exc.code, exc.message, exc.status)
    if not row.problem_id:
        return api_error("LEGACY_RECORD", "旧场景记录可回看，请从题目新建共创后带回代码", 400)
    candidate_id = data.get("candidate_id")
    if candidate_id == "review":
        if row.mode != "review":
            return api_error("INVALID_MODE", "请在代码质检记录中带回待检代码", 400)
        code = row.state.get("review", {}).get("code", "")
        stable_id = "review:" + hashlib.sha256(code.encode()).hexdigest()
    else:
        generation = next(
            (
                g
                for g in row.state.get("generations", [])
                if g["id"] == row.state.get("current_generation_id")
            ),
            None,
        )
        candidate = next(
            (c for c in (generation or {}).get("candidates", []) if c["id"] == candidate_id), None
        )
        if candidate is None:
            return api_error("CANDIDATE_NOT_FOUND", "请先生成并选择当前候选", 404)
        code = candidate.get("code", "")
        stable_id = candidate["id"]
    if not isinstance(code, str) or not code.strip() or len(code) > MAX_CODE_CHARS:
        return api_error("INVALID_CODE", "候选代码为空或过长", 400)
    context = row.state.get("practice_context", {})
    base_code = context.get("code", "")
    if not isinstance(base_code, str) or len(base_code) > MAX_CODE_CHARS:
        return api_error("INVALID_CONTEXT", "原草稿不完整，请从刷题页重新进入共创", 400)
    # Lock the same revision in the transaction that writes the proposal. A late
    # response must not attach a candidate superseded in another window.
    unchanged = CoCreateSession.query.filter_by(
        id=row.id, user_id=current_user.id, revision=data["revision"]
    ).update({"revision": data["revision"]}, synchronize_session=False)
    if unchanged != 1:
        db.session.rollback()
        return api_error("STALE_REVISION", "记录已被更新，请读取最新候选后再带回", 409)
    existing = CodeProposal.query.filter_by(
        user_id=current_user.id, co_create_session_id=row.id, co_create_candidate_id=stable_id
    ).first()
    if existing:
        db.session.commit()
        return api_success(
            {
                "proposal": proposal_payload(existing),
                "problem_id": row.problem_id,
                "language": row.language,
            }
        )
    base = Submission.query.filter_by(
        id=context.get("submission_id"),
        user_id=current_user.id,
        problem_id=row.problem_id,
        language=row.language,
    ).first()
    proposal = CodeProposal(
        user_id=current_user.id,
        help_id=None,
        submission_id=base.id if base else None,
        problem_id=row.problem_id,
        language=row.language,
        source="co_create",
        co_create_session_id=row.id,
        co_create_candidate_id=stable_id,
        base_code=base_code,
        candidate_code=code,
        edits=[],
    )
    db.session.add(proposal)
    try:
        db.session.flush()
        db.session.add(
            PracticeEvent(
                user_id=current_user.id,
                problem_id=row.problem_id,
                language=row.language,
                submission_id=base.id if base else None,
                proposal_id=proposal.id,
                kind="co_create",
                payload={
                    "session_id": row.id,
                    "candidate_id": stable_id,
                    "note": "候选已准备，等待用户查看差异并采纳；尚未正式判题",
                },
            )
        )
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        existing = CodeProposal.query.filter_by(
            user_id=current_user.id, co_create_session_id=row.id, co_create_candidate_id=stable_id
        ).first()
        if existing:
            return api_success(
                {
                    "proposal": proposal_payload(existing),
                    "problem_id": row.problem_id,
                    "language": row.language,
                }
            )
        return api_error("PRACTICE_SAVE_FAILED", "候选未确认保存，原草稿没有改变，请重试", 503)
    return api_success(
        {
            "proposal": proposal_payload(proposal),
            "problem_id": row.problem_id,
            "language": row.language,
        }
    )


@practice_history_blueprint.post("/proposals/<int:proposal_id>/actions")
@login_required
def proposal_action(proposal_id):
    try:
        return api_success(
            action(current_user.id, proposal_id, request.get_json(silent=True) or {})
        )
    except PracticeConflict as exc:
        db.session.rollback()
        return api_error("PRACTICE_CONFLICT", str(exc), exc.status)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not save proposal action")
        return api_error(
            "PRACTICE_SAVE_FAILED", "操作未确认保存，编辑器未改变；请重试读取或刷新查看记录", 503
        )


@practice_history_blueprint.get("/help/<int:help_id>/review")
@login_required
def review_help(help_id):
    from models import LearningHelp
    from services.learning_help import help_payload

    record = LearningHelp.query.filter_by(
        id=help_id, user_id=current_user.id, source="panel", state="ready"
    ).first()
    if not record:
        return api_error("HELP_NOT_FOUND", "提示不存在", 404)
    return api_success(help_payload(record))


@practice_history_blueprint.get("/problems/<problem_id>/practice-history")
@login_required
def practice_history(problem_id):
    from sqlalchemy import and_

    from models import CodeProposal, LearningHelp, PracticeEvent, Submission
    from services.code_proposals import proposal_payload
    from services.tutor_service import serialize_submission

    language = request.args.get("language", "python")
    before = request.args.get("before", type=int)
    query = Submission.query.filter_by(
        user_id=current_user.id, problem_id=problem_id, language=language
    )
    if before:
        query = query.filter(Submission.id < before)
    submissions = query.order_by(Submission.id.desc()).limit(21).all()
    has_more = len(submissions) > 20
    submissions = submissions[:20]
    ids = [sub.id for sub in submissions]
    # The most recently accepted, not undone proposal remains an explicit attribution choice.
    active_event = (
        PracticeEvent.query.join(CodeProposal, PracticeEvent.proposal_id == CodeProposal.id)
        .filter(
            PracticeEvent.user_id == current_user.id,
            PracticeEvent.problem_id == problem_id,
            PracticeEvent.language == language,
            PracticeEvent.kind == "accept",
            CodeProposal.state == "accepted",
        )
        .order_by(PracticeEvent.id.desc())
        .first()
    )
    active_id = active_event.proposal_id if active_event else None
    proposals = (
        CodeProposal.query.filter(
            CodeProposal.user_id == current_user.id,
            (CodeProposal.submission_id.in_(ids))
            | (CodeProposal.id == active_id)
            | and_(
                CodeProposal.source == "co_create",
                CodeProposal.problem_id == problem_id,
                CodeProposal.language == language,
            ),
        )
        .order_by(CodeProposal.id.desc())
        .limit(80)
        .all()
    )
    proposal_ids = [proposal.id for proposal in proposals]
    events = (
        PracticeEvent.query.filter(
            PracticeEvent.user_id == current_user.id,
            PracticeEvent.problem_id == problem_id,
            PracticeEvent.language == language,
            (PracticeEvent.submission_id.in_(ids)) | (PracticeEvent.proposal_id.in_(proposal_ids)),
        )
        .order_by(PracticeEvent.id)
        .all()
    )
    helps = (
        LearningHelp.query.filter(
            LearningHelp.user_id == current_user.id,
            LearningHelp.submission_id.in_(ids),
            LearningHelp.source == "panel",
        )
        .order_by(LearningHelp.id)
        .all()
    )
    return api_success(
        {
            "submissions": [serialize_submission(sub) for sub in submissions],
            "proposals": [proposal_payload(proposal) for proposal in proposals],
            "active_proposal_id": active_id,
            "helps": [
                {
                    "id": help.id,
                    "submission_id": help.submission_id,
                    "level": help.requested_level,
                    "state": help.state,
                    "mode": help.mode,
                    "shown_at": help.shown_at.isoformat() + "Z" if help.shown_at else None,
                    "created_at": help.created_at.isoformat() + "Z",
                }
                for help in helps
            ],
            "events": [
                {
                    "id": event.id,
                    "kind": event.kind,
                    "proposal_id": event.proposal_id,
                    "submission_id": event.submission_id,
                    "created_at": event.created_at.isoformat() + "Z",
                    "data": {k: v for k, v in event.payload.items() if k != "fingerprint"},
                }
                for event in events
            ],
            "next_before": ids[-1] if has_more else None,
        }
    )

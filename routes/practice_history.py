from flask import Blueprint, current_app, request
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from models import db
from routes.api_response import api_error, api_success
from services.practice_history import PracticeConflict, action

practice_history_blueprint = Blueprint("practice_history", __name__)


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
    proposals = CodeProposal.query.filter(
        CodeProposal.user_id == current_user.id,
        (CodeProposal.submission_id.in_(ids)) | (CodeProposal.id == active_id),
    ).all()
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

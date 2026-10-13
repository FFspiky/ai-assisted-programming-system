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

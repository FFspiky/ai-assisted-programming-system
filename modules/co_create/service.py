"""Shared session ownership, revisions and problem-based creation dispatch.

Retired scene sessions remain readable, but cannot be created or mutated.
"""

import copy
import uuid
from datetime import datetime, timezone

from models import db
from services.execute_runner import run_code  # noqa: F401 -- shared execution injection point

from . import problem_service
from .models import CoCreateSession, now


class CreationError(Exception):
    def __init__(self, message, status=400, code="CO_CREATE_ERROR"):
        super().__init__(message)
        self.message, self.status, self.code = message, status, code


def ident():
    return uuid.uuid4().hex


def stamp(value):
    return value.replace(tzinfo=timezone.utc).isoformat()


def text(value, name, size, empty=False):
    if not isinstance(value, str) or len(value) > size or (not empty and not value.strip()):
        raise CreationError(f"{name}须为文本，最多 {size} 字。")
    return value


def owned(session_id, user_id):
    row = CoCreateSession.query.filter_by(id=session_id, user_id=user_id).first()
    if row is None:
        raise CreationError("创作记录不存在或无权访问。", 404, "NOT_FOUND")
    return row


def recover_interrupted(row):
    """A terminated web worker must not leave a candidate permanently running."""
    state = copy.deepcopy(row.state)
    changed = False
    for generation in state.get("generations", []):
        if generation.get("status") != "running":
            continue
        try:
            started = datetime.fromisoformat(generation["created_at"])
            stale = (now() - started).total_seconds() > 300
        except (KeyError, ValueError, TypeError):
            stale = True
        if stale:
            generation.update(
                status="failed", error="生成或验证已中断，请重新生成。本次未完成验证。"
            )
            changed = True
    if changed:
        revision = row.revision
        count = (
            db.session.query(CoCreateSession)
            .filter_by(id=row.id, user_id=row.user_id, revision=revision)
            .update(
                {"state": state, "revision": revision + 1, "updated_at": now()},
                synchronize_session=False,
            )
        )
        if count == 1:
            db.session.commit()
        else:
            db.session.rollback()
        db.session.refresh(row)


def check_revision(row, revision):
    if type(revision) is not int or revision != row.revision:
        raise CreationError("记录已在另一窗口更新，请重新打开后操作。", 409, "STALE_REVISION")


def commit(row, revision, state, event):
    check_revision(row, revision)
    state = copy.deepcopy(state)
    state["events"] = state.get("events", [])[-79:] + [
        {"id": ident(), "title": event, "created_at": stamp(now())}
    ]
    changed = (
        db.session.query(CoCreateSession)
        .filter_by(
            id=row.id,
            user_id=row.user_id,
            revision=revision,
        )
        .update(
            {"state": state, "revision": revision + 1, "updated_at": now()},
            synchronize_session=False,
        )
    )
    if changed != 1:
        db.session.rollback()
        raise CreationError("此操作已经过期，请刷新查看最新记录。", 409, "STALE_REVISION")
    db.session.commit()
    db.session.refresh(row)
    return row


def require_mode(row, mode):
    if row.mode != mode:
        raise CreationError("此操作不适用于当前创作模式。")


def serialize(row, full=True):
    if problem_service.is_problem(row):
        recover_interrupted(row)
        return problem_service.serialize(row, full)
    result = {k: getattr(row, k) for k in ("id", "mode", "scenario_id", "title", "revision")}
    result.update(created_at=stamp(row.created_at), updated_at=stamp(row.updated_at))
    result.update(problem_id=None, language=row.language, legacy=True)
    if full:
        result["state"] = copy.deepcopy(row.state)
    return result


def require_current(row):
    if not problem_service.is_problem(row):
        raise CreationError("旧场景记录仅供回看，请从题库新建共创。", 400, "LEGACY_RECORD")


def create(user_id, mode, scenario_id=None, **data):
    if not data.get("problem_id"):
        raise CreationError("请从题库选择题目，旧场景共创已停用。", 400, "PROBLEM_REQUIRED")
    return problem_service.create(user_id, mode, **data)


def update_examples(row, revision, data):
    require_current(row)
    return problem_service.update_examples(row, revision, data)


def generate(row, revision, source):
    require_current(row)
    return problem_service.generate(row, revision, source)


def compare(row, revision, value, **data):
    require_current(row)
    return problem_service.compare(row, revision, value, **data)


def select(row, revision, generation_id, candidate_id):
    require_current(row)
    return problem_service.select(row, revision, generation_id, candidate_id)


def save_review(row, revision, data):
    require_current(row)
    return problem_service.save_review(row, revision, data)


def review_run(row, revision, value, **data):
    require_current(row)
    return problem_service.review_run(row, revision, value, **data)


def generate_review(row, revision, source):
    require_current(row)
    return problem_service.generate(row, revision, source, review=True)

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from config import SUPPORTED_LANGUAGES
from models import db
from routes.api_response import api_error, api_success
from routes.guards import rate_limit
from services.language_support import language_options

from . import ai, learning_service, problem_service, service
from .catalog import list_catalog
from .models import CoCreateSession

blueprint = Blueprint(
    "co_create",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/co-create-assets",
)


@blueprint.before_request
def bounded_request():
    if request.path.startswith("/api/co-create"):
        request.max_content_length = 80 * 1024
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if not request.is_json or not isinstance(request.get_json(silent=True), dict):
                return api_error("INVALID_JSON", "请使用 JSON 对象请求。", 400)


@blueprint.errorhandler(service.CreationError)
def creation_error(exc):
    return api_error(exc.code, exc.message, exc.status)


@blueprint.errorhandler(ValueError)
@blueprint.errorhandler(TypeError)
@blueprint.errorhandler(RecursionError)
def invalid_input(exc):
    return api_error(
        "INVALID_INPUT",
        str(exc)[:240] if isinstance(exc, ValueError) else "输入格式无效。",
        400,
    )


@blueprint.errorhandler(IntegrityError)
def concurrent(exc):
    db.session.rollback()
    return api_error("STALE_REVISION", "记录已被更新，请刷新。", 409)


@blueprint.get("/co-create.html")
def page():
    return render_template("problem_create.html")


@blueprint.get("/co-create")
def alias():
    return redirect(url_for("co_create.page"))


@blueprint.get("/api/co-create/catalog")
def catalog():
    return api_success(
        {
            "scenarios": list_catalog(),
            "ai_available": ai.available(),
            "languages": language_options(SUPPORTED_LANGUAGES),
            "problem_driven": True,
            "problems_url": "/api/problems",
        }
    )


@blueprint.get("/api/co-create/sessions")
@login_required
def sessions():
    rows = (
        CoCreateSession.query.filter_by(user_id=current_user.id)
        .order_by(CoCreateSession.updated_at.desc())
        .limit(80)
        .all()
    )
    return api_success({"sessions": [service.serialize(row, full=False) for row in rows]})


@blueprint.post("/api/co-create/sessions")
@login_required
@rate_limit(20, 60)
def create():
    data = request.get_json()
    row = service.create(
        current_user.id,
        data.get("mode"),
        data.get("scenario_id"),
        **{
            key: data[key]
            for key in ("problem_id", "language", "code", "input_text", "submission_id", "reuse")
            if key in data
        },
    )
    return api_success({"session": service.serialize(row)}, http_status=201)


def owned(session_id):
    return service.owned(session_id, current_user.id)


@blueprint.get("/api/co-create/sessions/<session_id>")
@login_required
def detail(session_id):
    return api_success({"session": service.serialize(owned(session_id))})


@blueprint.patch("/api/co-create/sessions/<session_id>")
@login_required
def update(session_id):
    data = request.get_json()
    row = service.update_examples(owned(session_id), data.get("revision"), data)
    return api_success({"session": service.serialize(row)})


@blueprint.post("/api/co-create/sessions/<session_id>/generate")
@login_required
@rate_limit(6, 60)
def generate(session_id):
    data = request.get_json()
    row = service.generate(owned(session_id), data.get("revision"), data.get("source"))
    return api_success({"session": service.serialize(row)})


@blueprint.post("/api/co-create/sessions/<session_id>/compare")
@login_required
@rate_limit(10, 60)
def compare(session_id):
    data = request.get_json()
    row, run = service.compare(
        owned(session_id),
        data.get("revision"),
        data.get("input"),
        **{key: data[key] for key in ("expected", "input_validated") if key in data},
    )
    return api_success({"session": service.serialize(row), "run": run})


@blueprint.post("/api/co-create/sessions/<session_id>/select")
@login_required
def select(session_id):
    data = request.get_json()
    row = service.select(
        owned(session_id),
        data.get("revision"),
        data.get("generation_id"),
        data.get("candidate_id"),
    )
    return api_success({"session": service.serialize(row)})


@blueprint.post("/api/co-create/sessions/<session_id>/review")
@login_required
def review(session_id):
    data = request.get_json()
    row = service.save_review(owned(session_id), data.get("revision"), data)
    return api_success({"session": service.serialize(row)})


@blueprint.post("/api/co-create/sessions/<session_id>/review-run")
@login_required
@rate_limit(12, 60)
def review_run(session_id):
    data = request.get_json()
    row, run = service.review_run(
        owned(session_id),
        data.get("revision"),
        data.get("input"),
        **{key: data[key] for key in ("expected", "input_validated") if key in data},
    )
    return api_success({"session": service.serialize(row), "run": run})


@blueprint.post("/api/co-create/sessions/<session_id>/review-generate")
@login_required
@rate_limit(6, 60)
def review_generate(session_id):
    data = request.get_json()
    row = service.generate_review(owned(session_id), data.get("revision"), data.get("source"))
    return api_success({"session": service.serialize(row)})


@blueprint.post("/api/co-create/sessions/<session_id>/verify")
@login_required
@rate_limit(6, 60)
def verify(session_id):
    data = request.get_json()
    row = owned(session_id)
    if not problem_service.is_problem(row):
        raise service.CreationError("旧场景记录没有对应的题库用例。")
    row, run = problem_service.verify(row, data.get("revision"), data.get("candidate_id"))
    return api_success({"session": service.serialize(row), "run": run})


def learning_result(row, **extra):
    return api_success({**learning_service.payload(row), **extra})


@blueprint.get("/api/co-create/sessions/<session_id>/learning")
@login_required
def learning_detail(session_id):
    return learning_result(owned(session_id))


@blueprint.post("/api/co-create/sessions/<session_id>/learning/reflection")
@login_required
def learning_reflection(session_id):
    data = request.get_json()
    row = learning_service.reflection(owned(session_id), data.get("revision"), data)
    return learning_result(row, session=service.serialize(row))


@blueprint.post("/api/co-create/sessions/<session_id>/learning/transfer")
@login_required
def learning_transfer(session_id):
    data = request.get_json()
    row, attempt = learning_service.transfer(
        owned(session_id), data.get("revision"), data.get("problem_id")
    )
    return learning_result(
        row,
        session=service.serialize(row),
        attempt=attempt,
        practice_url=learning_service.practice_url(row, attempt),
    )


@blueprint.get("/api/co-create/sessions/<session_id>/learning/transfer/<attempt_id>")
@login_required
def learning_attempt(session_id, attempt_id):
    return api_success(learning_service.attempt_context(owned(session_id), attempt_id))


@blueprint.post("/api/co-create/sessions/<session_id>/learning/transfer/<attempt_id>/submission")
@login_required
def learning_submission(session_id, attempt_id):
    data = request.get_json()
    row, attempt = learning_service.attach_submission(
        owned(session_id), data.get("revision"), attempt_id, data
    )
    return learning_result(row, session=service.serialize(row), attempt=attempt)

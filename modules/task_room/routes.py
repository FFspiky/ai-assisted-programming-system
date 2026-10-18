"""One integration point for the standalone task room."""

import json

from flask import Blueprint, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from models import db
from routes.api_response import api_error, api_success
from routes.guards import rate_limit
from services.language_support import language_options

from . import ai, service
from .catalog import list_catalog
from .languages import interface_guide, source_filename
from .models import TaskProject

blueprint = Blueprint(
    "task_room",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/task-room-assets",
)


@blueprint.before_request
def limit_body():
    if request.path.startswith("/api/task-room"):
        request.max_content_length = 160 * 1024
        if request.method not in {"GET", "HEAD", "OPTIONS"} and not request.is_json:
            return api_error("INVALID_JSON", "请使用 JSON 请求。", 400)
    return None


@blueprint.errorhandler(service.RoomError)
def room_error(exc):
    return api_error(exc.code, exc.message, exc.status)


@blueprint.errorhandler(ValueError)
@blueprint.errorhandler(TypeError)
@blueprint.errorhandler(RecursionError)
def invalid_input(exc):
    return api_error(
        "INVALID_INPUT", str(exc)[:240] if isinstance(exc, ValueError) else "输入格式无效。", 400
    )


@blueprint.errorhandler(IntegrityError)
def concurrent_update(exc):
    db.session.rollback()
    return api_error("CONCURRENT_UPDATE", "请求已在另一窗口提交，请刷新后查看。", 409)


@blueprint.get("/task-room.html")
def page():
    return render_template("task_room.html")


@blueprint.get("/task-room")
def alias():
    return redirect(url_for("task_room.page"))


@blueprint.get("/api/task-room/catalog")
def catalog():
    return api_success(
        {
            "scenarios": list_catalog(),
            "ai_available": ai.available(),
            "languages": [
                {
                    "id": spec["id"],
                    "label": spec["label"],
                    "version": spec["version"],
                    "filename": source_filename(spec["id"]),
                    "entrypoint": interface_guide(spec["id"]),
                }
                for spec in language_options()
            ],
        }
    )


@blueprint.get("/api/task-room/projects")
@login_required
def projects():
    archived = request.args.get("archived", "0") == "1"
    rows = (
        TaskProject.query.filter_by(user_id=current_user.id, archived=archived)
        .order_by(TaskProject.updated_at.desc())
        .all()
    )
    return api_success({"projects": [service.serialize(p, full=False) for p in rows]})


@blueprint.post("/api/task-room/projects")
@login_required
@rate_limit(15, 60)
def create():
    data = request.get_json()
    project = service.create_project(
        current_user.id, data.get("scenario_id"), data.get("language", "python")
    )
    return api_success({"project": service.serialize(project)}, http_status=201)


@blueprint.get("/api/task-room/projects/<project_id>")
@login_required
def detail(project_id):
    return api_success({"project": service.serialize(service.owned(project_id, current_user.id))})


@blueprint.patch("/api/task-room/projects/<project_id>")
@login_required
def update(project_id):
    data = request.get_json()
    project = service.owned(project_id, current_user.id)
    if "language" in data:
        raise service.RoomError(
            "项目语言创建后固定。请创建或恢复同任务、另一语言的项目，原草稿与证据会保留。",
            409,
            "LANGUAGE_BOUND",
        )
    if "archived" in data:
        if type(data["archived"]) is not bool or "code" in data:
            raise service.RoomError("归档参数无效。")
        service.transition(
            project,
            data.get("revision"),
            archived=data["archived"],
            events=service.event(
                project, "archive", "归档项目" if data["archived"] else "恢复项目"
            ),
        )
    else:
        project = service.owned(project_id, current_user.id, writable=True)
        service.save_draft(project, data.get("code"), data.get("draft_revision"))
    return api_success({"project": service.serialize(project)})


@blueprint.post("/api/task-room/projects/<project_id>/freeze")
@login_required
def freeze(project_id):
    data = request.get_json()
    project = service.owned(project_id, current_user.id, writable=True)
    service.freeze(project, data.get("rules"), data.get("revision"))
    return api_success({"project": service.serialize(project)})


@blueprint.post("/api/task-room/projects/<project_id>/messages")
@login_required
@rate_limit(8, 60)
def message(project_id):
    data = request.get_json()
    project = service.owned(project_id, current_user.id, writable=True)
    service.request_ai(
        project,
        data.get("intent"),
        data.get("message"),
        data.get("code", project.code),
        data.get("operation_id"),
    )
    return api_success({"project": service.serialize(project)})


@blueprint.post("/api/task-room/projects/<project_id>/messages/<message_id>/apply")
@login_required
def apply(project_id, message_id):
    project = service.owned(project_id, current_user.id, writable=True)
    service.apply_proposal(project, message_id, request.get_json().get("draft_revision"))
    return api_success({"project": service.serialize(project)})


@blueprint.post("/api/task-room/projects/<project_id>/messages/<message_id>/undo")
@login_required
def undo(project_id, message_id):
    project = service.owned(project_id, current_user.id, writable=True)
    service.apply_proposal(project, message_id, request.get_json().get("draft_revision"), undo=True)
    return api_success({"project": service.serialize(project)})


@blueprint.post("/api/task-room/projects/<project_id>/run")
@login_required
@rate_limit(12, 60)
def run(project_id):
    data = request.get_json()
    project = service.owned(project_id, current_user.id, writable=True)
    # Reject non-finite JSON before it reaches the runner or database.
    json.dumps(data.get("input"), allow_nan=False)
    result = service.execute(
        project, data.get("code"), data.get("kind"), data.get("contract_id"), data.get("input")
    )
    return api_success({"project": service.serialize(project), "run": service.run_payload(result)})


@blueprint.post("/api/task-room/projects/<project_id>/deliver")
@login_required
def deliver(project_id):
    data = request.get_json()
    project = service.owned(project_id, current_user.id, writable=True)
    service.deliver(project, data.get("code"), data.get("contract_id"), data.get("revision"))
    return api_success({"project": service.serialize(project)})


@blueprint.post("/api/task-room/projects/<project_id>/changes")
@login_required
def changes(project_id):
    data = request.get_json()
    project = service.owned(project_id, current_user.id, writable=True)
    service.change(project, data.get("change_id"), data.get("revision"))
    return api_success({"project": service.serialize(project)})


@blueprint.get("/api/task-room/projects/<project_id>/export")
@login_required
def export(project_id):
    project = service.owned(project_id, current_user.id)
    return send_file(
        service.export_project(project),
        as_attachment=True,
        download_name=f"task-room-{project.id[:8]}.zip",
        mimetype="application/zip",
        max_age=0,
    )

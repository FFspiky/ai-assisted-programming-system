import json
from datetime import datetime, timezone

from flask import Blueprint, request
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from models import WorkshopProject, WorkshopRun, WorkshopSuggestion, WorkshopVersion, db
from routes.api_response import api_error, api_success
from routes.guards import rate_limit
from services.ai_client import AIClientError
from services.execute_runner import run_code
from services.workshop import (
    MAX_WORKSHOP_CODE,
    bounded_text,
    catalog_payload,
    fingerprint,
    generate_candidate,
    parse_trace,
)
from services.workshop_catalog import normalize_params, scene_spec

workshop_blueprint = Blueprint("workshop", __name__)


@workshop_blueprint.after_request
def private_creation_responses(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


def run_payload(run):
    return {
        "id": run.id,
        "scene": run.scene,
        "title": run.title,
        "code": run.code,
        "params": run.params,
        "trace": run.trace,
        "execution": run.execution,
        "provenance": run.provenance,
        "fingerprint": run.fingerprint,
        "created_at": run.created_at.isoformat() + "Z",
    }


def project_payload(project):
    return {
        "id": project.id,
        "title": project.title,
        "scene": project.scene,
        "revision": project.revision,
        "updated_at": project.updated_at.isoformat() + "Z",
    }


def creative_input(data):
    scene = data.get("scene")
    if not isinstance(scene, str):
        raise ValueError("请选择创作主题")
    scene_spec(scene)
    code = bounded_text(data.get("code"), MAX_WORKSHOP_CODE, "代码")
    params = normalize_params(scene, data.get("params"))
    return scene, code, params


@workshop_blueprint.get("/workshop/catalog")
def catalog():
    return api_success({"scenes": catalog_payload()})


@workshop_blueprint.post("/workshop/run")
@login_required
@rate_limit(12, 60)
def run_creation():
    data = request.get_json(silent=True) or {}
    try:
        scene, code, params = creative_input(data)
        title = bounded_text(data.get("title"), 80, "作品名称").strip()
    except ValueError as exc:
        return api_error("INVALID_CREATION", str(exc))
    provenance = {"kind": "user_edited"}
    spec = scene_spec(scene)
    if code == spec["code"]:
        provenance = {"kind": "built_in_code"}
    suggestion_id = data.get("suggestion_id")
    if suggestion_id is not None:
        if type(suggestion_id) is not int:
            return api_error("INVALID_CREATION", "AI 候选标识无效")
        suggestion = WorkshopSuggestion.query.filter_by(
            id=suggestion_id, user_id=current_user.id, scene=scene
        ).first()
        if not suggestion:
            return api_error("NOT_FOUND", "找不到这份 AI 候选", 404)
        exact = suggestion.result["code"] == code and suggestion.result["params"] == params
        provenance = {
            "kind": "ai_candidate" if exact else "edited_ai_candidate",
            "suggestion_id": suggestion.id,
            "generation": suggestion.result["generation"],
        }
    result = run_code(code, "python", json.dumps(params))
    if not result.get("success") or result.get("output_truncated") or result.get("error_truncated"):
        status = 503 if result.get("status") in {"Environment Error", "Busy"} else 422
        return api_error(
            "CREATION_RUN_FAILED",
            result.get("error") or "轨迹运行未完成，请检查代码",
            status,
            execution={"status": result.get("status"), "error": (result.get("error") or "")[:3000]},
        )
    try:
        trace = parse_trace(scene, result.get("output", ""))
    except ValueError as exc:
        return api_error("INVALID_TRACE", str(exc), 422)
    run = WorkshopRun(
        user_id=current_user.id,
        scene=scene,
        title=title,
        code=code,
        params=params,
        trace=trace,
        provenance=provenance,
        fingerprint=fingerprint(scene, code, params),
        execution={
            "backend": result["execution_backend"],
            "elapsed_ms": result.get("time"),
            "state": "completed",
        },
    )
    db.session.add(run)
    db.session.commit()
    return api_success({"run": run_payload(run)}, http_status=201)


@workshop_blueprint.post("/workshop/suggest")
@login_required
@rate_limit(5, 60)
def suggest_creation():
    data = request.get_json(silent=True) or {}
    try:
        scene, code, params = creative_input(data)
        prompt = bounded_text(data.get("prompt"), 1200, "创意描述").strip()
        result = generate_candidate(scene, code, params, prompt)
    except ValueError as exc:
        return api_error("INVALID_CREATION", str(exc))
    except AIClientError:
        return api_error(
            "AI_UNAVAILABLE", "AI 暂未返回可用候选，请稍后重试。你的代码仍然保留。", 502
        )
    suggestion = WorkshopSuggestion(
        user_id=current_user.id,
        scene=scene,
        prompt=prompt,
        base_fingerprint=fingerprint(scene, code, params),
        result=result,
    )
    db.session.add(suggestion)
    db.session.commit()
    return api_success(
        {
            "suggestion": {
                "id": suggestion.id,
                "base_fingerprint": suggestion.base_fingerprint,
                **result,
            }
        },
        http_status=201,
    )


@workshop_blueprint.get("/workshop/projects")
@login_required
def list_projects():
    projects = (
        WorkshopProject.query.filter_by(user_id=current_user.id)
        .order_by(WorkshopProject.updated_at.desc())
        .limit(50)
        .all()
    )
    return api_success({"projects": [project_payload(p) for p in projects]})


@workshop_blueprint.get("/workshop/projects/<int:project_id>")
@login_required
def get_project(project_id):
    project = WorkshopProject.query.filter_by(id=project_id, user_id=current_user.id).first()
    if not project:
        return api_error("NOT_FOUND", "找不到这件作品", 404)
    versions = (
        WorkshopVersion.query.filter_by(project_id=project.id)
        .order_by(WorkshopVersion.number.desc())
        .all()
    )
    run = db.session.get(WorkshopRun, versions[0].run_id)
    return api_success(
        {
            "project": project_payload(project),
            "run": run_payload(run),
            "palette": versions[0].palette,
            "versions": [
                {"id": v.id, "number": v.number, "created_at": v.created_at.isoformat() + "Z"}
                for v in versions
            ],
        }
    )


@workshop_blueprint.get("/workshop/projects/<int:project_id>/versions/<int:version_id>")
@login_required
def get_version(project_id, version_id):
    project = WorkshopProject.query.filter_by(id=project_id, user_id=current_user.id).first()
    version = (
        WorkshopVersion.query.filter_by(id=version_id, project_id=project_id).first()
        if project
        else None
    )
    if not version:
        return api_error("NOT_FOUND", "找不到这个作品版本", 404)
    return api_success(
        {
            "run": run_payload(db.session.get(WorkshopRun, version.run_id)),
            "number": version.number,
            "palette": version.palette,
        }
    )


@workshop_blueprint.post("/workshop/projects")
@login_required
@rate_limit(20, 60)
def save_creation():
    data = request.get_json(silent=True) or {}
    palette = data.get("palette", "lagoon")
    if palette not in ("lagoon", "sunrise", "mint"):
        return api_error("INVALID_CREATION", "画面配色无效")
    if type(data.get("run_id")) is not int:
        return api_error("INVALID_CREATION", "请先完成一次真实运行")
    run = WorkshopRun.query.filter_by(id=data["run_id"], user_id=current_user.id).first()
    if not run:
        return api_error("NOT_FOUND", "找不到这次运行", 404)
    try:
        title = bounded_text(data.get("title"), 80, "作品名称").strip()
    except ValueError as exc:
        return api_error("INVALID_CREATION", str(exc))
    project_id = data.get("project_id")
    if project_id is None:
        if WorkshopProject.query.filter_by(user_id=current_user.id).count() >= 50:
            return api_error("PROJECT_LIMIT", "最多保留 50 件作品，请在已有作品中保存新版本", 409)
        project = WorkshopProject(user_id=current_user.id, title=title, scene=run.scene, revision=1)
        db.session.add(project)
        db.session.flush()
    else:
        if type(project_id) is not int or type(data.get("revision")) is not int:
            return api_error("INVALID_CREATION", "作品版本标识无效")
        project = WorkshopProject.query.filter_by(id=project_id, user_id=current_user.id).first()
        if not project:
            return api_error("NOT_FOUND", "找不到这件作品", 404)
        if project.scene != run.scene:
            return api_error("SCENE_CONFLICT", "主题已改变，请存为新作品", 409)
        if project.revision >= 100:
            return api_error("VERSION_LIMIT", "该作品已有 100 个版本，请存为新作品", 409)
        updated = WorkshopProject.query.filter_by(
            id=project.id, user_id=current_user.id, revision=data["revision"]
        ).update(
            {
                WorkshopProject.revision: WorkshopProject.revision + 1,
                WorkshopProject.title: title,
                WorkshopProject.updated_at: datetime.now(timezone.utc),
            },
            synchronize_session=False,
        )
        if updated != 1:
            db.session.rollback()
            return api_error(
                "VERSION_CONFLICT", "另一页面已保存新版本，请重新打开作品后再保存", 409
            )
        db.session.refresh(project)
    db.session.add(
        WorkshopVersion(
            project_id=project.id, run_id=run.id, number=project.revision, palette=palette
        )
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return api_error("VERSION_CONFLICT", "作品版本已改变，请重新打开后再保存", 409)
    return api_success(
        {"project": project_payload(project)}, message="作品版本已保存", http_status=201
    )

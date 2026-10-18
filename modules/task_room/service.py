"""Owner-scoped workflow, immutable contracts, real execution and explicit AI proposals."""

import hashlib
import io
import json
import logging
import uuid
import zipfile
from datetime import timedelta, timezone

from sqlalchemy.exc import IntegrityError

from models import db
from services.ai_client import AIClientError
from services.execute_runner import run_code

from . import ai
from .catalog import build_contract, evaluate_input, get_scenario, validate_rules
from .languages import (
    compiled_harness,
    export_sources,
    interface_guide,
    local_instructions,
    normalize_language,
    scaffold,
)
from .models import TaskContract, TaskMessage, TaskProject, TaskRun, now

logger = logging.getLogger(__name__)


class RoomError(Exception):
    def __init__(self, message, status=400, code="TASK_ROOM_ERROR"):
        super().__init__(message)
        self.message, self.status, self.code = message, status, code


def fingerprint(code):
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def timestamp(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def bounded_text(value, name, limit, empty=False):
    if not isinstance(value, str) or len(value) > limit or (not empty and not value.strip()):
        raise RoomError(f"{name}须为{'非空' if not empty else ''}文本，最多 {limit} 字。")
    return value


def owned(project_id, user_id, writable=False):
    project = TaskProject.query.filter_by(id=project_id, user_id=user_id).first()
    if project is None:
        raise RoomError("项目不存在或无权访问。", 404, "NOT_FOUND")
    if writable and project.archived:
        raise RoomError("请先恢复此项目，再继续操作。", 409, "ARCHIVED")
    return project


def contracts(project):
    return TaskContract.query.filter_by(project_id=project.id).order_by(TaskContract.version).all()


def current_contract(project):
    return (
        TaskContract.query.filter_by(project_id=project.id)
        .order_by(TaskContract.version.desc())
        .first()
    )


def contract_payload(item):
    return {
        **item.snapshot,
        "id": item.id,
        "created_at": timestamp(item.created_at),
        "change_id": item.change_id,
    }


def run_payload(item):
    return {
        key: getattr(item, key)
        for key in (
            "id",
            "kind",
            "language",
            "contract_id",
            "contract_version",
            "code_hash",
            "code",
            "status",
            "passed",
            "total",
            "results",
            "execution",
        )
    } | {"created_at": timestamp(item.created_at)}


def serialize(project, full=True):
    recover_interrupted(project)
    versions = contracts(project)
    runs = (
        TaskRun.query.filter_by(project_id=project.id)
        .order_by(TaskRun.created_at, TaskRun.id)
        .all()
    )
    messages = (
        TaskMessage.query.filter_by(project_id=project.id)
        .order_by(TaskMessage.created_at, TaskMessage.id)
        .all()
    )
    data = {
        key: getattr(project, key)
        for key in (
            "id",
            "title",
            "scenario_id",
            "language",
            "state",
            "archived",
            "revision",
            "draft_revision",
            "delivery",
        )
    }
    data.update(
        created_at=timestamp(project.created_at),
        updated_at=timestamp(project.updated_at),
        stats={
            "contracts": len(versions),
            "runs": len(runs),
            "passed": sum(r.status == "passed" and r.kind == "acceptance" for r in runs),
            "changes": sum(bool(c.change_id) for c in versions),
            "messages": sum(m.role == "user" for m in messages),
        },
        contract=contract_payload(versions[-1]) if versions else None,
        language_guide=interface_guide(project.language),
    )
    if full:
        data.update(
            code=project.code,
            scenario={
                **get_scenario(project.scenario_id),
                "starter_code": scaffold(get_scenario(project.scenario_id), project.language),
            },
            contracts=[contract_payload(c) for c in versions],
            messages=[
                {
                    "id": m.id,
                    "role": m.role,
                    "intent": m.intent,
                    "content": m.content,
                    "model": m.model,
                    "payload": m.payload,
                    "created_at": timestamp(m.created_at),
                }
                for m in messages
            ],
            runs=[run_payload(r) for r in runs],
            events=project.events,
        )
    return data


def event(project, kind, title, details=None):
    return list(project.events or [])[-499:] + [
        {
            "id": uuid.uuid4().hex,
            "kind": kind,
            "title": title,
            "created_at": timestamp(now()),
            "details": details or {},
        }
    ]


def check_revision(value, expected):
    if type(value) is not int or value != expected:
        raise RoomError(
            "项目已在其他窗口更新，请刷新后重试；本地代码请先保留。", 409, "STALE_REVISION"
        )


def transition(project, revision, *, expected_draft=None, **fields):
    check_revision(revision, project.revision)
    query = TaskProject.query.filter_by(id=project.id, user_id=project.user_id, revision=revision)
    if expected_draft is not None:
        query = query.filter_by(draft_revision=expected_draft, archived=False, state="development")
    count = query.update(
        {**fields, "revision": revision + 1, "updated_at": now()}, synchronize_session=False
    )
    if count != 1:
        db.session.rollback()
        raise RoomError("项目状态已改变，请刷新后重试。", 409, "STALE_REVISION")
    db.session.commit()
    db.session.refresh(project)
    return project


def recover_interrupted(project):
    """A server restart must not leave a project permanently blocked by a run."""
    cutoff = (now() - timedelta(minutes=2)).replace(tzinfo=None)
    changed = TaskRun.query.filter(
        TaskRun.project_id == project.id, TaskRun.status == "running", TaskRun.created_at < cutoff
    ).update(
        {
            "status": "error",
            "execution": {"status": "Interrupted", "error": "上次执行已中断，请重新运行。"},
        },
        synchronize_session=False,
    )
    ai_cutoff = (now() - timedelta(minutes=5)).replace(tzinfo=None)
    pending = TaskMessage.query.filter(
        TaskMessage.project_id == project.id, TaskMessage.created_at < ai_cutoff
    ).all()
    for message in pending:
        if message.payload.get("state") == "running":
            changed += TaskMessage.query.filter(
                TaskMessage.id == message.id, TaskMessage.payload["state"].as_string() == "running"
            ).update(
                {
                    "content": "上次 AI 请求已中断，可重新发起。",
                    "payload": {**message.payload, "state": "failed"},
                },
                synchronize_session=False,
            )
    if changed:
        db.session.commit()


def create_project(user_id, scenario_id, language="python"):
    try:
        scenario = get_scenario(scenario_id)
    except (ValueError, TypeError, KeyError) as exc:
        raise RoomError("请选择有效任务。") from exc
    try:
        language = normalize_language(language)
    except ValueError as exc:
        raise RoomError("请选择 Python、C++ 或 Java。") from exc
    if TaskProject.query.filter_by(user_id=user_id).count() >= 100:
        raise RoomError("已达到 100 个项目的保存上限。", 409)
    project = TaskProject(
        user_id=user_id,
        scenario_id=scenario_id,
        language=language,
        title=scenario["title"],
        code=scaffold(scenario, language),
        events=[],
    )
    db.session.add(project)
    db.session.flush()
    project.events = event(
        project, "created", "接下任务", {"scenario_id": scenario_id, "language": language}
    )
    db.session.commit()
    return project


def save_draft(project, code, revision):
    bounded_text(code, "代码", 20000, empty=True)
    check_revision(revision, project.draft_revision)
    fields = {"code": code, "draft_revision": revision + 1, "updated_at": now()}
    if project.state == "delivered" and code != project.code:
        fields.update(
            state="development",
            delivery=None,
            revision=project.revision + 1,
            events=event(project, "reopened", "交付后修改代码 · 需要重新验收"),
        )
    count = TaskProject.query.filter_by(
        id=project.id, draft_revision=revision, revision=project.revision, archived=False
    ).update(fields, synchronize_session=False)
    if count != 1:
        db.session.rollback()
        raise RoomError("草稿已在其他窗口更改，请先复制本地代码再刷新。", 409, "STALE_DRAFT")
    db.session.commit()
    db.session.refresh(project)
    return project


def freeze(project, rules, revision):
    check_revision(revision, project.revision)
    if project.state != "discovery" or current_contract(project):
        raise RoomError("需求已经确认，后续调整请使用需求变更。", 409)
    normalized = validate_rules(project.scenario_id, rules)
    snapshot = build_contract(project.scenario_id, normalized, version=1)
    snapshot.update(
        language=project.language,
        starter_code=scaffold(get_scenario(project.scenario_id), project.language),
    )
    db.session.add(TaskContract(project_id=project.id, version=1, snapshot=snapshot))
    return transition(
        project,
        revision,
        state="development",
        events=event(project, "contract", "确认需求 · V1", {"rules": normalized}),
    )


def require_contract(project, contract_id):
    contract = current_contract(project)
    if not contract or contract_id != contract.id:
        raise RoomError("验收需求版本已改变，请刷新并使用当前需求。", 409, "STALE_CONTRACT")
    return contract


def build_harness():
    # User code is only executed inside run_code's networkless Docker container.
    # Expected outputs never enter the sandbox. stdout per case is captured so a
    # debug print cannot masquerade as the structured result used by the host.
    return """import contextlib, io, json, sys
PAYLOAD = json.load(sys.stdin)
SOURCE = PAYLOAD["code"]
INPUTS = PAYLOAD["inputs"]
rows = []
for index, data in enumerate(INPUTS):
    capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
            namespace = {"__name__": "task_solution"}
            exec(compile(SOURCE, "solution.py", "exec"), namespace)
            solution = namespace.get("solve")
            if not callable(solution):
                raise ValueError("请定义 solve(data) 函数")
            value = solution(data)
            json.dumps(value, allow_nan=False)
        rows.append({"index": index, "actual": value, "error": None})
    except BaseException as exc:
        rows.append({"index": index, "actual": None, "error": type(exc).__name__ + ": " + str(exc)[:1000]})
print(json.dumps({"results": rows}, ensure_ascii=False, allow_nan=False))
"""


def same_json(actual, expected):
    # Python considers True == 1; the public JSON contract does not.
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            same_json(actual[k], v) for k, v in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            same_json(a, e) for a, e in zip(actual, expected, strict=True)
        )
    return actual == expected


def execute(project, code, kind, contract_id, custom_input=None):
    recover_interrupted(project)
    bounded_text(code, "代码", 20000)
    try:
        runner_source = (
            build_harness()
            if project.language == "python"
            else compiled_harness(code, project.language)
        )
    except ValueError as exc:
        raise RoomError(str(exc), 400, "SOURCE_CONTRACT") from exc
    if kind not in {"acceptance", "custom"}:
        raise RoomError("运行类型无效。")
    contract = require_contract(project, contract_id)
    if TaskRun.query.filter_by(project_id=project.id).count() >= 100:
        raise RoomError("本项目已达到 100 次运行上限，请新建项目继续。", 409)
    if TaskRun.query.filter_by(project_id=project.id, status="running").first():
        raise RoomError("本项目已有任务正在执行，请稍后刷新。", 409, "RUNNING")
    if kind == "acceptance":
        cases = contract.snapshot["cases"]
    else:
        if len(json.dumps(custom_input, ensure_ascii=False, allow_nan=False)) > 8000:
            raise RoomError("自定义输入最多 8000 字。")
        expected = evaluate_input(project.scenario_id, contract.snapshot["rules"], custom_input)
        cases = [
            {"id": "custom", "name": "自定义用例", "input": custom_input, "expected": expected}
        ]
    run = TaskRun(
        project_id=project.id,
        contract_id=contract.id,
        contract_version=contract.version,
        kind=kind,
        language=project.language,
        code=code,
        code_hash=fingerprint(code),
        total=len(cases),
    )
    db.session.add(run)
    db.session.commit()
    try:
        inputs = [c["input"] for c in cases]
        is_python = project.language == "python"
        execution = run_code(
            runner_source,
            project.language,
            input_text=json.dumps(
                {"code": code, "inputs": inputs} if is_python else inputs,
                ensure_ascii=False,
                allow_nan=False,
            ),
        )
        # Preserve the real runner's backend/status/timings; never label an
        # environment failure as a wrong answer or fabricate a successful run.
        safe_execution = {k: v for k, v in execution.items() if k != "output"}
        results = []
        if execution.get("success"):
            packet = json.loads(execution.get("output", ""))
            rows = packet["results"]
            if not isinstance(rows, list) or len(rows) != len(cases):
                raise ValueError("结果数量异常")
            for index, (case, row) in enumerate(zip(cases, rows, strict=True)):
                if (
                    not isinstance(row, dict)
                    or type(row.get("index")) is not int
                    or row["index"] != index
                    or "actual" not in row
                ):
                    raise ValueError("结果格式异常")
                error = row.get("error")
                passed = error is None and same_json(row["actual"], case["expected"])
                results.append(
                    {
                        **case,
                        "actual": row["actual"],
                        "error": str(error)[:1000] if error else None,
                        "passed": passed,
                    }
                )
            run.passed = sum(r["passed"] for r in results)
            run.status = "passed" if run.passed == run.total else "failed"
        else:
            run.status = "error"
        run.results, run.execution = results, safe_execution
    except (ValueError, TypeError, KeyError, RecursionError):
        run.status = "error"
        run.execution = {
            "status": "Protocol Error",
            "error": "程序未返回完整有效的 JSON 结果；请检查返回值、输出量和运行记录。",
        }
    except Exception:
        run.status = "error"
        run.execution = {"status": "Environment Error", "error": "执行环境暂不可用，请稍后重试。"}
    db.session.commit()
    return run


def deliver(project, code, contract_id, revision):
    bounded_text(code, "代码", 20000)
    contract = require_contract(project, contract_id)
    check_revision(revision, project.revision)
    if project.state == "delivered":
        raise RoomError("当前需求已经交付，可发起下一次变更。", 409)
    code_hash = fingerprint(code)
    if fingerprint(project.code) != code_hash:
        raise RoomError("请先保存当前代码再交付。", 409, "UNSAVED_DRAFT")
    run = (
        TaskRun.query.filter_by(
            project_id=project.id,
            contract_id=contract.id,
            code_hash=code_hash,
            kind="acceptance",
            language=project.language,
        )
        .order_by(TaskRun.created_at.desc(), TaskRun.id.desc())
        .first()
    )
    if not run or run.status != "passed" or run.language != project.language:
        raise RoomError(
            "当前代码须通过当前需求的全部验收用例后才能交付。", 409, "ACCEPTANCE_REQUIRED"
        )
    return transition(
        project,
        revision,
        expected_draft=project.draft_revision,
        state="delivered",
        delivery={
            "contract_id": contract.id,
            "code_hash": code_hash,
            "language": project.language,
            "run_id": run.id,
            "at": timestamp(now()),
        },
        events=event(
            project,
            "delivered",
            f"完成交付 · V{contract.version}",
            {"run_id": run.id, "code_hash": code_hash},
        ),
    )


def change(project, change_id, revision):
    check_revision(revision, project.revision)
    previous = current_contract(project)
    if project.state != "delivered" or previous is None:
        raise RoomError("请先完成当前需求的验收和交付，再处理客户变更。", 409)
    if TaskContract.query.filter_by(project_id=project.id, change_id=change_id).first():
        raise RoomError("这项变更已处理，请选择其他变更。", 409)
    scenario = get_scenario(project.scenario_id)
    selected = next((c for c in scenario["changes"] if c["id"] == change_id), None)
    if selected is None:
        raise RoomError("变更请求不存在。")
    rules = validate_rules(project.scenario_id, {**previous.snapshot["rules"], **selected["patch"]})
    if rules == previous.snapshot["rules"]:
        raise RoomError("当前需求已经包含这项规则，无需重复变更。", 409)
    version = previous.version + 1
    snapshot = build_contract(project.scenario_id, rules, version=version)
    snapshot.update(language=project.language, starter_code=scaffold(scenario, project.language))
    db.session.add(
        TaskContract(
            project_id=project.id,
            version=version,
            snapshot=snapshot,
            change_id=change_id,
        )
    )
    return transition(
        project,
        revision,
        state="development",
        delivery=None,
        events=event(
            project,
            "change",
            f"客户变更 · V{version}",
            {
                "change_id": change_id,
                "message": selected["message"],
                "before": previous.snapshot["rules"],
                "after": rules,
            },
        ),
    )


def request_ai(project, intent, message, code, operation_id):
    if intent not in {"customer", "coach", "review"}:
        raise RoomError("请选择客户沟通、开发教练或项目复盘。")
    bounded_text(message, "消息", 2000)
    bounded_text(code, "代码", 20000, empty=True)
    bounded_text(operation_id, "请求标识", 64)
    existing = TaskMessage.query.filter_by(project_id=project.id, operation_id=operation_id).first()
    if existing:
        if existing.payload.get("state") == "running":
            raise RoomError("该请求仍在处理中，请稍后刷新。", 409, "AI_RUNNING")
        if existing.payload.get("state") == "failed":
            raise RoomError(
                "该次 AI 请求未完成，请使用新的请求标识重新发起。", 503, "AI_UNAVAILABLE"
            )
        return project
    if intent == "coach" and not current_contract(project):
        raise RoomError("请先确认需求，再请开发教练协助。", 409)
    if intent == "review" and not TaskRun.query.filter_by(project_id=project.id).first():
        raise RoomError("请先完成至少一次实际运行，再进行复盘。", 409)
    if TaskMessage.query.filter_by(project_id=project.id).count() >= 200:
        raise RoomError("本项目已达到 100 轮沟通上限，请新建项目继续。", 409)
    contract = current_contract(project)
    response = TaskMessage(
        project_id=project.id,
        role="assistant",
        intent=intent,
        content="",
        operation_id=operation_id,
        payload={
            "state": "running",
            "contract_id": contract.id if contract else None,
            "base_hash": fingerprint(code),
            "base_code": code,
            "language": project.language,
        },
    )
    db.session.add(
        TaskMessage(
            project_id=project.id,
            role="user",
            intent=intent,
            content=message,
            payload={"state": "complete"},
        )
    )
    db.session.add(response)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise RoomError("请求已提交，请刷新查看结果。", 409, "AI_RUNNING") from exc
    try:
        answer = ai.respond(serialize(project), intent, message, code)
        response.content, response.model = answer["reply"], answer["model"]
        payload = {
            **response.payload,
            "state": "complete",
            "prompt_version": answer["prompt_version"],
        }
        if answer["code"]:
            payload.update(
                code=answer["code"], candidate_hash=fingerprint(answer["code"]), state="pending"
            )
        response.payload = payload
        db.session.commit()
    except Exception as exc:
        if not isinstance(exc, AIClientError):
            logger.warning("Task room AI adapter failed (%s)", type(exc).__name__)
        response.content = "AI 服务暂时无法完成请求。你的需求和代码仍已保留，可重新发起。"
        response.payload = {**response.payload, "state": "failed"}
        db.session.commit()
        raise RoomError(
            "AI 服务暂时不可用或回复格式异常，请稍后重试。", 503, "AI_UNAVAILABLE"
        ) from exc
    return project


def apply_proposal(project, message_id, draft_revision, undo=False):
    suggestion = TaskMessage.query.filter_by(
        id=message_id, project_id=project.id, role="assistant"
    ).first()
    if not suggestion or not suggestion.payload.get("code"):
        raise RoomError("候选代码不存在。", 404)
    payload = suggestion.payload
    if payload.get("language", "python") != project.language:
        raise RoomError("候选代码的语言与当前项目不同，请重新生成。", 409, "STALE_PROPOSAL")
    require_contract(project, payload.get("contract_id"))
    check_revision(draft_revision, project.draft_revision)
    allowed = {"applied"} if undo else {"pending", "undone"}
    expected = payload["candidate_hash"] if undo else payload["base_hash"]
    if payload.get("state") not in allowed or fingerprint(project.code) != expected:
        raise RoomError(
            "代码已改变，候选代码或撤销操作已过期；请保留当前草稿。", 409, "STALE_PROPOSAL"
        )
    target = payload["base_code"] if undo else payload["code"]
    fields = {"code": target, "draft_revision": draft_revision + 1, "updated_at": now()}
    if project.state == "delivered" and target != project.code:
        fields.update(
            state="development",
            delivery=None,
            revision=project.revision + 1,
            events=event(project, "reopened", "采用候选代码 · 需要重新验收"),
        )
    check = TaskProject.query.filter_by(
        id=project.id, draft_revision=draft_revision, revision=project.revision, archived=False
    ).update(fields, synchronize_session=False)
    if check != 1:
        db.session.rollback()
        raise RoomError("草稿已改变，请刷新后重试。", 409, "STALE_DRAFT")
    suggestion.payload = {**payload, "state": "undone" if undo else "applied"}
    db.session.commit()
    db.session.refresh(project)
    return project


def export_project(project):
    data = serialize(project)
    report = [
        f"# {project.title}",
        "",
        "AI 实战任务室 · 项目档案",
        "",
        f"项目：{project.id}",
        f"当前状态：{project.state}",
        "",
        "## 需求与变更",
    ]
    for contract in data["contracts"]:
        report += ["", f"### V{contract['version']}", contract["spec"], ""]
        report += [f"- {r['label']}：{r['text']}" for r in contract["rule_labels"]]
    report += [
        "",
        "## 实际运行记录",
        "",
        "验收只覆盖已列出的用例，不代表所有输入均正确。自定义运行不能替代完整验收。",
        "",
    ]
    report += [
        f"- {r['created_at']} · V{r['contract_version']} · {r['kind']} · {r['status']} · {r['passed']}/{r['total']} · {r['execution'].get('execution_backend', '无执行后端记录')} · 代码 {r['code_hash'][:12]}"
        for r in data["runs"]
    ]
    report += ["", "## AI 沟通与复盘", ""]
    report += [
        f"### {m['intent']} · {m['role']}\n{m['content']}\n"
        for m in data["messages"]
        if m["content"]
    ]
    report += [
        "",
        "## 本地使用",
        "",
        local_instructions(project.language),
        "输入输出格式、全部用例和每次运行代码快照见 project.json。网站中的验收始终在 Docker 隔离环境中执行。",
    ]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.md", "\n".join(report))
        for filename, content in export_sources(project.code, project.language).items():
            archive.writestr(filename, content)
        archive.writestr(
            "inputs.json",
            json.dumps(
                [case["input"] for case in (data["contract"] or {}).get("cases", [])],
                ensure_ascii=False,
                indent=2,
            ),
        )
        archive.writestr(
            "project.json", json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
        )
        if data["contract"]:
            archive.writestr(
                "acceptance.json", json.dumps(data["contract"], ensure_ascii=False, indent=2)
            )
    buffer.seek(0)
    return buffer

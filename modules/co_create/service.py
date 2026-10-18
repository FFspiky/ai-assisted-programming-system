"""Owner-scoped, revision-checked creation with immutable execution evidence."""

import ast
import base64
import copy
import hashlib
import json
import uuid
from datetime import datetime, timezone

from models import db
from services.ai_client import AIClientError
from services.execute_runner import run_code

from . import ai, problem_service
from .catalog import (
    IMPLEMENTATIONS,
    evaluate,
    get_scenario,
    validate_input,
    validate_output,
)
from .models import CoCreateSession, now


class CreationError(Exception):
    def __init__(self, message, status=400, code="CO_CREATE_ERROR"):
        super().__init__(message)
        self.message, self.status, self.code = message, status, code


def ident():
    return uuid.uuid4().hex


def same_output(actual, expected):
    # Python equates True with 1; output contracts require the JSON value types too.
    return json.dumps(
        actual,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ) == json.dumps(
        expected,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


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


def serialize(row, full=True):
    recover_interrupted(row)
    if problem_service.is_problem(row):
        return problem_service.serialize(row, full)
    result = {k: getattr(row, k) for k in ("id", "mode", "scenario_id", "title", "revision")}
    result.update(created_at=stamp(row.created_at), updated_at=stamp(row.updated_at))
    result.update(problem_id=None, language="python", legacy=True)
    if full:
        result.update(state=copy.deepcopy(row.state), scenario=get_scenario(row.scenario_id))
    return result


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


def create(user_id, mode, scenario_id=None, **data):
    if data.get("problem_id") is not None:
        return problem_service.create(user_id, mode, **data)
    if mode not in {"examples", "review"}:
        raise CreationError("请选择以例造程序或代码质检。")
    scenario = get_scenario(scenario_id)
    if CoCreateSession.query.filter_by(user_id=user_id).count() >= 80:
        raise CreationError("最多保存 80 条创作记录，请继续使用已有记录。")
    wrong_rule = next(
        r["id"] for r in scenario["rule_options"] if r["id"] != scenario["review_rule"]["id"]
    )
    state = {
        "examples": scenario["seed_examples"],
        "generations": [],
        "current_generation_id": None,
        "selected": None,
        "runs": [],
        "events": [],
        "review": {
            "rule_id": scenario["review_rule"]["id"],
            "code": IMPLEMENTATIONS[(scenario_id, wrong_rule)],
            "source": "teaching",
            "model": None,
            "judgment": "",
            "prediction": None,
            "prediction_saved": False,
            "prediction_input": None,
            "prediction_code_revision": None,
            "reflection": "",
            "evidence": [],
            "code_revision": 0,
            "history": [],
            "verified": False,
        },
    }
    row = CoCreateSession(
        user_id=user_id,
        mode=mode,
        scenario_id=scenario_id,
        title=scenario["title"],
        state=state,
    )
    db.session.add(row)
    db.session.commit()
    return row


def require_mode(row, mode):
    if row.mode != mode:
        raise CreationError("此操作不适用于当前创作模式。")


def update_examples(row, revision, data):
    if problem_service.is_problem(row):
        return problem_service.update_examples(row, revision, data)
    require_mode(row, "examples")
    check_revision(row, revision)
    state = copy.deepcopy(row.state)
    if data.get("action") == "delete_example":
        key = data.get("example_id")
        existing = [e for e in state["examples"] if e["id"] != key]
        if len(existing) == len(state["examples"]):
            raise CreationError("例子不存在。", 404, "NOT_FOUND")
        if not existing:
            raise CreationError("至少保留一个例子。")
        state["examples"] = existing
    elif data.get("action") == "upsert_example":
        example = data.get("example")
        if not isinstance(example, dict) or "input" not in example or "expected" not in example:
            raise CreationError("请填写输入与期望输出。")
        value = validate_input(row.scenario_id, example["input"])
        expected = validate_output(row.scenario_id, example["expected"])
        key = example.get("id")
        if key is not None and not any(e["id"] == key for e in state["examples"]):
            raise CreationError("待编辑的例子不存在。", 404, "NOT_FOUND")
        if key is None and len(state["examples"]) >= 12:
            raise CreationError("最多保留 12 个例子。")
        for old in state["examples"]:
            if old["id"] != key and old["input"] == value:
                raise CreationError("这个输入已有例子，请编辑它以避免重复或矛盾。")
        replacement = {"id": key or ident(), "input": value, "expected": expected}
        state["examples"] = [replacement if e["id"] == key else e for e in state["examples"]]
        if key is None:
            state["examples"].append(replacement)
    else:
        raise CreationError("未知例子操作。")
    state["current_generation_id"], state["selected"] = None, None
    return commit(row, revision, state, "更新例子，原候选保留为历史记录")


def validate_code(code):
    code = text(code, "Python 代码", 6000)
    try:
        tree = ast.parse(code)
        if not any(isinstance(n, ast.FunctionDef) and n.name == "solve" for n in tree.body):
            raise SyntaxError("需要 def solve(data)")
    except (SyntaxError, RecursionError, MemoryError) as exc:
        raise CreationError("请提供包含 def solve(data) 的有效 Python 代码。") from exc
    return code


def execute(code, values):
    """The source is encoded and only compiled/executed inside the Docker runner."""
    validate_code(code)
    marker = "CO_CREATE_RESULT_" + ident() + ":"
    encoded = base64.b64encode(code.encode()).decode()
    wrapper = f"""import base64, contextlib, io, json, sys
namespace = {{"__name__": "candidate"}}
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(base64.b64decode({encoded!r}), "candidate.py", "exec"), namespace)
values = json.loads(sys.stdin.read())
results = []
for value in values:
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            output = namespace["solve"](value)
            json.dumps(output, allow_nan=False)
        results.append({{"success": True, "output": output}})
    except BaseException as exc:
        results.append({{"success": False, "error": type(exc).__name__ + ": " + str(exc)[:240]}})
print({marker!r} + json.dumps(results, ensure_ascii=False, allow_nan=False))
"""
    result = run_code(wrapper, "Python", input_text=json.dumps(values, ensure_ascii=False))
    execution = {k: result.get(k) for k in ("status", "execution_backend", "time")}
    if not result.get("success") or result.get("execution_backend") != "docker":
        return [
            {
                "success": False,
                "status": result.get("status", "Environment Error"),
                "error": (result.get("error") or "隔离执行未成功。")[:600],
            }
            for _ in values
        ], execution
    try:
        output = result.get("output", "")
        payload = next(
            line[len(marker) :] for line in output.splitlines() if line.startswith(marker)
        )
        if len(payload) > 18000:
            raise ValueError("size")
        outcomes = json.loads(
            payload, parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s))
        )
        if not isinstance(outcomes, list) or len(outcomes) != len(values):
            raise ValueError("count")
        for item in outcomes:
            if not isinstance(item, dict) or type(item.get("success")) is not bool:
                raise ValueError("outcome")
            if item["success"]:
                if "output" not in item or len(json.dumps(item["output"], allow_nan=False)) > 4000:
                    raise ValueError("output")
                item["status"] = "Accepted"
            else:
                item["status"] = "Runtime Error"
                item["error"] = str(item.get("error", "候选执行失败。"))[:600]
        return outcomes, execution
    except (ValueError, TypeError, StopIteration, RecursionError):
        return [
            {
                "success": False,
                "status": "Invalid Output",
                "error": "候选未返回合法的 JSON 结果。",
            }
            for _ in values
        ], execution


def source_check(source):
    if source not in {"teaching", "ai"}:
        raise CreationError("请明确选择教学样例或真实 AI。")


def generate(row, revision, source):
    if problem_service.is_problem(row):
        return problem_service.generate(row, revision, source)
    require_mode(row, "examples")
    check_revision(row, revision)
    source_check(source)
    state = copy.deepcopy(row.state)
    scenario = get_scenario(row.scenario_id)
    examples = state["examples"]
    rules = [
        rule
        for rule in scenario["rule_options"]
        if all(
            same_output(evaluate(row.scenario_id, rule["id"], e["input"]), e["expected"])
            for e in examples
        )
    ]
    generation = {
        "id": ident(),
        "source": source,
        "model": None,
        "status": "running",
        "candidates": [],
        "behavior_difference": None,
        "error": None,
        "examples": copy.deepcopy(examples),
        "created_at": stamp(now()),
    }
    state["generations"] = state["generations"][-39:] + [generation]
    state["current_generation_id"], state["selected"] = generation["id"], None
    commit(row, revision, state, "开始生成并隔离验证候选")
    reserved_revision = row.revision
    try:
        if not rules:
            raise CreationError(
                "例子不符合当前场景的两种规则。请检查期望输出；当前版本只探索页面列出的规则。"
            )
        if source == "ai":
            proposed, model = ai.generate(scenario, rules, examples)
            generation["model"] = model
        else:
            proposed = [
                {
                    "rule_id": r["id"],
                    "code": IMPLEMENTATIONS[(row.scenario_id, r["id"])],
                    "explanation": "预置教学程序；来源不是 AI。",
                }
                for r in rules
            ]
        rule_lookup = {r["id"]: r for r in rules}
        probe_outputs = []
        for proposed_candidate in proposed:
            rule = rule_lookup[proposed_candidate["rule_id"]]
            code = validate_code(proposed_candidate["code"])
            values = [e["input"] for e in examples] + [scenario["probe"]]
            expected = [e["expected"] for e in examples] + [
                evaluate(row.scenario_id, rule["id"], scenario["probe"])
            ]
            outcomes, execution = execute(code, values)
            cases = [
                {
                    "input": value,
                    "expected": answer,
                    **outcome,
                    "passed": outcome.get("success") is True
                    and same_output(outcome.get("output"), answer),
                    "kind": "example" if i < len(examples) else "rule_probe",
                }
                for i, (value, answer, outcome) in enumerate(
                    zip(values, expected, outcomes, strict=True)
                )
            ]
            candidate = {
                "id": ident(),
                "rule_id": rule["id"],
                "label": rule["label"],
                "code": code,
                "explanation": proposed_candidate.get("explanation", ""),
                "source": source,
                "model": generation["model"],
                "verified": all(c["passed"] for c in cases),
                "verification": {
                    "cases": cases,
                    "passed": sum(c["passed"] for c in cases),
                    "total": len(cases),
                    "execution": execution,
                },
                "code_hash": hashlib.sha256(code.encode()).hexdigest(),
            }
            generation["candidates"].append(candidate)
            probe_outputs.append(outcomes[-1])
        verified = all(c["verified"] for c in generation["candidates"])
        generation["status"] = "verified" if verified else "failed"
        generation["behavior_difference"] = {
            "input": scenario["probe"],
            "outputs": probe_outputs,
            "different": len(probe_outputs) > 1
            and all(o.get("success") for o in probe_outputs)
            and not same_output(probe_outputs[0].get("output"), probe_outputs[1].get("output")),
            "verified": verified,
        }
        if not verified:
            generation["error"] = "候选没有全部通过真实隔离验证，请查看失败证据。"
    except AIClientError:
        generation["status"], generation["error"] = (
            "failed",
            "真实 AI 请求失败或回复无效。本次没有生成可用 AI 候选；可重试或明确选择教学样例。",
        )
    except (CreationError, ValueError, TypeError) as exc:
        generation["status"], generation["error"] = "failed", str(exc)[:500]
    current = copy.deepcopy(row.state)
    current["generations"] = [
        generation if g["id"] == generation["id"] else g for g in current["generations"]
    ]
    return commit(
        row,
        reserved_revision,
        current,
        "候选验证完成" if generation["status"] == "verified" else "候选生成或验证失败",
    )


def current_generation(row, state=None):
    state = state or row.state
    generation = next(
        (g for g in state["generations"] if g["id"] == state["current_generation_id"]),
        None,
    )
    if generation is None or generation["status"] != "verified":
        raise CreationError("请先生成并验证当前例子对应的候选。", 409, "NO_VERIFIED_CANDIDATE")
    return generation


def compare(row, revision, value, **data):
    if problem_service.is_problem(row):
        return problem_service.compare(row, revision, value, **data)
    require_mode(row, "examples")
    check_revision(row, revision)
    value = validate_input(row.scenario_id, value)
    generation = current_generation(row)
    # Reserve a revision before lengthy container work. Any newer edit invalidates completion.
    commit(row, revision, row.state, "开始对照运行")
    reserved = row.revision
    results = []
    for candidate in generation["candidates"]:
        outcomes, execution = execute(candidate["code"], [value])
        results.append({"candidate_id": candidate["id"], **outcomes[0], "execution": execution})
    run = {
        "id": ident(),
        "kind": "compare",
        "input": value,
        "results": results,
        "different": len(results) > 1
        and all(r.get("success") for r in results)
        and not same_output(results[0].get("output"), results[1].get("output")),
        "generation_id": generation["id"],
        "created_at": stamp(now()),
    }
    state = copy.deepcopy(row.state)
    state["runs"] = state["runs"][-79:] + [run]
    commit(row, reserved, state, "保存对照运行证据")
    return row, run


def select(row, revision, generation_id, candidate_id):
    if problem_service.is_problem(row):
        return problem_service.select(row, revision, generation_id, candidate_id)
    require_mode(row, "examples")
    check_revision(row, revision)
    generation = current_generation(row)
    if generation["id"] != generation_id:
        raise CreationError("历史候选已经过期，请选择当前例子的候选。", 409, "STALE_CANDIDATE")
    candidate = next(
        (c for c in generation["candidates"] if c["id"] == candidate_id and c["verified"]),
        None,
    )
    if candidate is None:
        raise CreationError("候选不存在或尚未验证。")
    state = copy.deepcopy(row.state)
    state["selected"] = {
        "generation_id": generation_id,
        "candidate_id": candidate_id,
        "rule_id": candidate["rule_id"],
        "label": candidate["label"],
        "confirmed_at": stamp(now()),
    }
    return commit(row, revision, state, "确认当前程序规则")


def save_review(row, revision, data):
    if problem_service.is_problem(row):
        return problem_service.save_review(row, revision, data)
    require_mode(row, "review")
    check_revision(row, revision)
    state = copy.deepcopy(row.state)
    review = state["review"]
    if "judgment" in data:
        if data["judgment"] not in {"correct", "incorrect", "unsure"}:
            raise CreationError("请选择你的判断。")
        review["judgment"] = data["judgment"]
    if "reflection" in data:
        review["reflection"] = text(data["reflection"], "反思", 2000, empty=True)
    if "code" in data:
        code = validate_code(data["code"])
        if code != review["code"]:
            review["history"] = review["history"][-19:] + [
                {
                    "code": review["code"],
                    "code_revision": review["code_revision"],
                    "source": review["source"],
                    "model": review["model"],
                }
            ]
            review.update(
                code=code,
                code_revision=review["code_revision"] + 1,
                source="student",
                model=None,
                verified=False,
            )
            review.update(
                prediction_saved=False,
                prediction_input=None,
                prediction_code_revision=None,
            )
    if "prediction" in data:
        validate_output(row.scenario_id, data["prediction"])
        if "prediction_input" not in data:
            raise CreationError("保存预测时请同时提供对应的反例输入。")
        prediction_input = validate_input(row.scenario_id, data["prediction_input"])
        review.update(
            prediction=copy.deepcopy(data["prediction"]),
            prediction_saved=True,
            prediction_input=prediction_input,
            prediction_code_revision=review["code_revision"],
        )
    return commit(row, revision, state, "保存质检判断与修订")


def review_run(row, revision, value, **data):
    if problem_service.is_problem(row):
        return problem_service.review_run(row, revision, value, **data)
    require_mode(row, "review")
    check_revision(row, revision)
    value = validate_input(row.scenario_id, value)
    review = copy.deepcopy(row.state["review"])
    if not review["judgment"] or not review["prediction_saved"]:
        raise CreationError("请先保存你的判断与预测输出，再运行反例。")
    if review.get("prediction_code_revision") != review["code_revision"] or not same_output(
        review.get("prediction_input"), value
    ):
        raise CreationError(
            "输入或代码已变化，请为当前输入与代码重新保存预测。",
            409,
            "STALE_PREDICTION",
        )
    commit(row, revision, row.state, "开始质检反例运行")
    reserved = row.revision
    outcomes, execution = execute(review["code"], [value])
    outcome = outcomes[0]
    expected = evaluate(row.scenario_id, review["rule_id"], value)
    run = {
        "id": ident(),
        "kind": "review",
        "input": value,
        "expected": expected,
        "actual": outcome.get("output"),
        "prediction": review["prediction"],
        "judgment": review["judgment"],
        "passed": outcome.get("success") is True and same_output(outcome.get("output"), expected),
        "prediction_matched": outcome.get("success") is True
        and same_output(outcome.get("output"), review["prediction"]),
        "success": outcome.get("success"),
        "error": outcome.get("error"),
        "status": outcome.get("status"),
        "execution": execution,
        "code_revision": review["code_revision"],
        "code_hash": hashlib.sha256(review["code"].encode()).hexdigest(),
        "created_at": stamp(now()),
    }
    state = copy.deepcopy(row.state)
    state["runs"] = state["runs"][-79:] + [run]
    state["review"]["evidence"] = state["review"]["evidence"][-39:] + [run]
    # A single passing example is evidence for that example, not a proof of global correctness.
    state["review"]["verified"] = False
    commit(row, reserved, state, "保存真实质检证据")
    return row, run


def generate_review(row, revision, source):
    if problem_service.is_problem(row):
        return problem_service.generate(row, revision, source, review=True)
    require_mode(row, "review")
    check_revision(row, revision)
    source_check(source)
    scenario = get_scenario(row.scenario_id)
    other = next(r for r in scenario["rule_options"] if r["id"] != scenario["review_rule"]["id"])
    state = copy.deepcopy(row.state)
    commit(row, revision, state, "开始准备待质检候选")
    reserved = row.revision
    review = state["review"]
    if source == "ai":
        try:
            proposed, model = ai.generate(scenario, [other], scenario["seed_examples"])
            code = validate_code(proposed[0]["code"])
        except (AIClientError, CreationError, ValueError, TypeError):
            state["review"]["generation_error"] = "真实 AI 请求失败或回复无效；原候选保持不变。"
            return commit(row, reserved, state, "质检候选生成失败")
    else:
        code, model = IMPLEMENTATIONS[(row.scenario_id, other["id"])], None
    review["history"] = review["history"][-19:] + [
        {
            "code": review["code"],
            "code_revision": review["code_revision"],
            "source": review["source"],
            "model": review["model"],
        }
    ]
    review.update(
        code=code,
        code_revision=review["code_revision"] + 1,
        source=source,
        model=model,
        judgment="",
        prediction=None,
        prediction_saved=False,
        prediction_input=None,
        prediction_code_revision=None,
        reflection="",
        verified=False,
        generation_error=None,
    )
    return commit(row, reserved, state, "准备待质检候选；尚未执行")

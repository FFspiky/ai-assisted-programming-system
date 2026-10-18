"""Problem-linked creation; all program and reference execution stays in Docker.

Only public problem snapshots and public/redacted execution evidence are persisted.
Private answers and reference source never enter a session or an AI request.
"""

import copy
import hashlib
import json
from pathlib import Path

from config import MAX_CODE_CHARS, MAX_STDIN_CHARS, SUPPORTED_LANGUAGES
from models import Problem, Submission, db
from services.ai_client import AIClientError
from services.judge import outputs_match
from services.language_support import language_options, normalize_language

from . import ai
from . import service as core
from .models import CoCreateSession, now

ROOT = Path(__file__).resolve().parents[2]
UNSET = object()


def is_problem(row):
    return (row.state or {}).get("kind") == "problem"


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def _cases(problem):
    return problem.test_cases.order_by("id").all()


def _fingerprint(problem, cases):
    return _digest(
        {
            "id": problem.id,
            "title": problem.title,
            "description": problem.description,
            "judge_mode": problem.judge_mode,
            "cases": [
                {
                    "input": c.input_data,
                    "output": c.expected_output,
                    "public": c.is_public,
                }
                for c in cases
            ],
        }
    )


def _reference(problem, cases):
    """An ID alone cannot authorize a bundled reference after an admin edits a problem."""
    try:
        records = json.loads((ROOT / "data/problem_library.json").read_text(encoding="utf-8"))
        canonical = next((p for p in records if p["id"] == problem.id), None)
        if canonical is None:
            return None
        current = {
            "id": problem.id,
            "title": problem.title,
            "description": problem.description,
            "judge_mode": problem.judge_mode,
            "cases": [
                {"input": c.input_data, "output": c.expected_output, "public": c.is_public}
                for c in cases
            ],
        }
        expected = {k: canonical[k] for k in current}
        if _digest(current) != _digest(expected):
            return None
        references = json.loads(
            (ROOT / "data/reference_solutions.json").read_text(encoding="utf-8")
        )
        source = references.get(problem.id)
        return source if isinstance(source, str) and source.strip() else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def problem_snapshot(problem):
    cases = _cases(problem)
    return {
        "id": problem.id,
        "title": problem.title,
        "description": problem.description,
        "difficulty": problem.difficulty,
        "category": problem.category,
        "tags": copy.deepcopy(problem.tags or []),
        "source": problem.source,
        "judge_mode": problem.judge_mode,
        "fingerprint": _fingerprint(problem, cases),
        "public_examples": [
            {
                "id": f"official-{c.id}",
                "input": c.input_data,
                "expected": c.expected_output,
                "source": "official",
                "readonly": True,
            }
            for c in cases
            if c.is_public
        ],
        "reference_available": _reference(problem, cases) is not None,
        "case_count": len(cases),
    }


def live_problem(row):
    problem = db.session.get(Problem, row.problem_id)
    if problem is None:
        raise core.CreationError(
            "原题目已移除，历史记录可查看，不能继续验证。", 409, "PROBLEM_MISSING"
        )
    cases = _cases(problem)
    if _fingerprint(problem, cases) != row.state["problem_snapshot"]["fingerprint"]:
        raise core.CreationError(
            "题面或测试用例已经更新，请针对新版题目新建共创；旧证据仍保留。",
            409,
            "PROBLEM_CHANGED",
        )
    return problem, cases


def serialize(row, full=True):
    result = {
        k: getattr(row, k)
        for k in ("id", "mode", "scenario_id", "problem_id", "language", "title", "revision")
    }
    result.update(
        legacy=False, created_at=core.stamp(row.created_at), updated_at=core.stamp(row.updated_at)
    )
    if full:
        state = copy.deepcopy(row.state)
        snapshot = copy.deepcopy(state["problem_snapshot"])
        try:
            problem, cases = live_problem(row)
            snapshot["reference_available"] = _reference(problem, cases) is not None
            snapshot["changed"] = False
        except core.CreationError:
            snapshot["reference_available"], snapshot["changed"] = False, True
        result.update(state=state, problem=snapshot)
    return result


def validate_text(value, name="输入", output=False, empty=True):
    return core.text(value, name, MAX_STDIN_CHARS if not output else 20000, empty=empty)


def validate_program(value, empty=False):
    return core.text(value, "代码", MAX_CODE_CHARS, empty=empty)


def create(
    user_id,
    mode,
    problem_id,
    language="python",
    code=None,
    input_text="",
    submission_id=None,
    reuse=False,
    **_,
):
    if mode not in {"examples", "review"}:
        raise core.CreationError("请选择例子推演或代码质检。")
    if not isinstance(problem_id, str) or not 1 <= len(problem_id) <= 50:
        raise core.CreationError("请选择有效的题目。")
    language = normalize_language(language)
    enabled = {item["id"] for item in language_options(SUPPORTED_LANGUAGES)}
    if language not in enabled:
        raise core.CreationError("当前未启用这种编程语言。")
    problem = db.session.get(Problem, problem_id)
    if problem is None:
        raise core.CreationError("题目不存在。", 404, "PROBLEM_NOT_FOUND")
    if type(reuse) is not bool:
        raise core.CreationError("恢复共创选项须为布尔值。")
    source = "student"
    if submission_id is not None:
        if type(submission_id) is not int:
            raise core.CreationError("提交编号无效。")
        submission = Submission.query.filter_by(id=submission_id, user_id=user_id).first()
        if (
            submission is None
            or submission.problem_id != problem_id
            or normalize_language(submission.language) != language
        ):
            raise core.CreationError(
                "提交不存在、无权访问或不属于此题目和语言。", 404, "SUBMISSION_NOT_FOUND"
            )
        if code is None:
            code, source = submission.code_submitted, "submission"
    code = validate_program("" if code is None else code, empty=True)
    input_text = validate_text(input_text, "当前输入")
    snapshot = problem_snapshot(problem)
    context = {"code": code, "input_text": input_text, "submission_id": submission_id}
    if reuse:
        recent = (
            CoCreateSession.query.filter_by(
                user_id=user_id, mode=mode, problem_id=problem_id, language=language
            )
            .order_by(CoCreateSession.updated_at.desc())
            .limit(20)
            .all()
        )
        for previous in recent:
            prior = previous.state or {}
            if (
                prior.get("kind") == "problem"
                and prior.get("practice_context") == context
                and prior.get("problem_snapshot", {}).get("fingerprint") == snapshot["fingerprint"]
            ):
                return previous
    if CoCreateSession.query.filter_by(user_id=user_id).count() >= 80:
        raise core.CreationError("最多保存 80 条记录，请继续使用已有记录。")
    state = {
        "kind": "problem",
        "problem_snapshot": snapshot,
        "examples": copy.deepcopy(snapshot["public_examples"]),
        "generations": [],
        "current_generation_id": None,
        "selected": None,
        "runs": [],
        "events": [],
        "baseline": {
            "code": code,
            "language": language,
            "input_text": input_text,
            "submission_id": submission_id,
            "source": source,
        },
        "practice_context": {
            "code": code,
            "input_text": input_text,
            "submission_id": submission_id,
        },
        "review": {
            "code": code,
            "source": source if code else "empty",
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
        scenario_id="problem",
        problem_id=problem_id,
        language=language,
        title=problem.title[:120],
        state=state,
    )
    db.session.add(row)
    db.session.commit()
    return row


def update_examples(row, revision, data):
    core.require_mode(row, "examples")
    core.check_revision(row, revision)
    live_problem(row)
    state = copy.deepcopy(row.state)
    example_data = data.get("example")
    key = (
        data.get("example_id")
        if data.get("action") == "delete_example"
        else (example_data.get("id") if isinstance(example_data, dict) else None)
    )
    old = next((e for e in state["examples"] if e["id"] == key), None)
    if old and old.get("source") == "official":
        raise core.CreationError("题目公开样例不能改写或删除，请另加自定义例子。")
    if data.get("action") == "delete_example":
        if old is None:
            raise core.CreationError("例子不存在。", 404, "NOT_FOUND")
        state["examples"] = [e for e in state["examples"] if e["id"] != key]
    elif data.get("action") == "upsert_example":
        example = data.get("example")
        if not isinstance(example, dict) or "input" not in example:
            raise core.CreationError("请填写标准输入。")
        if key is not None and old is None:
            raise core.CreationError("例子不存在。", 404, "NOT_FOUND")
        if key is None and len(state["examples"]) >= 12:
            raise core.CreationError("最多保留 12 个例子。")
        value = validate_text(example["input"])
        if any(e["id"] != key and e["input"] == value for e in state["examples"]):
            raise core.CreationError("此输入已有例子，请编辑自定义例子。")
        expected = example.get("expected")
        if expected is not None:
            expected = validate_text(expected, "你的期望输出", output=True)
        replacement = {
            "id": key or core.ident(),
            "input": value,
            "expected": expected,
            "source": "user" if expected is not None else "unknown",
            "readonly": False,
        }
        state["examples"] = [replacement if e["id"] == key else e for e in state["examples"]]
        if key is None:
            state["examples"].append(replacement)
    else:
        raise core.CreationError("未知例子操作。")
    state["current_generation_id"], state["selected"] = None, None
    return core.commit(row, revision, state, "更新题目例子，原候选保留为历史")


def execute(code, language, value):
    """No host compile/eval, including for reference programs."""
    result = core.run_code(code, language, input_text=value)
    success = result.get("success") is True and result.get("execution_backend") == "docker"
    return {
        "success": success,
        "status": "Executed" if success else result.get("status", "Environment Error"),
        "output": result.get("output", "") if success else result.get("output", ""),
        "error": result.get("error", "") if not success else "",
        "execution": {
            k: result.get(k) for k in ("execution_backend", "time", "compile_time", "run_time")
        },
        "output_truncated": bool(result.get("output_truncated")),
        "error_truncated": bool(result.get("error_truncated")),
    }


def _verdict(outcome, expected, source, judge_mode):
    known = expected is not None
    intact = outcome.get("success") and not outcome.get("output_truncated")
    passed = (
        bool(intact and outputs_match(outcome.get("output", ""), expected, judge_mode))
        if known
        else None
    )
    verdict = "execution_failed" if not intact else "unverified"
    if intact and known:
        verdict = (
            ("matches_user" if passed else "differs_user")
            if source == "user"
            else ("passed" if passed else "failed")
        )
    return {"expected": expected, "expected_source": source, "passed": passed, "verdict": verdict}


def resolve_answer(row, value, supplied=UNSET, input_validated=False):
    problem, cases = live_problem(row)
    for case in cases:
        if case.is_public and case.input_data.rstrip("\r\n") == value.rstrip("\r\n"):
            return case.expected_output, "official", None
    if supplied is not UNSET and supplied is not None:
        return validate_text(supplied, "你的期望输出", output=True), "user", None
    if input_validated is True:
        reference = _reference(problem, cases)
        if reference:
            result = execute(reference, "python", value)
            if result["success"] and not result["output_truncated"]:
                return result["output"], "reference", "参考程序对照；输入范围由你确认。"
            # Do not expose reference stderr, which may reveal private source lines.
            return None, "unknown", "参考程序未完成执行，此输入的正确性尚未验证。"
    return None, "unknown", "没有已确认的标准输出；结果一致也不能证明正确。"


def _generation(row):
    generation = next(
        (g for g in row.state["generations"] if g["id"] == row.state["current_generation_id"]), None
    )
    if not generation or not generation.get("candidates") or generation.get("status") == "running":
        raise core.CreationError("请先生成当前例子对应的候选。", 409, "NO_CANDIDATE")
    return generation


def same_result(left, right, mode):
    # stdout is never a trusted list of alternative answers; require symmetry.
    return outputs_match(left, right, mode) and outputs_match(right, left, mode)


def owned_candidate(row, candidate_id, current=True):
    """Pure lookup on an already owner-scoped session; no network or mutation."""
    generations = [_generation(row)] if current else row.state.get("generations", [])
    for generation in generations:
        for candidate in generation.get("candidates", []):
            if candidate["id"] == candidate_id:
                return copy.deepcopy(candidate)
    raise core.CreationError("候选不存在或已过期。", 409, "STALE_CANDIDATE")


def generate(row, revision, source, review=False):
    core.require_mode(row, "review" if review else "examples")
    core.check_revision(row, revision)
    live_problem(row)
    if source != "ai":
        raise core.CreationError("题目候选仅由真实 AI 生成；也可直接使用当前代码进行质检。")
    state = copy.deepcopy(row.state)
    generation = {
        "id": core.ident(),
        "source": "ai",
        "model": None,
        "status": "running",
        "candidates": [],
        "examples": copy.deepcopy(state["examples"]),
        "behavior_difference": None,
        "error": None,
        "created_at": core.stamp(now()),
    }
    state["generations"] = state["generations"][-39:] + [generation]
    state["current_generation_id"], state["selected"] = generation["id"], None
    core.commit(row, revision, state, "开始生成题目候选")
    reserved = row.revision
    baseline = state["review"]["code"] if review else state["baseline"]["code"]
    try:
        count = 1 if review or baseline.strip() else 2
        proposed, model = ai.generate_problem(
            state["problem_snapshot"],
            row.language,
            state["examples"],
            count=count,
            baseline=baseline,
        )
        generation["model"] = model
        if not review and baseline.strip():
            proposed = [
                {
                    "code": baseline,
                    "label": "当前代码",
                    "explanation": "来自带入的当前代码，不是 AI 生成。",
                    "source": state["baseline"]["source"],
                }
            ] + proposed
        for index, item in enumerate(proposed, 1):
            code = validate_program(item["code"])
            evidence = []
            for example in state["examples"]:
                outcome = execute(code, row.language, example["input"])
                evidence.append(
                    {
                        "id": example["id"],
                        "input": example["input"],
                        **outcome,
                        **_verdict(
                            outcome,
                            example.get("expected"),
                            example.get("source", "unknown"),
                            state["problem_snapshot"]["judge_mode"],
                        ),
                    }
                )
            known = [e for e in evidence if e["expected_source"] == "official"]
            candidate_source = item.get("source", "ai")
            generation["candidates"].append(
                {
                    "id": core.ident(),
                    "label": item.get("label") or f"候选 {index}",
                    "code": code,
                    "language": row.language,
                    "explanation": item.get("explanation", ""),
                    "source": candidate_source,
                    "model": model if candidate_source == "ai" else None,
                    "code_hash": hashlib.sha256(code.encode()).hexdigest(),
                    "verified": bool(known) and all(e["passed"] is True for e in known),
                    "verification": {
                        "scope": "examples",
                        "cases": evidence,
                        "total": len(evidence),
                        "passed": sum(e["passed"] is True for e in known),
                        "official_total": len(known),
                        "message": "仅为已运行例子的结果；完整题库验证需另行操作。",
                    },
                }
            )
        generation["status"] = "ready"
        if review:
            candidate = generation["candidates"][0]
            _replace_review(state["review"], candidate["code"], "ai", model)
            state["review"]["generation_error"] = None
    except (AIClientError, core.CreationError, ValueError, TypeError, KeyError) as exc:
        generation["status"] = "failed"
        generation["error"] = (
            "真实 AI 请求失败或回复无效，本次未采用新的候选。"
            if isinstance(exc, AIClientError)
            else str(exc)[:500]
        )
        if review:
            state["review"]["generation_error"] = generation["error"]
    state["generations"] = [
        generation if g["id"] == generation["id"] else g for g in state["generations"]
    ]
    return core.commit(
        row,
        reserved,
        state,
        "题目候选已保存" if generation["status"] == "ready" else "题目候选生成失败",
    )


def compare(row, revision, value, expected=UNSET, input_validated=False):
    core.require_mode(row, "examples")
    core.check_revision(row, revision)
    value = validate_text(value)
    live_problem(row)
    generation = _generation(row)
    core.commit(row, revision, row.state, "开始题目候选对照")
    reserved = row.revision
    answer, source, note = resolve_answer(row, value, expected, input_validated)
    results = []
    for candidate in generation["candidates"]:
        outcome = execute(candidate["code"], row.language, value)
        results.append(
            {
                "candidate_id": candidate["id"],
                **outcome,
                **_verdict(outcome, answer, source, row.state["problem_snapshot"]["judge_mode"]),
            }
        )
    successful = all(r["success"] and not r["output_truncated"] for r in results)
    run = {
        "id": core.ident(),
        "kind": "compare",
        "input": value,
        "expected": answer,
        "expected_source": source,
        "note": note,
        "results": results,
        "different": len(results) > 1
        and successful
        and not same_result(
            results[0]["output"], results[1]["output"], row.state["problem_snapshot"]["judge_mode"]
        ),
        "correctness_verified": source in {"official", "reference"} and successful,
        "generation_id": generation["id"],
        "created_at": core.stamp(now()),
    }
    state = copy.deepcopy(row.state)
    state["runs"] = state["runs"][-79:] + [run]
    core.commit(row, reserved, state, "保存题目对照运行证据")
    return row, run


def select(row, revision, generation_id, candidate_id):
    core.require_mode(row, "examples")
    core.check_revision(row, revision)
    live_problem(row)
    generation = _generation(row)
    if generation["id"] != generation_id:
        raise core.CreationError("请使用当前例子对应的候选。", 409, "STALE_CANDIDATE")
    candidate = owned_candidate(row, candidate_id)
    state = copy.deepcopy(row.state)
    state["selected"] = {
        "generation_id": generation_id,
        "candidate_id": candidate_id,
        "label": candidate["label"],
        "confirmed_at": core.stamp(now()),
        "requires_formal_submission": True,
    }
    return core.commit(row, revision, state, "选择候选；正式提交与积分仍由刷题页处理")


def _replace_review(review, code, source="student", model=None):
    if review["code"]:
        review["history"] = review["history"][-19:] + [
            {k: review[k] for k in ("code", "code_revision", "source", "model")}
        ]
    review.update(
        code=code,
        source=source,
        model=model,
        code_revision=review["code_revision"] + 1,
        verified=False,
        prediction_saved=False,
        prediction_input=None,
        prediction_code_revision=None,
        judgment="",
    )


def save_review(row, revision, data):
    core.require_mode(row, "review")
    core.check_revision(row, revision)
    live_problem(row)
    state = copy.deepcopy(row.state)
    review = state["review"]
    if "code" in data:
        code = validate_program(data["code"], empty=True)
        if code != review["code"]:
            _replace_review(review, code)
    if "judgment" in data:
        if data["judgment"] not in {"correct", "incorrect", "unsure"}:
            raise core.CreationError("请选择你的判断。")
        review["judgment"] = data["judgment"]
    if "reflection" in data:
        review["reflection"] = core.text(data["reflection"], "反思", 2000, empty=True)
    if data.get("clear_prediction") is True:
        review.update(
            prediction=None,
            prediction_saved=False,
            prediction_input=None,
            prediction_code_revision=None,
        )
    if "prediction" in data:
        if "prediction_input" not in data:
            raise core.CreationError("请同时提供预测对应的标准输入。")
        review.update(
            prediction=validate_text(data["prediction"], "预测输出", output=True),
            prediction_input=validate_text(data["prediction_input"]),
            prediction_saved=True,
            prediction_code_revision=review["code_revision"],
        )
    return core.commit(row, revision, state, "保存题目质检判断与修订")


def review_run(row, revision, value, expected=UNSET, input_validated=False):
    core.require_mode(row, "review")
    core.check_revision(row, revision)
    live_problem(row)
    value = validate_text(value)
    review = copy.deepcopy(row.state["review"])
    validate_program(review["code"])
    if review["prediction_saved"] and (
        review.get("prediction_input") != value
        or review.get("prediction_code_revision") != review["code_revision"]
    ):
        raise core.CreationError("输入或代码已变化，请重新保存预测。", 409, "STALE_PREDICTION")
    core.commit(row, revision, row.state, "开始题目质检运行")
    reserved = row.revision
    answer, source, note = resolve_answer(row, value, expected, input_validated)
    outcome = execute(review["code"], row.language, value)
    run = {
        "id": core.ident(),
        "kind": "review",
        "input": value,
        "actual": outcome["output"],
        **outcome,
        **_verdict(outcome, answer, source, row.state["problem_snapshot"]["judge_mode"]),
        "note": note,
        "prediction": review["prediction"],
        "judgment": review["judgment"],
        "prediction_matched": (
            (
                outcome["success"]
                and not outcome["output_truncated"]
                and same_result(
                    outcome["output"],
                    review["prediction"],
                    row.state["problem_snapshot"]["judge_mode"],
                )
            )
            if review["prediction_saved"]
            else None
        ),
        "code_revision": review["code_revision"],
        "code_hash": hashlib.sha256(review["code"].encode()).hexdigest(),
        "created_at": core.stamp(now()),
    }
    state = copy.deepcopy(row.state)
    state["runs"] = state["runs"][-79:] + [run]
    state["review"]["evidence"] = state["review"]["evidence"][-39:] + [run]
    state["review"]["verified"] = False
    core.commit(row, reserved, state, "保存真实题目质检证据")
    return row, run


def verify(row, revision, candidate_id=None):
    core.check_revision(row, revision)
    problem, cases = live_problem(row)
    if not cases:
        raise core.CreationError("该题尚无验证用例。", 400, "TEST_CASES_MISSING")
    if row.mode == "review" and candidate_id is None:
        code = validate_program(row.state["review"]["code"])
        code_revision = row.state["review"]["code_revision"]
    else:
        if candidate_id is None:
            candidate_id = (row.state.get("selected") or {}).get("candidate_id")
        candidate = owned_candidate(row, candidate_id)
        code, code_revision = candidate["code"], None
    core.commit(row, revision, row.state, "开始题库用例验证，不创建正式提交")
    reserved = row.revision
    results = []
    for index, case in enumerate(cases, 1):
        outcome = execute(code, row.language, case.input_data)
        passed = (
            outcome["success"]
            and not outcome["output_truncated"]
            and outputs_match(outcome["output"], case.expected_output, problem.judge_mode)
        )
        status = (
            "Accepted" if passed else "Wrong Answer" if outcome["success"] else outcome["status"]
        )
        public = {
            "id": f"case-{index}",
            "index": index,
            "is_public": case.is_public,
            "status": status,
            "passed": bool(passed),
        }
        if case.is_public:
            public.update(
                input=case.input_data,
                expected=case.expected_output,
                expected_source="official",
                actual=outcome["output"],
                **outcome,
            )
            public["status"] = status
        results.append(public)
    run = {
        "id": core.ident(),
        "kind": "verify",
        "scope": "problem_cases",
        "candidate_id": candidate_id,
        "code_revision": code_revision,
        "code_hash": hashlib.sha256(code.encode()).hexdigest(),
        "cases": results,
        "total": len(cases),
        "executed": len(results),
        "passed_count": sum(r["passed"] for r in results),
        "passed": all(r["passed"] for r in results),
        "hidden_total": sum(not r["is_public"] for r in results),
        "hidden_passed": sum(r["passed"] and not r["is_public"] for r in results),
        "message": "仅表示题库现有用例的结果；没有创建正式刷题提交或增加积分。",
        "created_at": core.stamp(now()),
    }
    state = copy.deepcopy(row.state)
    state["runs"] = state["runs"][-79:] + [run]
    if row.mode == "review":
        state["review"]["evidence"] = state["review"]["evidence"][-39:] + [run]
        state["review"]["verified"] = False
    core.commit(row, reserved, state, "保存脱敏后的题库验证证据")
    return row, run

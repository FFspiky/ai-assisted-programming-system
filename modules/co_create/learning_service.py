"""Student-authored explanations and owned, evidence-linked transfer attempts.

There is no mastery score, generated student contribution, or paid AI call here.
Learning state is lazily added to existing problem-linked sessions.
"""

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from models import CodeProposal, LearningHelp, PracticeEvent, Problem, Submission, db

from . import problem_service
from . import service as core
from .models import now

ROOT = Path(__file__).resolve().parents[2]
HELP_USAGE = {"none", "hint", "full", "unspecified"}
JUDGMENTS = {"", "correct", "incorrect", "unsure"}
NOTES = [
    "用例通过只描述已执行的有限用例，不能保证所有输入正确。",
    "解释由学生本人填写，空白保持空白；代码修改后须重新核对解释。",
    "帮助情况是学生自述；本站记录也不能证明站外没有帮助。",
    "关联题提交是一次实际尝试，不自动等同于已掌握。",
    "复盘展示最近 40 次运行、40 份带回候选及每份最近 80 个操作；更早记录仍保留在原历史。",
]


def _hash(code):
    return hashlib.sha256(code.encode()).hexdigest()


def _commit(row, revision, state, event):
    try:
        return core.commit(row, revision, state, event)
    except IntegrityError as exc:
        db.session.rollback()
        raise core.CreationError(
            "记录已更新，请读取最新状态后重试。", 409, "STALE_REVISION"
        ) from exc
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise core.CreationError(
            "学习记录未确认保存，请读取记录后重试。", 503, "LEARNING_SAVE_FAILED"
        ) from exc


def _clip(value, limit=800):
    return value[:limit] if isinstance(value, str) else value


def _state(row):
    value = copy.deepcopy((row.state or {}).get("learning") or {})
    return {
        "version": 1,
        "reflection": value.get("reflection"),
        "reflection_history": value.get("reflection_history", [])[-20:],
        "attempts": value.get("attempts", [])[-20:],
    }


def _require(row):
    if not problem_service.is_problem(row):
        raise core.CreationError("旧场景记录仍可回看，请从题库新建学习共创。", 400, "LEGACY_RECORD")
    return problem_service.live_problem(row)


def _program(row, candidate_id=None):
    if row.mode == "review":
        if candidate_id not in {None, "review"}:
            raise core.CreationError("请选择当前待检代码。", 409, "STALE_CANDIDATE")
        review = row.state.get("review", {})
        code = review.get("code", "")
        problem_service.validate_program(code)
        return {
            "candidate_id": "review",
            "label": "当前待检代码",
            "code": code,
            "code_hash": _hash(code),
            "source": review.get("source", "student"),
            "model": review.get("model"),
            "code_revision": review.get("code_revision"),
        }
    if candidate_id is None:
        candidate_id = (row.state.get("selected") or {}).get("candidate_id")
        if candidate_id is None:
            generation = next(
                (
                    g
                    for g in row.state.get("generations", [])
                    if g.get("id") == row.state.get("current_generation_id")
                ),
                {},
            )
            candidate_id = next((c.get("id") for c in generation.get("candidates", [])), None)
    candidate = problem_service.owned_candidate(row, candidate_id)
    return {
        "candidate_id": candidate["id"],
        "label": candidate.get("label", "候选代码"),
        "code": candidate["code"],
        "code_hash": _hash(candidate["code"]),
        "source": candidate.get("source", "unknown"),
        "model": candidate.get("model"),
        "verification": _run_summary(candidate.get("verification", {})),
    }


def _reflection(row, learning):
    value = copy.deepcopy(learning.get("reflection"))
    if not value:
        return None
    try:
        problem_service.live_problem(row)
        bound = _program(row, value.get("candidate_id"))
        value["stale"] = bound["code_hash"] != value.get("code_hash")
        current = _program(row)
        value["is_current_target"] = current["candidate_id"] == value.get(
            "candidate_id"
        ) and current["code_hash"] == value.get("code_hash")
    except core.CreationError:
        value["stale"] = True
        value["is_current_target"] = False
    return value


def _run_summary(run):
    """Explicit allowlist: hidden outcomes never inherit raw execution fields."""
    fields = (
        "id",
        "kind",
        "created_at",
        "code_hash",
        "candidate_id",
        "generation_id",
        "scope",
        "total",
        "executed",
        "passed",
        "passed_count",
        "hidden_total",
        "hidden_passed",
        "official_total",
        "expected_source",
        "different",
        "prediction_matched",
        "code_revision",
        "correctness_verified",
    )
    result = {k: copy.deepcopy(run[k]) for k in fields if k in run}
    for key in ("input", "expected", "actual", "output", "prediction", "status", "note"):
        if key in run:
            result[key] = _clip(run[key])
    if "cases" in run:
        result["cases"] = []
        for case in run["cases"][:20]:
            public = case.get("is_public", True) is True
            item = {
                k: copy.deepcopy(case[k]) for k in ("id", "index", "status", "passed") if k in case
            }
            item["is_public"] = public
            if public:
                for key in (
                    "input",
                    "expected",
                    "actual",
                    "output",
                    "expected_output",
                    "actual_output",
                    "expected_source",
                    "success",
                    "output_truncated",
                ):
                    if key in case:
                        item[key] = _clip(case[key])
            result["cases"].append(item)
        result["cases_omitted"] = max(0, len(run["cases"]) - 20)
    if "results" in run:
        result["results"] = [
            {
                k: _clip(item[k])
                for k in (
                    "candidate_id",
                    "status",
                    "success",
                    "passed",
                    "output",
                    "expected_source",
                    "output_truncated",
                )
                if k in item
            }
            for item in run["results"][:4]
        ]
    return result


def _canonical():
    try:
        return {
            p["id"]: p
            for p in json.loads((ROOT / "data/problem_library.json").read_text(encoding="utf-8"))
        }
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def _canonical_live(problem, catalog):
    record = catalog.get(problem.id) if problem else None
    if not record:
        return False
    expected = {k: record[k] for k in ("id", "title", "description", "judge_mode", "cases")}
    return problem_service._fingerprint(
        problem, problem_service._cases(problem)
    ) == problem_service._digest(expected)


def related(row):
    if not problem_service.is_problem(row):
        return []
    try:
        problem, _ = problem_service.live_problem(row)
        catalog = _canonical()
        if not _canonical_live(problem, catalog):
            return []
        raw = json.loads((ROOT / "data/co_create_learning_pairs.json").read_text(encoding="utf-8"))
        pairs = raw.get("pairs", []) if isinstance(raw, dict) else raw
        result, seen = [], set()
        for pair in pairs:
            source, target = pair.get("source_id"), pair.get("target_id")
            if row.problem_id == target:
                source, target = target, source
            if (
                source != row.problem_id
                or not isinstance(target, str)
                or target == source
                or target in seen
            ):
                continue
            live = db.session.get(Problem, target)
            if not _canonical_live(live, catalog):
                continue
            result.append(
                {
                    "problem_id": live.id,
                    "title": live.title,
                    "difficulty": live.difficulty,
                    "category": live.category,
                    "reason": _clip(pair.get("reason", ""), 500),
                    "focus": _clip(pair.get("concept", ""), 300),
                    "practice_url": "/practice.html?"
                    + urlencode({"problem": live.id, "language": row.language}),
                }
            )
            seen.add(target)
            if len(result) >= 4:
                break
        return result
    except (OSError, ValueError, TypeError, KeyError, core.CreationError):
        return []


def _submission(submission):
    return {
        "id": submission.id,
        "problem_id": submission.problem_id,
        "language": submission.language,
        "status": submission.status,
        "created_at": core.stamp(submission.timestamp),
        "code_hash": _hash(submission.code_submitted),
        "evidence": _run_summary(submission.evidence_snapshot or {}),
    }


def _attempt(row, value):
    result = copy.deepcopy(value)
    target = db.session.get(Problem, result.get("problem_id"))
    valid = target is not None and problem_service._fingerprint(
        target, problem_service._cases(target)
    ) == result.get("problem_fingerprint")
    result["status"] = (
        "target_changed"
        if not valid
        else "submitted" if result.get("submissions") else "in_progress"
    )
    for saved in result.get("submissions", []):
        submission = Submission.query.filter_by(
            id=saved["submission_id"],
            user_id=row.user_id,
            problem_id=result["problem_id"],
            language=row.language,
        ).first()
        saved["submission"] = _submission(submission) if submission else None
        saved["record_available"] = submission is not None
        saved["recorded_help"] = _recorded_help(row, saved["submission_id"])
        saved["recorded_help_source"] = "live_site_records"
        saved["recorded_help_limit"] = 20
        saved["help_note"] = "仅列此提交最近 20 条本站帮助记录，不能证明站外没有帮助。"
    return result


def _recorded_help(row, submission_id):
    records = (
        LearningHelp.query.filter_by(
            user_id=row.user_id, submission_id=submission_id, state="ready"
        )
        .order_by(LearningHelp.created_at.desc(), LearningHelp.id.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": h.id,
            "source": h.source,
            "level": h.returned_level,
            "created_at": core.stamp(h.created_at),
            "shown_at": core.stamp(h.shown_at) if h.shown_at else None,
        }
        for h in records
    ]


def _practice_event(event):
    result = {
        "id": event.id,
        "kind": event.kind,
        "created_at": core.stamp(event.created_at),
        "submission_id": event.submission_id,
    }
    payload = event.payload or {}
    for key in ("before_code", "after_code"):
        if isinstance(payload.get(key), str):
            result[key + "_hash"] = _hash(payload[key])
    if type(payload.get("edited_after_accept")) is bool:
        result["edited_after_accept"] = payload["edited_after_accept"]
    return result


def _proposal_evidence(row):
    records = (
        CodeProposal.query.filter_by(user_id=row.user_id, co_create_session_id=row.id)
        .order_by(CodeProposal.created_at.desc(), CodeProposal.id.desc())
        .limit(40)
        .all()
    )
    result = []
    for proposal in reversed(records):
        events = (
            PracticeEvent.query.filter_by(user_id=row.user_id, proposal_id=proposal.id)
            .order_by(PracticeEvent.created_at.desc(), PracticeEvent.id.desc())
            .limit(80)
            .all()
        )
        events.reverse()
        formal = []
        for event in events:
            if event.kind != "retest" or not event.submission_id:
                continue
            submission = Submission.query.filter_by(
                id=event.submission_id,
                user_id=row.user_id,
                problem_id=row.problem_id,
                language=row.language,
            ).first()
            if submission:
                formal.append(_submission(submission))
        result.append(
            {
                "id": proposal.id,
                "state": proposal.state,
                "candidate_id": proposal.co_create_candidate_id,
                "code_hash": _hash(proposal.candidate_code),
                "created_at": core.stamp(proposal.created_at),
                "events": [_practice_event(e) for e in events],
                "formal_submissions": formal,
            }
        )
    return result


def payload(row):
    learning = _state(row)
    reflection = _reflection(row, learning)
    attempts = [_attempt(row, value) for value in learning["attempts"]]
    try:
        chosen = _program(row) if problem_service.is_problem(row) else None
    except core.CreationError:
        chosen = None
    changed = False
    try:
        _require(row)
    except core.CreationError:
        changed = True
    baseline = row.state.get("baseline", {})
    code = baseline.get("code", "")
    recap = {
        "version": 1,
        "session": {
            "id": row.id,
            "title": row.title,
            "problem_id": row.problem_id,
            "language": row.language,
            "mode": row.mode,
            "revision": row.revision,
            "problem_changed": changed,
            "legacy": not problem_service.is_problem(row),
            "created_at": core.stamp(row.created_at),
        },
        "baseline": {
            "code": code,
            "source": baseline.get("source", "unknown"),
            "code_hash": _hash(code),
            "submission_id": row.state.get("practice_context", {}).get("submission_id"),
        },
        "chosen": chosen,
        "reflection": reflection,
        "reflection_history": copy.deepcopy(learning["reflection_history"]),
        "runs": [_run_summary(run) for run in row.state.get("runs", [])[-40:]],
        "runs_omitted": max(0, len(row.state.get("runs", [])) - 40),
        "proposals": _proposal_evidence(row),
        "transfer_attempts": attempts,
        "scope_notes": NOTES,
    }
    public_learning = {
        "version": 1,
        "reflection": reflection,
        "stage": "transfer" if attempts else "explain" if reflection else "verify",
    }
    return {
        "session_id": row.id,
        "revision": row.revision,
        "learning": public_learning,
        "recap": recap,
        "related": related(row),
        "attempts": attempts,
    }


def _matching_runs(row, program):
    result = []
    for run in row.state.get("runs", []):
        if run.get("code_hash") == program["code_hash"]:
            result.append(run["id"])
        elif run.get("kind") == "compare" and any(
            r.get("candidate_id") == program["candidate_id"] for r in run.get("results", [])
        ):
            result.append(run["id"])
    return result[-40:]


def reflection(row, revision, data):
    core.check_revision(row, revision)
    _require(row)
    program = _program(row, data.get("candidate_id"))
    judgment = data.get("judgment", "")
    if judgment not in JUDGMENTS:
        raise core.CreationError("判断须为正确、需修改、不确定或留空。")
    value = {
        key: core.text(data.get(key, ""), name, 2000, empty=True)
        for key, name in (
            ("reason", "修改理由"),
            ("boundary", "适用边界"),
            ("next_check", "下一步检查"),
        )
    }
    value.update(
        candidate_id=program["candidate_id"],
        code_hash=program["code_hash"],
        source=program["source"],
        judgment=judgment,
        saved_at=core.stamp(now()),
        run_ids=_matching_runs(row, program),
    )
    state = copy.deepcopy(row.state)
    learning = _state(row)
    if learning["reflection"]:
        learning["reflection_history"] = learning["reflection_history"][-19:] + [
            learning["reflection"]
        ]
    learning["reflection"] = value
    state["learning"] = learning
    return _commit(row, revision, state, "学生保存自己的解释与下一步检查")


def transfer(row, revision, problem_id):
    core.check_revision(row, revision)
    _require(row)
    if not isinstance(problem_id, str) or len(problem_id) > 50:
        raise core.CreationError("请选择关联题目。")
    selected = next((p for p in related(row) if p["problem_id"] == problem_id), None)
    if selected is None:
        raise core.CreationError(
            "关联题目不存在或题面已更新，请刷新后重新选择。", 409, "RELATED_PROBLEM_CHANGED"
        )
    learning = _state(row)
    if len(learning["attempts"]) >= 20:
        raise core.CreationError("本次共创最多保留 20 次关联题尝试，请继续已有尝试。")
    target = db.session.get(Problem, problem_id)
    value = {
        "id": core.ident(),
        "problem_id": problem_id,
        "title": target.title,
        "language": row.language,
        "started_at": core.stamp(now()),
        "problem_fingerprint": problem_service._fingerprint(target, problem_service._cases(target)),
        "reason": selected["reason"],
        "focus": selected["focus"],
        "submissions": [],
        "existing_submission_count": Submission.query.filter_by(
            user_id=row.user_id, problem_id=problem_id, language=row.language
        ).count(),
    }
    learning["attempts"].append(value)
    state = copy.deepcopy(row.state)
    state["learning"] = learning
    _commit(row, revision, state, "开始关联题尝试；尚未形成学习结论")
    return row, _attempt(row, value)


def owned_attempt(row, attempt_id):
    value = next((a for a in _state(row)["attempts"] if a["id"] == attempt_id), None)
    if value is None:
        raise core.CreationError("关联题尝试不存在或无权访问。", 404, "ATTEMPT_NOT_FOUND")
    return value


def attempt_context(row, attempt_id):
    value = owned_attempt(row, attempt_id)
    return {
        "session_id": row.id,
        "revision": row.revision,
        "attempt": _attempt(row, value),
        "source": {
            "session_id": row.id,
            "problem_id": row.problem_id,
            "title": row.title,
            "language": row.language,
        },
        "recap_url": "/co-create.html?" + urlencode({"session": row.id, "stage": "recap"}),
        "recap": payload(row)["recap"],
    }


def practice_url(row, attempt):
    return "/practice.html?" + urlencode(
        {
            "problem": attempt["problem_id"],
            "language": row.language,
            "co_create_session": row.id,
            "transfer_attempt": attempt["id"],
        }
    )


def attach_submission(row, revision, attempt_id, data):
    if type(revision) is not int:
        raise core.CreationError("请提供有效记录版本。", 409, "STALE_REVISION")
    _require(row)
    value = owned_attempt(row, attempt_id)
    if _attempt(row, value)["status"] == "target_changed":
        raise core.CreationError(
            "关联题面或用例已经更新，本次尝试保留为历史记录。", 409, "TARGET_PROBLEM_CHANGED"
        )
    submission_id, usage = data.get("submission_id"), data.get("help_usage", "unspecified")
    if type(submission_id) is not int or usage not in HELP_USAGE:
        raise core.CreationError("提交编号或帮助情况无效。")
    submission = Submission.query.filter_by(
        id=submission_id, user_id=row.user_id, problem_id=value["problem_id"], language=row.language
    ).first()
    if not submission:
        raise core.CreationError(
            "提交不存在、无权访问或与尝试题目及语言不匹配。", 404, "SUBMISSION_NOT_FOUND"
        )
    began = datetime.fromisoformat(value["started_at"])
    if submission.timestamp.replace(tzinfo=timezone.utc) < began:
        raise core.CreationError(
            "只能关联本次尝试开始之后的真实提交。", 409, "SUBMISSION_BEFORE_ATTEMPT"
        )
    saved = next((s for s in value["submissions"] if s["submission_id"] == submission_id), None)
    if saved and saved["help_usage"] == usage:
        return row, _attempt(row, value)
    core.check_revision(row, revision)
    if len(value["submissions"]) >= 20 and saved is None:
        raise core.CreationError("本次尝试最多关联 20 次提交。")
    key = f"transfer-submission:{submission_id}"
    claimed = PracticeEvent.query.filter_by(user_id=row.user_id, operation_id=key).first()
    if claimed and (
        claimed.payload.get("attempt_id") != attempt_id
        or claimed.payload.get("session_id") != row.id
    ):
        raise core.CreationError(
            "该提交已经属于另一条关联题尝试。", 409, "SUBMISSION_ALREADY_LINKED"
        )
    item = {
        "submission_id": submission_id,
        "help_usage": usage,
        "help_usage_source": "student_self_report",
        "linked_at": core.stamp(now()),
        "recorded_help": _recorded_help(row, submission_id),
        "help_note": "本站帮助记录仅覆盖已记录内容，不能证明站外没有帮助。",
    }
    learning = _state(row)
    attempt = next(a for a in learning["attempts"] if a["id"] == attempt_id)
    attempt["submissions"] = [
        s for s in attempt["submissions"] if s["submission_id"] != submission_id
    ] + [item]
    state = copy.deepcopy(row.state)
    state["learning"] = learning
    if not claimed:
        db.session.add(
            PracticeEvent(
                user_id=row.user_id,
                problem_id=value["problem_id"],
                language=row.language,
                submission_id=submission_id,
                kind="transfer_submission",
                operation_id=key,
                payload={
                    "session_id": row.id,
                    "attempt_id": attempt_id,
                    "help_usage_source": "student_self_report",
                },
            )
        )
    _commit(row, revision, state, "关联真实提交与学生自述帮助情况")
    return row, _attempt(row, attempt)

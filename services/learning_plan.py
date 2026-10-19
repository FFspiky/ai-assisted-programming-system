"""Small, transparent learning recommendations. No LLM call or inferred mastery score."""

import copy
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from models import LearningAssessment, db
from modules.task_room.catalog import list_catalog
from modules.task_room.models import TaskContract, TaskProject, TaskRun
from modules.task_room.service import fingerprint
from services.language_support import language_label

VERSION = 2
QUESTIONS = [
    {
        "id": "experience",
        "title": "你目前做过多少编程练习？",
        "type": "single",
        "options": [
            {"value": "new", "label": "刚开始，还没有独立完成过"},
            {"value": "some", "label": "做过一些小练习"},
            {"value": "project", "label": "完成过一个小项目"},
        ],
    },
    {
        "id": "coding",
        "title": "使用你选择的语言阅读和编写代码时，你的感受是？",
        "type": "single",
        "options": [
            {"value": "new", "label": "还需要从变量和输入输出学起"},
            {"value": "basic", "label": "能看懂简单代码，需要提示才能写"},
            {"value": "comfortable", "label": "能自己写出函数并调试"},
        ],
    },
    {
        "id": "preferred_language",
        "title": "你希望用哪种语言完成接下来的练习？",
        "type": "single",
        "options": [
            {"value": "python", "label": "Python"},
            {"value": "cpp", "label": "C++"},
        ],
    },
    {
        "id": "loops",
        "title": "条件判断和循环，你能独立使用吗？",
        "type": "single",
        "options": [
            {"value": "new", "label": "还不熟悉，想先练基础"},
            {"value": "basic", "label": "能写简单判断和遍历"},
            {"value": "comfortable", "label": "能组合循环处理边界情况"},
        ],
    },
    {
        "id": "collections",
        "title": "处理列表、字典和一组数据时，你更接近哪种情况？",
        "type": "single",
        "options": [
            {"value": "new", "label": "还需要学习如何取值和修改"},
            {"value": "basic", "label": "能遍历、求和和筛选"},
            {"value": "comfortable", "label": "能按规则分组、去重和排序"},
        ],
    },
    {
        "id": "testing",
        "title": "代码写完后，你通常怎样检查？",
        "type": "single",
        "options": [
            {"value": "new", "label": "运行一个示例，结果对了就结束"},
            {"value": "basic", "label": "会检查空输入、重复值等边界"},
            {"value": "confident", "label": "会按每项需求安排用例并复测"},
        ],
    },
    {
        "id": "time",
        "title": "你希望每次练习大约花多久？",
        "type": "single",
        "options": [
            {"value": "short", "label": "15 分钟左右，先完成一小步"},
            {"value": "medium", "label": "30 分钟左右，完成一个小任务"},
            {"value": "long", "label": "60 分钟左右，完整练习与修改"},
        ],
    },
    {
        "id": "interests",
        "title": "你更想从哪些场景入手？最多选两项。",
        "type": "multi",
        "max_select": 2,
        "options": [
            {"value": "daily", "label": "日常生活小工具"},
            {"value": "campus", "label": "校园活动小任务"},
            {"value": "data", "label": "数据整理与统计"},
        ],
    },
    {
        "id": "goal",
        "title": "这阶段，你最想先做好哪件事？",
        "type": "single",
        "options": [
            {"value": "basics", "label": "巩固基础，独立写出小程序"},
            {"value": "data", "label": "学会整理和处理一组数据"},
            {"value": "business", "label": "按明确需求完成一个小项目"},
        ],
    },
]

LEVELS = {
    "starter": {
        "value": "starter",
        "label": "从小任务起步",
        "description": "先练变量、判断和遍历，每次完成一个范围明确的小任务。",
    },
    "basic": {
        "value": "basic",
        "label": "练习数据处理",
        "description": "在小任务中练习列表、字典、筛选和排序，再尝试业务规则。",
    },
    "applied": {
        "value": "applied",
        "label": "尝试完整需求",
        "description": "从确认规则、编写代码到验收交付，练习应对一次需求变化。",
    },
}


class PlanError(Exception):
    def __init__(self, message, status=400, code="INVALID_ASSESSMENT"):
        super().__init__(message)
        self.message, self.status, self.code = message, status, code


def public_questions():
    return copy.deepcopy(QUESTIONS)


def current_answers(answers):
    """Map version-1 Python self-reports without rewriting historical records."""
    if not isinstance(answers, dict):
        return answers
    result = copy.deepcopy(answers)
    legacy = {q["id"] for q in QUESTIONS} - {"coding", "preferred_language"} | {"python"}
    if set(result) == legacy:
        result["coding"] = result.pop("python")
        result["preferred_language"] = "python"
    return result


def validate_answers(answers):
    answers = current_answers(answers)
    if not isinstance(answers, dict) or set(answers) != {q["id"] for q in QUESTIONS}:
        raise PlanError(f"请完成全部 {len(QUESTIONS)} 个问题，且不要添加问卷以外的答案。")
    cleaned = {}
    for question in QUESTIONS:
        answer = answers[question["id"]]
        valid = {option["value"] for option in question["options"]}
        if question["type"] == "multi":
            if (
                not isinstance(answer, list)
                or not 1 <= len(answer) <= question["max_select"]
                or any(not isinstance(value, str) or value not in valid for value in answer)
                or len(set(answer)) != len(answer)
            ):
                raise PlanError("兴趣场景请选择 1 至 2 项不同的有效选项。")
            cleaned[question["id"]] = list(answer)
        else:
            if not isinstance(answer, str) or answer not in valid:
                raise PlanError(f"请为‘{question['title']}’选择有效选项。")
            cleaned[question["id"]] = answer
    return cleaned


def chosen_level(answers):
    answers = current_answers(answers)
    if answers["coding"] == "new" or answers["loops"] == "new" or answers["experience"] == "new":
        return "starter"
    if answers["collections"] != "comfortable" or answers["experience"] != "project":
        return "basic"
    return "applied"


def ranked_scenarios(answers):
    level = chosen_level(answers)
    preference = {
        "starter": {"starter": 100, "basic": 50, "applied": 10},
        "basic": {"starter": 65, "basic": 100, "applied": 45},
        "applied": {"starter": 40, "basic": 75, "applied": 100},
    }[level]
    target_minutes = {"short": 15, "medium": 30, "long": 60}[answers["time"]]
    goals = {
        "basics": {"basics", "loops", "strings"},
        "data": {"lists", "dicts", "sorting"},
        "business": {"business", "testing"},
    }

    def score(scenario):
        result = preference.get(scenario.get("level", "applied"), 10)
        skills = set(scenario.get("skills", []))
        result += len(skills & goals[answers["goal"]]) * 6
        result += len(set(scenario.get("topics", [])) & set(answers["interests"])) * 8
        if scenario.get("estimated_minutes", 45) <= target_minutes:
            result += 15
        elif answers["time"] == "short":
            result -= 15
        if answers["testing"] == "new" and "testing" in skills:
            result += 3
        return result

    return sorted(
        list_catalog(), key=lambda s: (-score(s), s.get("estimated_minutes", 45), s["id"])
    )


def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def progress(user_id, language=None):
    projects = (
        TaskProject.query.filter_by(user_id=user_id).order_by(TaskProject.updated_at.desc()).all()
    )
    project_ids = [project.id for project in projects]
    runs = TaskRun.query.filter(TaskRun.project_id.in_(project_ids)).all() if project_ids else []
    versions = (
        TaskContract.query.filter(TaskContract.project_id.in_(project_ids)).all()
        if project_ids
        else []
    )
    latest = {}
    for contract in versions:
        if (
            contract.project_id not in latest
            or contract.version > latest[contract.project_id].version
        ):
            latest[contract.project_id] = contract
    by_run = {run.id: run for run in runs}
    result = {}
    delivered_count = 0
    for project in projects:
        contract = latest.get(project.id)
        delivery = project.delivery or {}
        run = by_run.get(delivery.get("run_id"))
        delivered = bool(
            project.state == "delivered"
            and contract
            and run
            and delivery.get("contract_id") == contract.id == run.contract_id
            and delivery.get("code_hash") == fingerprint(project.code) == run.code_hash
            and run.kind == "acceptance"
            and (run.language or "python") == (project.language or "python")
            and delivery.get("language", "python") == (project.language or "python")
            and run.status == "passed"
            and run.total > 0
            and run.total == run.passed == len(contract.snapshot.get("cases", []))
            and fingerprint(run.code) == run.code_hash
        )
        delivered_count += int(delivered)
        if language and (project.language or "python") != language:
            continue
        if project.archived and not delivered:
            continue
        # Prefer a finished project over an unfinished duplicate; within each
        # status the query order selects the most recently updated one.
        previous = result.get(project.scenario_id)
        if previous is None or (delivered and previous["status"] != "delivered"):
            result[project.scenario_id] = {
                "status": "delivered" if delivered else "in_progress",
                "project_id": project.id,
                "language": project.language or "python",
            }
    return result, {
        "projects": len(projects),
        "delivered": delivered_count,
        "acceptance_runs": sum(r.kind == "acceptance" and r.status != "running" for r in runs),
    }


def payload(user_id):
    assessment = LearningAssessment.query.filter_by(user_id=user_id).first()
    if not assessment:
        return {"assessment": None, "plan": None}
    answers = current_answers(assessment.answers)
    language = answers["preferred_language"]
    ranked = ranked_scenarios(answers)
    by_id = {s["id"]: s for s in ranked}
    selected_ids = [sid for sid in assessment.recommended_ids if sid in by_id]
    selected_ids += [s["id"] for s in ranked if s["id"] not in selected_ids]
    statuses, stats = progress(user_id, language)
    goal_labels = {o["value"]: o["label"] for o in QUESTIONS[-1]["options"]}
    recommendations = []
    for order, scenario_id in enumerate(selected_ids[:6], 1):
        scenario = by_id[scenario_id]
        minutes = scenario.get("estimated_minutes", 45)
        learning_goal = scenario.get("learning_goal", "练习明确规则与实际验收").rstrip("。.!！")
        reason = f"围绕‘{goal_labels[answers['goal']]}’安排练习，{learning_goal}。"
        if minutes <= {"short": 15, "medium": 30, "long": 60}[answers["time"]]:
            reason += "预计时长适合你选择的单次学习时间。"
        recommendation = {
            key: scenario.get(key)
            for key in (
                "title",
                "subtitle",
                "level",
                "duration",
                "estimated_minutes",
                "skills",
                "learning_goal",
            )
        }
        recommendation.update(
            scenario_id=scenario_id,
            reason=reason,
            order=order,
            language=language,
            **{
                k: v
                for k, v in statuses.get(
                    scenario_id, {"status": "not_started", "project_id": None}
                ).items()
                if k != "language"
            },
        )
        recommendations.append(recommendation)
    level = chosen_level(answers)
    return {
        "assessment": {
            "answers": answers,
            "original_answers": assessment.answers,
            "version": assessment.version,
            "revision": assessment.revision,
            "updated_at": iso(assessment.updated_at),
        },
        "plan": {
            "level": LEVELS[level],
            "preferred_language": language,
            "language_label": language_label(language),
            "summary": LEVELS[level]["description"] + "先选择一个项目，完成后回到这里查看进度。",
            "recommendations": recommendations,
            "stats": stats,
            "source": "问卷自评用于安排练习，不是能力考试；交付进度来自当前账号的实际项目记录。",
            "updated_at": iso(assessment.updated_at),
        },
    }


def save(user_id, answers, revision):
    cleaned = validate_answers(answers)
    if type(revision) is not int or revision < 0:
        raise PlanError("问卷版本须为非负整数，请刷新后重试。")
    assessment = LearningAssessment.query.filter_by(user_id=user_id).first()
    expected = assessment.revision if assessment else 0
    if revision != expected:
        raise PlanError(
            "问卷已在其他窗口更新；本页答案仍可保留，请刷新后再确认。", 409, "STALE_ASSESSMENT"
        )
    fields = {
        "answers": cleaned,
        "recommended_ids": [s["id"] for s in ranked_scenarios(cleaned)[:6]],
        "revision": revision + 1,
        "version": VERSION,
        "updated_at": datetime.now(timezone.utc),
    }
    if assessment:
        count = LearningAssessment.query.filter_by(user_id=user_id, revision=revision).update(
            fields, synchronize_session=False
        )
        if count != 1:
            db.session.rollback()
            raise PlanError("问卷版本已改变，请刷新后重试。", 409, "STALE_ASSESSMENT")
    else:
        db.session.add(LearningAssessment(user_id=user_id, **fields))
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise PlanError("问卷已在其他窗口提交，请刷新后查看。", 409, "STALE_ASSESSMENT") from exc
    return payload(user_id)

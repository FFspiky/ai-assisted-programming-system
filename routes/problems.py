from bs4 import BeautifulSoup
from flask import Blueprint, request
from flask_login import current_user, login_required
from sqlalchemy import case, func

from models import Problem, Submission, db
from routes.api_response import api_error, api_success
from services.problem_metadata import CATEGORIES

problems_blueprint = Blueprint("problems", __name__)


@problems_blueprint.route("/problems", methods=["GET"])
def get_all_problems():
    category_order = {key: index for index, key in enumerate(CATEGORIES)}
    problems = Problem.query.order_by(
        case(category_order, value=Problem.category, else_=len(CATEGORIES)), Problem.id
    )
    accepted_problem_ids, attempted_problem_ids = set(), set()
    if current_user.is_authenticated:
        accepted_problem_ids = {
            row.problem_id
            for row in Submission.query.with_entities(Submission.problem_id)
            .filter_by(user_id=current_user.id, status="Accepted")
            .distinct()
            .all()
        }
        attempted_problem_ids = {
            row.problem_id
            for row in Submission.query.with_entities(Submission.problem_id)
            .filter_by(user_id=current_user.id)
            .distinct()
        }

    category_counts = dict(
        db.session.query(Problem.category, func.count(Problem.id)).group_by(Problem.category).all()
    )
    categories = [
        {"id": key, "name": name, "count": category_counts.get(key, 0)}
        for key, name in CATEGORIES.items()
    ]
    selected = request.args.get("category", "")
    difficulty = request.args.get("difficulty", "")
    state = request.args.get("state", "")
    query = request.args.get("q", "").strip().casefold()[:100]
    if selected and selected not in CATEGORIES:
        return api_error("INVALID_FILTER", "无效的分类", 400)
    if difficulty and difficulty not in {"简单", "中等", "困难"}:
        return api_error("INVALID_FILTER", "无效的难度", 400)
    if state and state not in {"unattempted", "attempted", "accepted"}:
        return api_error("INVALID_FILTER", "无效的练习状态", 400)
    if state and not current_user.is_authenticated:
        return api_error("AUTH_REQUIRED", "登录后可按练习状态筛选", 401)
    if selected:
        problems = problems.filter(Problem.category == selected)
    if difficulty:
        problems = problems.filter(Problem.difficulty == difficulty)
    if query:
        problems = problems.filter(
            func.lower(Problem.id + " " + Problem.title).contains(query, autoescape=True)
        )
    if state == "accepted":
        problems = problems.filter(Problem.id.in_(accepted_problem_ids))
    elif state == "attempted":
        problems = problems.filter(
            Problem.id.in_(attempted_problem_ids), ~Problem.id.in_(accepted_problem_ids)
        )
    elif state == "unattempted":
        problems = problems.filter(~Problem.id.in_(attempted_problem_ids))
    ids = [row.id for row in problems.with_entities(Problem.id).all()]
    total = len(ids)
    pagination = {}
    # The original unpaginated contract is retained for existing integrations.
    if "page" in request.args:
        try:
            page, size = max(1, int(request.args["page"])), min(
                50, max(1, int(request.args.get("page_size", 12)))
            )
        except ValueError:
            return api_error("INVALID_PAGE", "页码须为整数", 400)
        pages = max(1, (total + size - 1) // size)
        page = min(page, pages)
        problems = problems.offset((page - 1) * size).limit(size)
        pagination = {"page": page, "page_size": size, "pages": pages}

    problems_list = [
        {
            "id": p.id,
            "title": p.title,
            # 返回简短描述，可以在模型中增加一个short_description字段
            "description": BeautifulSoup(p.description, "html.parser").get_text(" ", strip=True)[
                :120
            ],
            "difficulty": p.difficulty,
            "category": p.category,
            "category_name": CATEGORIES.get(p.category, "未分类"),
            "tags": p.tags or [],
            "accepted": p.id in accepted_problem_ids,
            "practice_state": (
                "accepted"
                if p.id in accepted_problem_ids
                else "attempted" if p.id in attempted_problem_ids else "unattempted"
            ),
        }
        for p in problems
    ]
    data = {
        "problems": problems_list,
        "ids": ids,
        "total": total,
        "categories": categories,
        **pagination,
    }
    return api_success(data, problems=problems_list)


@problems_blueprint.route("/problems/<problem_id>", methods=["GET"])
def get_problem_details(problem_id):
    problem = db.session.get(Problem, problem_id)
    if not problem:
        return api_error("PROBLEM_NOT_FOUND", "题目未找到", 404)

    problem_data = {
        "id": problem.id,
        "title": problem.title,
        "description": problem.description,
        "difficulty": problem.difficulty,
        "category": problem.category,
        "category_name": CATEGORIES.get(problem.category, "未分类"),
        "tags": problem.tags or [],
        "source": problem.source,
    }
    return api_success({"problem": problem_data}, problem=problem_data)


@problems_blueprint.route("/submissions", methods=["GET"])
@login_required
def get_user_submissions():
    # 查询当前用户的所有提交记录，按时间倒序
    submissions = (
        db.session.query(Submission, Problem.title)
        .join(Problem, Submission.problem_id == Problem.id)
        .filter(Submission.user_id == current_user.id)
        .order_by(Submission.timestamp.desc())
        .all()
    )

    submissions_list = [
        {
            "problem_title": title,
            "problem_id": s.problem_id,
            "status": s.status,
            "language": s.language,
            "timestamp": s.timestamp.strftime("%Y-%m-%d %H:%M:%S"),  # 格式化时间
        }
        for s, title in submissions
    ]

    return api_success({"submissions": submissions_list}, submissions=submissions_list)

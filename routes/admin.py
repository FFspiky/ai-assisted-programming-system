# routes/admin.py
from functools import wraps

from bs4 import BeautifulSoup
from flask import Blueprint, request
from flask_login import current_user

from models import Problem, TestCase, db
from routes.api_response import api_error, api_success
from services.problem_metadata import CATEGORIES, validate_metadata

admin_blueprint = Blueprint("admin", __name__)

ALLOWED_DESCRIPTION_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "div",
    "em",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "ol",
    "p",
    "pre",
    "span",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}
ALLOWED_DESCRIPTION_ATTRS = {
    "a": {"href", "title"},
    "code": {"class"},
    "pre": {"class"},
}
ALLOWED_LINK_SCHEMES = ("http://", "https://", "mailto:", "#", "/", "./", "../")


def sanitize_description(tag):
    for blocked in tag.find_all(["script", "style", "iframe", "object", "embed", "svg", "math"]):
        blocked.decompose()

    for node in tag.find_all(True):
        tag_name = (node.name or "").lower()
        if tag_name not in ALLOWED_DESCRIPTION_TAGS:
            node.unwrap()
            continue

        allowed_attrs = ALLOWED_DESCRIPTION_ATTRS.get(tag_name, set())
        for attr in list(node.attrs):
            attr_lower = attr.lower()
            value = node.attrs.get(attr)
            if attr_lower not in allowed_attrs:
                del node.attrs[attr]
                continue
            if tag_name == "a" and attr_lower == "href":
                value_text = " ".join(value) if isinstance(value, list) else str(value)
                href = value_text.strip()
                if not href.lower().startswith(ALLOWED_LINK_SCHEMES):
                    del node.attrs[attr]
                else:
                    node.attrs[attr] = href
    return tag.decode_contents()


def _text_or_none(tag):
    if not tag:
        return None
    text = tag.get_text().strip()
    return text or None


def _problem_payload(problem):
    test_cases = problem.test_cases.all()
    return {
        "id": problem.id,
        "title": problem.title,
        "difficulty": problem.difficulty,
        "judge_mode": problem.judge_mode,
        "description": problem.description,
        "category": problem.category,
        "tags": problem.tags or [],
        "source": problem.source,
        "test_case_count": len(test_cases),
        "test_cases": [
            {
                "id": case.id,
                "input_data": case.input_data,
                "expected_output": case.expected_output,
                "is_public": case.is_public,
            }
            for case in test_cases
        ],
    }


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return api_error("ADMIN_REQUIRED", "需要管理员权限", 403)
        return f(*args, **kwargs)

    return decorated_function


@admin_blueprint.route("/problems", methods=["GET"])
@admin_required
def list_problems():
    problems = Problem.query.order_by(Problem.id.asc()).all()
    data = {
        "problems": [_problem_payload(problem) for problem in problems],
        "categories": CATEGORIES,
    }
    return api_success(data, problems=data["problems"])


@admin_blueprint.route("/problems/<problem_id>", methods=["PUT"])
@admin_required
def update_problem(problem_id):
    problem = db.session.get(Problem, problem_id)
    if problem is None:
        return api_error("PROBLEM_NOT_FOUND", "题目不存在", 404)

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    difficulty = (data.get("difficulty") or "简单").strip()
    description = (data.get("description") or "").strip()
    test_cases = data.get("test_cases")
    try:
        category, tags, source = validate_metadata(
            data.get("category", problem.category),
            data.get("tags", problem.tags or []),
            data.get("source", problem.source or ""),
        )
    except ValueError as exc:
        return api_error("INVALID_METADATA", str(exc), 400)

    if not title or not description:
        return api_error("VALIDATION_ERROR", "标题和题目描述不能为空", 400)
    if not isinstance(test_cases, list):
        return api_error("VALIDATION_ERROR", "测试用例必须是列表", 400)

    judge_mode = data.get("judge_mode", problem.judge_mode)
    if judge_mode not in ("text", "integer", "float"):
        return api_error("VALIDATION_ERROR", "判题模式必须为 text、integer 或 float", 400)
    for case in test_cases:
        if not isinstance(case, dict) or type(case.get("is_public", True)) is not bool:
            return api_error("VALIDATION_ERROR", "测试用例必须是对象，is_public 必须为布尔值", 400)
    problem.judge_mode = judge_mode
    problem.title = title
    problem.difficulty = difficulty or "简单"
    problem.category, problem.tags, problem.source = category, tags, source
    description_soup = BeautifulSoup(f"<div>{description}</div>", "lxml")
    problem.description = sanitize_description(description_soup.div)

    TestCase.query.filter_by(problem_id=problem_id).delete()
    for index, case in enumerate(test_cases, start=1):
        input_data = "" if case.get("input_data") is None else str(case.get("input_data"))
        expected_output = (
            "" if case.get("expected_output") is None else str(case.get("expected_output"))
        )
        if not expected_output.strip():
            return api_error("VALIDATION_ERROR", f"第 {index} 个测试用例 output 不能为空", 400)
        db.session.add(
            TestCase(
                input_data=input_data,
                expected_output=expected_output.strip(),
                problem_id=problem_id,
                is_public=case.get("is_public", True),
            )
        )

    db.session.commit()
    return api_success(
        {"problem": _problem_payload(problem)},
        message="题目已更新",
        problem=_problem_payload(problem),
    )


@admin_blueprint.route("/problems/<problem_id>", methods=["DELETE"])
@admin_required
def delete_problem(problem_id):
    problem = db.session.get(Problem, problem_id)
    if problem is None:
        return api_error("PROBLEM_NOT_FOUND", "题目不存在", 404)

    db.session.delete(problem)
    db.session.commit()
    return api_success(message="题目已删除")


@admin_blueprint.route("/problems/upload", methods=["POST"])
@admin_required
def upload_problems():
    if "file" not in request.files:
        return api_error("UPLOAD_FILE_MISSING", "没有找到上传的文件", 400)
    file = request.files["file"]
    if file.filename == "":
        return api_error("UPLOAD_FILE_EMPTY", "未选择文件", 400)
    if not file.filename.endswith(".html"):
        return api_error("UPLOAD_FILE_TYPE_INVALID", "请上传HTML格式的文件", 400)

    try:
        html_content = file.read().decode("utf-8")
        soup = BeautifulSoup(html_content, "lxml")

        problem_items = soup.find_all("div", class_="problem-item")
        if not problem_items:
            return api_error(
                "PROBLEM_ITEMS_MISSING", "在文件中未找到 class='problem-item' 的题目", 400
            )

        imported = []
        skipped = []
        parse_errors = []

        for index, item in enumerate(problem_items, start=1):
            prob_id_tag = item.find("div", class_="prob-id")
            title_tag = item.find("h2")
            prob_id = _text_or_none(prob_id_tag)
            if not prob_id and title_tag:
                prob_id = (title_tag.get("data-id") or "").strip() or None

            title = _text_or_none(title_tag)
            difficulty_tag = item.find("div", class_="difficulty")
            difficulty = _text_or_none(difficulty_tag) or "简单"

            description_tag = item.find("div", class_="description")
            description = sanitize_description(description_tag) if description_tag else ""

            missing_fields = []
            if not prob_id:
                missing_fields.append("题目ID")
            if not title:
                missing_fields.append("标题")
            if not description.strip():
                missing_fields.append("题目描述")

            if missing_fields:
                skipped.append(
                    {
                        "index": index,
                        "id": prob_id,
                        "title": title,
                        "reason": f"缺少核心字段: {', '.join(missing_fields)}",
                    }
                )
                continue

            problem = db.session.get(Problem, prob_id)
            action = "updated" if problem else "created"
            if not problem:
                problem = Problem(id=prob_id)

            category_tag, tags_tag, source_tag = (
                item.find(class_="category"),
                item.find(class_="tags"),
                item.find(class_="source"),
            )
            try:
                category, tags, source = validate_metadata(
                    (
                        _text_or_none(category_tag)
                        if category_tag
                        else problem.category or "uncategorized"
                    ),
                    (
                        [
                            t.strip()
                            for t in tags_tag.get_text().replace("，", ",").split(",")
                            if t.strip()
                        ]
                        if tags_tag
                        else problem.tags or []
                    ),
                    source_tag.get_text().strip() if source_tag else problem.source or "",
                )
            except ValueError as exc:
                skipped.append({"index": index, "id": prob_id, "title": title, "reason": str(exc)})
                continue

            problem.title = title
            problem.difficulty = difficulty
            problem.description = description
            problem.category, problem.tags, problem.source = category, tags, source
            db.session.merge(problem)

            TestCase.query.filter_by(problem_id=prob_id).delete()
            valid_test_case_count = 0
            test_cases = item.find_all("div", class_="test-case")
            for case_index, case in enumerate(test_cases, start=1):
                input_tag = case.find("pre", class_="input")
                output_tag = case.find("pre", class_="output")

                if not input_tag or not output_tag:
                    parse_errors.append(
                        {
                            "index": index,
                            "id": prob_id,
                            "test_case_index": case_index,
                            "reason": "测试用例缺少 input 或 output",
                        }
                    )
                    continue

                input_data = input_tag.get_text()
                output_data = output_tag.get_text().strip()
                if not output_data:
                    parse_errors.append(
                        {
                            "index": index,
                            "id": prob_id,
                            "test_case_index": case_index,
                            "reason": "测试用例 output 为空",
                        }
                    )
                    continue

                new_case = TestCase(
                    input_data=input_data,
                    expected_output=output_data,
                    problem_id=prob_id,
                )
                db.session.add(new_case)
                valid_test_case_count += 1

            imported.append(
                {
                    "index": index,
                    "id": prob_id,
                    "title": title,
                    "action": action,
                    "test_case_count": valid_test_case_count,
                }
            )

        db.session.commit()
        data = {
            "imported_count": len(imported),
            "skipped_count": len(skipped),
            "parse_error_count": len(parse_errors),
            "imported": imported,
            "skipped": skipped,
            "parse_errors": parse_errors,
        }
        message = (
            f"成功导入/更新了 {len(imported)} 道题目，"
            f"跳过 {len(skipped)} 道，解析问题 {len(parse_errors)} 条。"
        )
        return api_success(data, message=message)

    except Exception as e:
        db.session.rollback()
        return api_error("PROBLEM_IMPORT_FAILED", f"解析或保存时出错: {str(e)}", 500)

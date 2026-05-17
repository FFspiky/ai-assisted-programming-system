# routes/admin.py
from flask import Blueprint, request, jsonify
from models import db, Problem, TestCase
from functools import wraps
from flask_login import current_user
from bs4 import BeautifulSoup
import os

admin_blueprint = Blueprint('admin', __name__)


def sanitize_description(tag):
    for blocked in tag.find_all(["script", "style", "iframe", "object", "embed"]):
        blocked.decompose()
    for node in tag.find_all(True):
        for attr in list(node.attrs):
            attr_lower = attr.lower()
            value = node.attrs.get(attr)
            if attr_lower.startswith("on"):
                del node.attrs[attr]
                continue
            if attr_lower in {"href", "src"}:
                value_text = " ".join(value) if isinstance(value, list) else str(value)
                if value_text.strip().lower().startswith("javascript:"):
                    del node.attrs[attr]
    return tag.decode_contents()


def _text_or_none(tag):
    if not tag:
        return None
    text = tag.get_text().strip()
    return text or None


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return jsonify({"success": False, "error": "需要管理员权限"}), 403
        return f(*args, **kwargs)
    return decorated_function

@admin_blueprint.route('/problems/upload', methods=['POST'])
@admin_required
def upload_problems():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "没有找到上传的文件"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "未选择文件"}), 400
    if not file.filename.endswith('.html'):
        return jsonify({"success": False, "error": "请上传HTML格式的文件"}), 400

    try:
        html_content = file.read().decode('utf-8')
        soup = BeautifulSoup(html_content, 'lxml')
        
        problem_items = soup.find_all('div', class_='problem-item')
        if not problem_items:
            return jsonify({"success": False, "error": "在文件中未找到 class='problem-item' 的题目"}), 400
            
        imported = []
        skipped = []
        parse_errors = []

        for index, item in enumerate(problem_items, start=1):
            prob_id_tag = item.find('div', class_='prob-id')
            title_tag = item.find('h2')
            prob_id = _text_or_none(prob_id_tag)
            if not prob_id and title_tag:
                prob_id = (title_tag.get("data-id") or "").strip() or None

            title = _text_or_none(title_tag)
            difficulty_tag = item.find('div', class_='difficulty')
            difficulty = _text_or_none(difficulty_tag) or '简单'
            
            description_tag = item.find('div', class_='description')
            description = sanitize_description(description_tag) if description_tag else ''

            missing_fields = []
            if not prob_id:
                missing_fields.append("题目ID")
            if not title:
                missing_fields.append("标题")
            if not description.strip():
                missing_fields.append("题目描述")

            if missing_fields:
                skipped.append({
                    "index": index,
                    "id": prob_id,
                    "title": title,
                    "reason": f"缺少核心字段: {', '.join(missing_fields)}",
                })
                continue 

            problem = db.session.get(Problem, prob_id)
            action = "updated" if problem else "created"
            if not problem:
                problem = Problem(id=prob_id)
            
            problem.title = title
            problem.difficulty = difficulty
            problem.description = description
            db.session.merge(problem)

            TestCase.query.filter_by(problem_id=prob_id).delete()
            valid_test_case_count = 0
            test_cases = item.find_all('div', class_='test-case')
            for case_index, case in enumerate(test_cases, start=1):
                input_tag = case.find('pre', class_='input')
                output_tag = case.find('pre', class_='output')
                
                if not input_tag or not output_tag:
                    parse_errors.append({
                        "index": index,
                        "id": prob_id,
                        "test_case_index": case_index,
                        "reason": "测试用例缺少 input 或 output",
                    })
                    continue

                input_data = input_tag.get_text().strip()
                output_data = output_tag.get_text().strip()
                if not output_data:
                    parse_errors.append({
                        "index": index,
                        "id": prob_id,
                        "test_case_index": case_index,
                        "reason": "测试用例 output 为空",
                    })
                    continue

                new_case = TestCase(
                    input_data=input_data,
                    expected_output=output_data,
                    problem_id=prob_id,
                )
                db.session.add(new_case)
                valid_test_case_count += 1
            
            imported.append({
                "index": index,
                "id": prob_id,
                "title": title,
                "action": action,
                "test_case_count": valid_test_case_count,
            })
            
        db.session.commit()
        return jsonify({
            "success": True,
            "message": (
                f"成功导入/更新了 {len(imported)} 道题目，"
                f"跳过 {len(skipped)} 道，解析问题 {len(parse_errors)} 条。"
            ),
            "data": {
                "imported_count": len(imported),
                "skipped_count": len(skipped),
                "parse_error_count": len(parse_errors),
                "imported": imported,
                "skipped": skipped,
                "parse_errors": parse_errors,
            },
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": f"解析或保存时出错: {str(e)}"}), 500

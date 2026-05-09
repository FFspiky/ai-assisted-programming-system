# routes/admin.py
from flask import Blueprint, request, jsonify
from models import db, Problem, TestCase
from functools import wraps
from flask_login import current_user
from bs4 import BeautifulSoup
import os

admin_blueprint = Blueprint('admin', __name__)

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
            
        count = 0
        for item in problem_items:
            # --- 修改开始 ---
            # 1. 从 <div class="prob-id"> 获取ID
            prob_id_tag = item.find('div', class_='prob-id')
            prob_id = prob_id_tag.text.strip() if prob_id_tag else None

            title = item.find('h2').text.strip()
            difficulty_tag = item.find('div', class_='difficulty')
            difficulty = difficulty_tag.text.strip() if difficulty_tag else '简单' # 提供默认值
            
            description_tag = item.find('div', class_='description')
            description = description_tag.prettify() if description_tag else ''
            # --- 修改结束 ---

            if not all([prob_id, title, description]): # 确保核心数据存在
                continue 

            problem = Problem.query.get(prob_id)
            if not problem:
                problem = Problem(id=prob_id)
            
            problem.title = title
            problem.difficulty = difficulty
            problem.description = description
            db.session.merge(problem)

            TestCase.query.filter_by(problem_id=prob_id).delete()
            test_cases = item.find_all('div', class_='test-case')
            for case in test_cases:
                # --- 修改开始 ---
                # 2. 确保能安全地找到input和output
                input_tag = case.find('pre', class_='input')
                output_tag = case.find('pre', class_='output')
                
                if input_tag and output_tag:
                    input_data = input_tag.get_text().strip()
                    output_data = output_tag.get_text().strip()
                    if input_data and output_data: # 确保内容不为空
                        new_case = TestCase(input_data=input_data, expected_output=output_data, problem_id=prob_id)
                        db.session.add(new_case)
                # --- 修改结束 ---
            
            count += 1
            
        db.session.commit()
        return jsonify({"success": True, "message": f"成功导入/更新了 {count} 道题目。"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": f"解析或保存时出错: {str(e)}"}), 500
from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from models import Problem, Submission, db

problems_blueprint = Blueprint('problems', __name__)

@problems_blueprint.route('/problems', methods=['GET'])
def get_all_problems():
    problems = Problem.query.all()
    problems_list = [
        {
            "id": p.id, 
            "title": p.title, 
            # 返回简短描述，可以在模型中增加一个short_description字段
            "description": p.description[:100] + '...' if len(p.description) > 100 else p.description, 
            "difficulty": p.difficulty
        } for p in problems
    ]
    return jsonify({"success": True, "problems": problems_list})

@problems_blueprint.route('/problems/<problem_id>', methods=['GET'])
def get_problem_details(problem_id):
    problem = db.session.get(Problem, problem_id)
    if not problem:
        return jsonify({"success": False, "error": "题目未找到"}), 404
    
    return jsonify({
        "success": True,
        "problem": {
            "id": problem.id,
            "title": problem.title,
            "description": problem.description,
            "difficulty": problem.difficulty
        }
    })

@problems_blueprint.route('/submissions', methods=['GET'])
@login_required
def get_user_submissions():
    # 查询当前用户的所有提交记录，按时间倒序
    submissions = db.session.query(Submission, Problem.title)\
        .join(Problem, Submission.problem_id == Problem.id)\
        .filter(Submission.user_id == current_user.id)\
        .order_by(Submission.timestamp.desc())\
        .all()
    
    submissions_list = [
        {
            "problem_title": title,
            "problem_id": s.problem_id,
            "status": s.status,
            "language": s.language,
            "timestamp": s.timestamp.strftime('%Y-%m-%d %H:%M:%S') # 格式化时间
        } for s, title in submissions
    ]
    
    return jsonify({"success": True, "submissions": submissions_list})

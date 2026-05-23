from flask import Blueprint
from flask_login import login_required, current_user
from models import Problem, Submission, db
from routes.api_response import api_error, api_success

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
    return api_success({"problems": problems_list}, problems=problems_list)

@problems_blueprint.route('/problems/<problem_id>', methods=['GET'])
def get_problem_details(problem_id):
    problem = db.session.get(Problem, problem_id)
    if not problem:
        return api_error("PROBLEM_NOT_FOUND", "题目未找到", 404)

    problem_data = {
            "id": problem.id,
            "title": problem.title,
            "description": problem.description,
            "difficulty": problem.difficulty
    }
    return api_success({"problem": problem_data}, problem=problem_data)

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
    
    return api_success({"submissions": submissions_list}, submissions=submissions_list)

# routes/solution_checker.py
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, Submission, Problem, TestCase, User
from services.execute_runner import run_code # 假设您的执行代码服务在这里

solution_checker_blueprint = Blueprint("solution_checker", __name__)

@solution_checker_blueprint.route("/check-solution", methods=["POST"])
@login_required
def check_solution():
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    language = data.get("language", "Python")
    problem_id = data.get("problem_id", "")

    problem = db.session.get(Problem, problem_id)
    if not problem:
        return jsonify({"success": False, "error": "题目不存在"}), 404

    test_cases = problem.test_cases.all()
    if not test_cases:
        return jsonify({"success": False, "error": "该题目还没有测试用例"}), 400

    final_status = "Accepted"
    feedback_details = []

    for i, case in enumerate(test_cases):
        # 修正此处的函数调用，使用关键字参数传递输入
        run_result = run_code(code, language, input_text=case.input_data)
        
        actual_output = run_result.get("output", "").strip()
        expected_output = case.expected_output.strip()

        if not run_result.get("success"):
            final_status = "Runtime Error"
            feedback_details.append(f"测试用例 {i+1} 发生运行时错误: {run_result.get('error', '')}")
            break # 出现错误，直接中断
        
        if actual_output != expected_output:
            final_status = "Wrong Answer"
            feedback_details.append(f"测试用例 {i+1} 未通过: \n输入:\n{case.input_data}\n预期输出:\n{expected_output}\n你的输出:\n{actual_output}")
            break # 答案错误，直接中断
        
        feedback_details.append(f"测试用例 {i+1} 通过!")

    already_accepted = None
    if final_status == "Accepted":
        already_accepted = Submission.query.filter_by(
            user_id=current_user.id,
            problem_id=problem_id,
            status="Accepted"
        ).first()

    # 保存提交记录
    new_submission = Submission(
        code_submitted=code,
        language=language,
        status=final_status,
        feedback="\n".join(feedback_details),
        user_id=current_user.id,
        problem_id=problem_id
    )
    db.session.add(new_submission)

    if final_status == "Accepted" and already_accepted is None:
        user = db.session.get(User, current_user.id)
        user.points += 10 # 首次答对加分
    
    db.session.commit()

    return jsonify({
        "success": True,
        "status": final_status,
        "details": "\n".join(feedback_details),
        "new_points": current_user.points
    })

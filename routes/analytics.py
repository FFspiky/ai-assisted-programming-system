# routes/analytics.py
from flask import Blueprint, jsonify, request, Response
from flask_login import login_required, current_user
from models import db, Submission, Problem, User
import requests
import json
import time

# 从配置文件导入API信息
try:
    from config import API_KEY, API_URL, MODEL_NAME
except ImportError:
    API_KEY = ""
    API_URL = ""
    MODEL_NAME = ""

analytics_blueprint = Blueprint('analytics', __name__)

# --- 学习概览 API (已更新) ---
@analytics_blueprint.route('/learning_overview', methods=['GET'])
@login_required
def learning_overview():
    user_id = current_user.id
    total_submissions = Submission.query.filter_by(user_id=user_id).count()
    accepted_submissions = Submission.query.filter_by(user_id=user_id, status='Accepted').count()
    accuracy = round((accepted_submissions / total_submissions) * 100) if total_submissions > 0 else 0
    
    # 从数据库获取真实学习时长 (小时)
    learning_hours = round(current_user.learning_duration / 3600, 1)

    return jsonify({
        'success': True, 
        'data': {
            'total_solved': accepted_submissions, # <--- 修正拼写
            'accuracy': accuracy,
            'learning_hours': learning_hours
        }
    })

# --- 更新学习时长 API (新增) ---
@analytics_blueprint.route('/update_learning_time', methods=['POST'])
@login_required
def update_learning_time():
    data = request.get_json(silent=True) or {}
    duration_seconds = data.get('duration', 0)

    try:
        duration_seconds = int(duration_seconds)
    except (TypeError, ValueError):
        duration_seconds = 0

    if 0 < duration_seconds <= 8 * 60 * 60:
        user = db.session.get(User, current_user.id)
        user.learning_duration += int(duration_seconds)
        db.session.commit()
        return jsonify({'success': True, 'message': '学习时长已更新'})
    return jsonify({'success': False, 'message': '无效的时长'})

# --- 排行榜 API (新增) ---
@analytics_blueprint.route('/leaderboard', methods=['GET'])
def leaderboard():
    # 查询所有用户，并计算他们的解题数
    users_with_stats = db.session.query(
        User,
        db.func.count(db.func.distinct(Submission.problem_id)).label('solved_count')
    ).outerjoin(Submission, (User.id == Submission.user_id) & (Submission.status == 'Accepted'))\
     .group_by(User.id)\
     .order_by(db.desc('solved_count'), db.desc(User.learning_duration))\
     .limit(10).all()

    leaderboard_data = []
    for rank, (user, solved_count) in enumerate(users_with_stats, 1):
        leaderboard_data.append({
            'rank': rank,
            'username': user.username,
            'solved_count': solved_count,
            # 使用 or 0 来优雅地处理 None 的情况
            'learning_hours': round((user.learning_duration or 0) / 3600, 1)
        })

    return jsonify({'success': True, 'data': leaderboard_data})


# --- AI学习分析 API (已升级为流式输出) ---
@analytics_blueprint.route('/ai_learning_analysis_stream', methods=['GET'])
@login_required
def ai_learning_analysis_stream():
    user_id = current_user.id
    
    # 升级：获取最近20次提交记录
    recent_submissions = db.session.query(Submission, Problem.title, Problem.difficulty)\
        .join(Problem, Submission.problem_id == Problem.id)\
        .filter(Submission.user_id == user_id)\
        .order_by(Submission.timestamp.desc())\
        .limit(20).all()

    if not recent_submissions:
        def empty_stream():
            yield f"data: {json.dumps({'content': '<h3>开始您的编程之旅吧！</h3><p>我们还没有发现您的刷题记录。请先去“刷题”页面完成一些题目，AI 就能为您生成一份个性化的学习分析报告了。'})}\n\n"
        return Response(empty_stream(), mimetype='text/event-stream')

    # --- 精心设计的Prompt ---
    submission_details = ""
    for sub, title, difficulty in recent_submissions:
        submission_details += f"- 题目: '{title}' (难度: {difficulty}), 提交状态: {sub.status}\n"

    prompt = f"""
    你是一位资深的编程导师和数据分析专家。请根据以下提供的用户刷题记录，为用户 '{current_user.username}' 生成一份专业、有深度、鼓励人心的学习分析报告。

    **分析要求:**
    1.  **开场白**: 以亲切和鼓励的口吻开始。
    2.  **优势分析 (Strengths)**: 从提交记录中找出用户的优点，例如在某些类型的题目上表现出色、代码风格良好、或者进步很快。
    3.  **潜在提升点 (Areas for Improvement)**: 精准地指出用户可能存在的薄弱环节。例如，对特定算法不熟练、边界条件考虑不周、代码效率有待提高等。请用具体例子佐证。
    4.  **个性化学习建议 (Personalized Suggestions)**: 针对提升点，提供具体、可操作的学习建议。例如，推荐学习的知识点、建议练习的题目类型（无需指定具体题目）、或者改进代码的技巧。
    5.  **总结**: 用一段积极的话语结束，鼓励用户继续前行。

    **输出格式要求:**
    - 使用 Markdown 格式。
    - 必须包含 "优势分析", "潜在提升点", "个性化学习建议" 这三个H4标题（####）。
    - 语言风格：专业、清晰、有建设性且充满正能量。

    **用户的最近20条刷题记录:**
    {submission_details}

    请现在开始生成你的分析报告：
    """

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True  # 开启流式输出
    }

    def generate():
        if not API_KEY:
            yield f"data: {json.dumps({'error': '未配置 SILICONFLOW_API_KEY（可在 .env 或环境变量中设置）'}, ensure_ascii=False)}\n\n"
            return
        try:
            response = requests.post(API_URL, headers=headers, json=payload, stream=True)
            response.raise_for_status() # 如果请求失败则抛出异常
            
            for chunk in response.iter_lines():
                if chunk:
                    chunk_str = chunk.decode('utf-8')
                    if chunk_str.startswith('data: '):
                        data_str = chunk_str[6:]
                        if data_str.strip() == '[DONE]':
                            break
                        try:
                            data = json.loads(data_str)
                            content = data.get('choices', [{}])[0].get('delta', {}).get('content', '')
                            if content:
                                # 将内容封装成JSON格式发送
                                yield f"data: {json.dumps({'content': content})}\n\n"
                                time.sleep(0.02) # 控制一下输出速度，体验更好
                        except json.JSONDecodeError:
                            continue
        except requests.exceptions.RequestException as e:
            error_message = f"请求AI服务失败: {e}"
            yield f"data: {json.dumps({'error': error_message})}\n\n"

    return Response(generate(), mimetype='text/event-stream')

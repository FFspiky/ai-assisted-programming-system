# routes/analytics.py
import json
from datetime import datetime, timezone

from flask import Blueprint, Response, request, stream_with_context
from flask_login import current_user, login_required
from sqlalchemy import case

from models import Problem, Submission, User, db
from routes.api_response import api_error, api_success
from services.ai_client import AIClientError
from services.learning_analysis import stream_learning_analysis

analytics_blueprint = Blueprint("analytics", __name__)
LEARNING_TIME_DAILY_BUCKETS = {}
MAX_LEARNING_TIME_REPORT_SECONDS = 5 * 60
MAX_LEARNING_TIME_PER_DAY_SECONDS = 8 * 60 * 60


def _learning_day_key():
    return datetime.now(timezone.utc).date().isoformat()


def _get_today_reported_seconds(user_id):
    key = (_learning_day_key(), user_id)
    return LEARNING_TIME_DAILY_BUCKETS.get(key, 0)


def _add_today_reported_seconds(user_id, duration_seconds):
    key = (_learning_day_key(), user_id)
    reported = LEARNING_TIME_DAILY_BUCKETS.get(key, 0)
    allowed = max(0, MAX_LEARNING_TIME_PER_DAY_SECONDS - reported)
    accepted = min(duration_seconds, allowed)
    LEARNING_TIME_DAILY_BUCKETS[key] = reported + accepted
    return accepted, allowed


# --- 学习概览 API (已更新) ---
@analytics_blueprint.route("/learning_overview", methods=["GET"])
@login_required
def learning_overview():
    user_id = current_user.id
    total_submissions = Submission.query.filter_by(user_id=user_id).count()
    accepted_submissions = Submission.query.filter_by(user_id=user_id, status="Accepted").count()
    accuracy = (
        round((accepted_submissions / total_submissions) * 100) if total_submissions > 0 else 0
    )

    # 从数据库获取真实学习时长 (小时)
    learning_hours = round(current_user.learning_duration / 3600, 1)

    return api_success(
        {
            "total_solved": db.session.query(Submission.problem_id)
            .filter_by(user_id=user_id, status="Accepted")
            .distinct()
            .count(),
            "accuracy": accuracy,
            "learning_hours": learning_hours,
        }
    )


# --- 更新学习时长 API (新增) ---
@analytics_blueprint.route("/update_learning_time", methods=["POST"])
@login_required
def update_learning_time():
    data = request.get_json(silent=True) or {}
    duration_seconds = data.get("duration", 0)

    try:
        duration_seconds = int(duration_seconds)
    except (TypeError, ValueError):
        duration_seconds = 0

    if 0 < duration_seconds <= MAX_LEARNING_TIME_REPORT_SECONDS:
        accepted_seconds, _ = _add_today_reported_seconds(current_user.id, duration_seconds)
        if accepted_seconds <= 0:
            return api_error(
                "LEARNING_TIME_DAILY_LIMIT",
                "今日学习时长已达到上限",
                429,
                data={
                    "accepted_seconds": 0,
                    "daily_reported_seconds": _get_today_reported_seconds(current_user.id),
                },
            )

        user = db.session.get(User, current_user.id)
        user.learning_duration += int(accepted_seconds)
        db.session.commit()
        return api_success(
            {
                "accepted_seconds": accepted_seconds,
                "daily_reported_seconds": _get_today_reported_seconds(current_user.id),
            },
            message="学习时长已更新",
        )
    return api_error("INVALID_LEARNING_TIME", "无效的时长", 400)


# --- 排行榜 API (新增) ---
@analytics_blueprint.route("/leaderboard", methods=["GET"])
def leaderboard():
    # 查询所有用户，并计算解题数、提交数和通过数，让排行榜指标含义更清晰。
    users_with_stats = (
        db.session.query(
            User,
            db.func.count(
                db.distinct(case((Submission.status == "Accepted", Submission.problem_id)))
            ).label("solved_count"),
            db.func.count(Submission.id).label("submission_count"),
            db.func.count(case((Submission.status == "Accepted", 1))).label("accepted_count"),
        )
        .outerjoin(Submission, User.id == Submission.user_id)
        .group_by(User.id)
        .order_by(db.desc("solved_count"), db.desc(User.points), db.desc(User.learning_duration))
        .limit(10)
        .all()
    )

    leaderboard_data = []
    for rank, (user, solved_count, submission_count, accepted_count) in enumerate(
        users_with_stats, 1
    ):
        accuracy = round((accepted_count / submission_count) * 100) if submission_count else 0
        leaderboard_data.append(
            {
                "rank": rank,
                "username": user.username,
                "solved_count": solved_count,
                "points": user.points or 0,
                "learning_hours": round((user.learning_duration or 0) / 3600, 1),
                "accuracy": accuracy,
            }
        )

    return api_success(leaderboard_data)


# --- AI学习分析 API (已升级为流式输出) ---
@analytics_blueprint.route("/ai_learning_analysis_stream", methods=["GET"])
@login_required
def ai_learning_analysis_stream():
    user_id = current_user.id

    # 升级：获取最近20次提交记录
    recent_submissions = (
        db.session.query(Submission, Problem.title, Problem.difficulty)
        .join(Problem, Submission.problem_id == Problem.id)
        .filter(Submission.user_id == user_id)
        .order_by(Submission.timestamp.desc())
        .limit(20)
        .all()
    )

    if not recent_submissions:

        def empty_stream():
            yield f"data: {json.dumps({'content': '<h3>开始您的编程之旅吧！</h3><p>我们还没有发现您的刷题记录。请先去“刷题”页面完成一些题目，AI 就能为您生成一份个性化的学习分析报告了。'})}\n\n"

        return Response(empty_stream(), mimetype="text/event-stream")

    records = [
        {
            "problem_id": sub.problem_id,
            "title": title,
            "difficulty": difficulty,
            "status": sub.status,
            "language": sub.language,
            "submitted_at": sub.timestamp.isoformat(),
        }
        for sub, title, difficulty in recent_submissions
    ]
    username = current_user.username

    def generate():
        try:
            for content in stream_learning_analysis(username, records):
                yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
        except AIClientError as exc:
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")

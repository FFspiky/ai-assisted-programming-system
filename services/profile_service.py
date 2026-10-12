"""Account data and practice statistics derived from the signed-in user's records."""

import hashlib
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import case

from models import Problem, Submission, db

LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")


def iso_utc(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc).isoformat()


def user_payload(user):
    avatar = None
    if user.avatar_image:
        version = hashlib.sha256(user.avatar_image).hexdigest()[:12]
        avatar = f"/api/profile/avatar?v={version}"
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name or "",
        "email": user.email,
        "bio": user.bio or "",
        "location": user.location or "",
        "avatar_url": avatar,
        "points": user.points or 0,
        "created_at": iso_utc(user.created_at),
    }


def practice_stats(user, now=None):
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(LOCAL_TIMEZONE).date()
    # Calendar columns begin on Monday; future cells aren't counted.
    first_day = today - timedelta(days=today.weekday() + 51 * 7)
    start = (
        datetime.combine(first_day, datetime.min.time(), LOCAL_TIMEZONE)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )
    query = Submission.query.filter_by(user_id=user.id)
    count, attempted, solved, accepted = (
        db.session.query(
            db.func.count(Submission.id),
            db.func.count(db.distinct(Submission.problem_id)),
            db.func.count(
                db.distinct(case((Submission.status == "Accepted", Submission.problem_id)))
            ),
            db.func.count(case((Submission.status == "Accepted", 1))),
        )
        .filter(Submission.user_id == user.id)
        .one()
    )
    days = Counter(
        timestamp.replace(tzinfo=timezone.utc).astimezone(LOCAL_TIMEZONE).date()
        for (timestamp,) in query.with_entities(Submission.timestamp)
        .filter(Submission.timestamp >= start)
        .all()
    )
    activity = []
    day = first_day
    while day <= today:
        activity.append({"date": day.isoformat(), "count": days[day]})
        day += timedelta(days=1)
    languages = (
        db.session.query(Submission.language, db.func.count(Submission.id))
        .filter(Submission.user_id == user.id)
        .group_by(Submission.language)
        .order_by(db.func.count(Submission.id).desc())
        .all()
    )
    difficulty = (
        db.session.query(Problem.difficulty, db.func.count(db.distinct(Problem.id)))
        .join(Submission, Submission.problem_id == Problem.id)
        .filter(Submission.user_id == user.id, Submission.status == "Accepted")
        .group_by(Problem.difficulty)
        .all()
    )
    recent = (
        db.session.query(Submission, Problem.title)
        .join(Problem, Submission.problem_id == Problem.id)
        .filter(Submission.user_id == user.id)
        .order_by(Submission.timestamp.desc(), Submission.id.desc())
        .limit(20)
        .all()
    )
    return {
        "practice_seconds": user.learning_duration or 0,
        "attempted_problems": attempted,
        "solved_problems": solved,
        "total_submissions": count,
        "accepted_submissions": accepted,
        "acceptance_rate": round(accepted / count * 100, 1) if count else 0,
        "active_days": len([day for day in days if day <= today]),
        "activity": activity,
        "languages": [{"language": name, "count": total} for name, total in languages],
        "difficulties": [{"difficulty": name, "count": total} for name, total in difficulty],
        "recent_submissions": [
            {
                "id": sub.id,
                "problem_id": sub.problem_id,
                "title": title,
                "language": sub.language,
                "status": sub.status,
                "timestamp": iso_utc(sub.timestamp),
            }
            for sub, title in recent
        ],
    }

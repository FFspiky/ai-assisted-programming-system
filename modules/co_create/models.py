import uuid
from datetime import datetime, timezone

from models import db


def now():
    return datetime.now(timezone.utc)


class CoCreateSession(db.Model):
    __tablename__ = "co_create_session"
    id = db.Column(db.String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    mode = db.Column(db.String(16), nullable=False)
    scenario_id = db.Column(db.String(40), nullable=False)
    # Nullable association preserves historical finite-scene sessions and deleted problems.
    problem_id = db.Column(db.String(50), nullable=True, index=True)
    language = db.Column(db.String(20), nullable=False, default="python", server_default="python")
    title = db.Column(db.String(120), nullable=False)
    revision = db.Column(db.Integer, nullable=False, default=0)
    state = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    updated_at = db.Column(db.DateTime, nullable=False, default=now)

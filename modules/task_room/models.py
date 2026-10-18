"""Task-room data is separate from practice submissions and retired workshop data."""

import uuid
from datetime import datetime, timezone

from models import db


def now():
    return datetime.now(timezone.utc)


def new_id():
    return uuid.uuid4().hex


class TaskProject(db.Model):
    __tablename__ = "task_room_project"
    id = db.Column(db.String(32), primary_key=True, default=new_id)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    scenario_id = db.Column(db.String(40), nullable=False)
    language = db.Column(db.String(16), nullable=False, default="python")
    title = db.Column(db.String(120), nullable=False)
    state = db.Column(db.String(20), nullable=False, default="discovery")
    archived = db.Column(db.Boolean, nullable=False, default=False)
    revision = db.Column(db.Integer, nullable=False, default=0)
    draft_revision = db.Column(db.Integer, nullable=False, default=0)
    code = db.Column(db.Text, nullable=False, default="")
    delivery = db.Column(db.JSON, nullable=True)
    events = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    updated_at = db.Column(db.DateTime, nullable=False, default=now)


class TaskContract(db.Model):
    __tablename__ = "task_room_contract"
    id = db.Column(db.String(32), primary_key=True, default=new_id)
    project_id = db.Column(
        db.String(32), db.ForeignKey("task_room_project.id"), nullable=False, index=True
    )
    version = db.Column(db.Integer, nullable=False)
    snapshot = db.Column(db.JSON, nullable=False)
    change_id = db.Column(db.String(40), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    __table_args__ = (db.UniqueConstraint("project_id", "version"),)


class TaskMessage(db.Model):
    __tablename__ = "task_room_message"
    id = db.Column(db.String(32), primary_key=True, default=new_id)
    project_id = db.Column(
        db.String(32), db.ForeignKey("task_room_project.id"), nullable=False, index=True
    )
    role = db.Column(db.String(16), nullable=False)
    intent = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    model = db.Column(db.String(120), nullable=True)
    operation_id = db.Column(db.String(64), nullable=True)
    payload = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    __table_args__ = (db.UniqueConstraint("project_id", "operation_id"),)


class TaskRun(db.Model):
    __tablename__ = "task_room_run"
    id = db.Column(db.String(32), primary_key=True, default=new_id)
    project_id = db.Column(
        db.String(32), db.ForeignKey("task_room_project.id"), nullable=False, index=True
    )
    contract_id = db.Column(db.String(32), db.ForeignKey("task_room_contract.id"), nullable=False)
    contract_version = db.Column(db.Integer, nullable=False)
    kind = db.Column(db.String(16), nullable=False)
    language = db.Column(db.String(16), nullable=False, default="python")
    code = db.Column(db.Text, nullable=False)
    code_hash = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="running")
    passed = db.Column(db.Integer, nullable=False, default=0)
    total = db.Column(db.Integer, nullable=False, default=0)
    results = db.Column(db.JSON, nullable=False, default=list)
    execution = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=now)

# models.py
from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


# 用户模型 (增加 is_admin 和 learning_duration 字段)
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    points = db.Column(db.Integer, default=0)
    is_admin = db.Column(db.Boolean, default=False)
    # 新增：学习总时长，单位为秒
    learning_duration = db.Column(db.Integer, default=0)
    display_name = db.Column(db.String(80), nullable=False, default="", server_default="")
    bio = db.Column(db.String(160), nullable=False, default="", server_default="")
    location = db.Column(db.String(80), nullable=False, default="", server_default="")
    avatar_image = db.Column(db.LargeBinary, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=True)
    auth_version = db.Column(db.Integer, nullable=False, default=0, server_default="0")

    help_mode = db.Column(
        db.String(20), nullable=False, default="learning", server_default="learning"
    )
    help_revision = db.Column(db.Integer, nullable=False, default=0, server_default="0")

    submissions = db.relationship("Submission", backref="author", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# 题目模型 (保持不变)
class Problem(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(20), default="简单")
    judge_mode = db.Column(db.String(20), nullable=False, default="text", server_default="text")
    category = db.Column(
        db.String(40), nullable=False, default="uncategorized", server_default="uncategorized"
    )
    tags = db.Column(db.JSON, nullable=False, default=list, server_default="[]")
    source = db.Column(db.String(200), nullable=False, default="", server_default="")
    test_cases = db.relationship(
        "TestCase", backref="problem", lazy="dynamic", cascade="all, delete-orphan"
    )


# 测试用例模型 (保持不变)
class TestCase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    is_public = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    input_data = db.Column(db.Text, nullable=False)
    expected_output = db.Column(db.Text, nullable=False)
    problem_id = db.Column(db.String(50), db.ForeignKey("problem.id"), nullable=False)


# 提交记录模型 (保持不变)
class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code_submitted = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False, index=True)
    feedback = db.Column(db.Text, nullable=True)
    evidence_snapshot = db.Column(db.JSON, nullable=True)
    diagnosis = db.Column(db.JSON, nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    problem_id = db.Column(db.String(50), db.ForeignKey("problem.id"), nullable=False, index=True)


class LearningHelp(db.Model):
    """A requested help level and the content actually returned, never a mastery score."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("submission.id"), nullable=True, index=True)
    source = db.Column(db.String(20), nullable=False)
    mode = db.Column(db.String(20), nullable=False)
    mode_revision = db.Column(db.Integer, nullable=False)
    requested_level = db.Column(db.Integer, nullable=False)
    returned_level = db.Column(db.Integer, nullable=True)
    state = db.Column(db.String(20), nullable=False, default="pending")
    request_snapshot = db.Column(db.JSON, nullable=False)
    result = db.Column(db.JSON, nullable=True)
    model = db.Column(db.String(120), nullable=False)
    prompt_version = db.Column(db.String(60), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    shown_at = db.Column(db.DateTime, nullable=True)


class CodeProposal(db.Model):
    """Immutable candidate attached to one explicitly requested help response."""

    id = db.Column(db.Integer, primary_key=True)
    help_id = db.Column(db.Integer, db.ForeignKey("learning_help.id"), nullable=True, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("submission.id"), nullable=True, index=True)
    base_code = db.Column(db.Text, nullable=False)
    candidate_code = db.Column(db.Text, nullable=False)
    edits = db.Column(db.JSON, nullable=False)
    state = db.Column(db.String(20), nullable=False, default="pending")
    revision = db.Column(db.Integer, nullable=False, default=0)
    problem_id = db.Column(db.String(50), nullable=True, index=True)
    language = db.Column(db.String(16), nullable=True)
    source = db.Column(db.String(20), nullable=False, default="panel", server_default="panel")
    co_create_session_id = db.Column(db.String(32), nullable=True)
    co_create_candidate_id = db.Column(db.String(100), nullable=True)
    __table_args__ = (
        db.UniqueConstraint(
            "co_create_session_id", "co_create_candidate_id", name="uq_proposal_co_create"
        ),
    )
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class PracticeEvent(db.Model):
    __table_args__ = (db.UniqueConstraint("user_id", "operation_id", name="uq_practice_operation"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    problem_id = db.Column(db.String(50), nullable=False, index=True)
    language = db.Column(db.String(50), nullable=False)
    submission_id = db.Column(db.Integer, db.ForeignKey("submission.id"), nullable=True)
    proposal_id = db.Column(
        db.Integer, db.ForeignKey("code_proposal.id"), nullable=True, index=True
    )
    kind = db.Column(db.String(30), nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    operation_id = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class LearningAssessment(db.Model):
    """Latest self-report and a stable, resumable sequence of task-room projects."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    answers = db.Column(db.JSON, nullable=False)
    recommended_ids = db.Column(db.JSON, nullable=False, default=list)
    revision = db.Column(db.Integer, nullable=False, default=1)
    version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class WorkshopSuggestion(db.Model):
    """Retired feature history; retained with its migration to preserve existing data."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    scene = db.Column(db.String(20), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    base_fingerprint = db.Column(db.String(64), nullable=False)
    result = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class WorkshopRun(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    scene = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(80), nullable=False)
    code = db.Column(db.Text, nullable=False)
    params = db.Column(db.JSON, nullable=False)
    trace = db.Column(db.JSON, nullable=False)
    execution = db.Column(db.JSON, nullable=False)
    provenance = db.Column(db.JSON, nullable=False)
    fingerprint = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class WorkshopProject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(80), nullable=False)
    scene = db.Column(db.String(20), nullable=False)
    revision = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class WorkshopVersion(db.Model):
    __table_args__ = (db.UniqueConstraint("project_id", "number", name="uq_workshop_version"),)
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("workshop_project.id"), nullable=False, index=True
    )
    run_id = db.Column(db.Integer, db.ForeignKey("workshop_run.id"), nullable=False)
    number = db.Column(db.Integer, nullable=False)
    palette = db.Column(db.String(20), nullable=False, default="lagoon")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

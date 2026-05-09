# models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

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
    
    submissions = db.relationship('Submission', backref='author', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# 题目模型 (保持不变)
class Problem(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(20), default='简单')
    test_cases = db.relationship('TestCase', backref='problem', lazy='dynamic', cascade="all, delete-orphan")

# 测试用例模型 (保持不变)
class TestCase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    input_data = db.Column(db.Text, nullable=False)
    expected_output = db.Column(db.Text, nullable=False)
    problem_id = db.Column(db.String(50), db.ForeignKey('problem.id'), nullable=False)

# 提交记录模型 (保持不变)
class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code_submitted = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False) 
    feedback = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    problem_id = db.Column(db.String(50), db.ForeignKey('problem.id'), nullable=False)
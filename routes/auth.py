import re
import secrets

from flask import Blueprint, request, session
from flask_login import current_user, login_required, login_user, logout_user

from models import User, db
from routes.api_response import api_error, api_success
from services.profile_service import user_payload
from services.rate_limiter import allow_request, reset_limit

auth_blueprint = Blueprint("auth", __name__)
LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 5
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 15 * 60


@auth_blueprint.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if not all([username, email, password]):
        return api_error("VALIDATION_ERROR", "所有字段都不能为空", 400)
    if not 3 <= len(username) <= 80:
        return api_error("VALIDATION_ERROR", "用户名长度应为 3-80 个字符", 400)
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return api_error("VALIDATION_ERROR", "邮箱格式不正确", 400)
    if len(password) < 8:
        return api_error("VALIDATION_ERROR", "密码长度至少为 8 个字符", 400)

    if User.query.filter_by(username=username).first() is not None:
        return api_error("USERNAME_EXISTS", "用户名已存在", 409)

    if User.query.filter_by(email=email).first() is not None:
        return api_error("EMAIL_EXISTS", "邮箱已被注册", 409)

    new_user = User(username=username, email=email)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    return api_success(message="注册成功！", http_status=201)


@auth_blueprint.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    client_key = f"login:{request.remote_addr or 'unknown'}:{username}"

    if not allow_request(
        client_key,
        LOGIN_RATE_LIMIT_MAX_ATTEMPTS,
        LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    ):
        return api_error("LOGIN_RATE_LIMITED", "登录失败次数过多，请 15 分钟后再试", 429)

    user = User.query.filter_by(username=username).first()

    if user is None or not user.check_password(password):
        return api_error("INVALID_CREDENTIALS", "用户名或密码错误", 401)

    reset_limit(client_key)
    login_user(user, remember=False)  # 默认不持久化登录，关闭浏览器后需重新登录
    session["auth_version"] = user.auth_version
    session["csrf_token"] = secrets.token_urlsafe(32)
    data = {
        "user": user_payload(user),
        "csrf_token": session["csrf_token"],
    }
    return api_success(data, message="登录成功", user=data["user"], csrf_token=data["csrf_token"])


@auth_blueprint.route("/logout", methods=["POST"])
def logout():
    session.pop("csrf_token", None)
    logout_user()
    return api_success(message="已成功登出")


@auth_blueprint.route("/current_user", methods=["GET"])
@login_required
def get_current_user():
    # current_user 由 Flask-Login 提供
    user_data = user_payload(current_user)
    return api_success({"user": user_data}, user=user_data)


@auth_blueprint.route("/unauthorized")
def unauthorized():
    # 当Flask-Login需要登录但用户未登录时，会调用此函数
    return api_error("AUTH_REQUIRED", "需要登录", 401)

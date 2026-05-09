from flask import Blueprint, request, jsonify
from models import db, User
from flask_login import login_user, logout_user, login_required, current_user
import re
import time
from collections import defaultdict

auth_blueprint = Blueprint('auth', __name__)
LOGIN_ATTEMPTS = defaultdict(list)

@auth_blueprint.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''

    if not all([username, email, password]):
        return jsonify({"success": False, "error": "所有字段都不能为空"}), 400
    if not 3 <= len(username) <= 80:
        return jsonify({"success": False, "error": "用户名长度应为 3-80 个字符"}), 400
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify({"success": False, "error": "邮箱格式不正确"}), 400
    if len(password) < 8:
        return jsonify({"success": False, "error": "密码长度至少为 8 个字符"}), 400

    if User.query.filter_by(username=username).first() is not None:
        return jsonify({"success": False, "error": "用户名已存在"}), 409

    if User.query.filter_by(email=email).first() is not None:
        return jsonify({"success": False, "error": "邮箱已被注册"}), 409

    new_user = User(username=username, email=email)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"success": True, "message": "注册成功！"}), 201

@auth_blueprint.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    client_key = f"{request.remote_addr or 'unknown'}:{username}"
    now = time.time()
    LOGIN_ATTEMPTS[client_key] = [
        item for item in LOGIN_ATTEMPTS[client_key] if now - item < 15 * 60
    ]

    if len(LOGIN_ATTEMPTS[client_key]) >= 5:
        return jsonify({"success": False, "error": "登录失败次数过多，请 15 分钟后再试"}), 429

    user = User.query.filter_by(username=username).first()

    if user is None or not user.check_password(password):
        LOGIN_ATTEMPTS[client_key].append(now)
        return jsonify({"success": False, "error": "用户名或密码错误"}), 401

    LOGIN_ATTEMPTS.pop(client_key, None)
    login_user(user, remember=False) # 默认不持久化登录，关闭浏览器后需重新登录
    return jsonify({
        "success": True, 
        "message": "登录成功",
        "user": {"username": user.username, "points": user.points}
    }), 200

@auth_blueprint.route('/logout', methods=['POST'])
def logout():
    logout_user()
    return jsonify({"success": True, "message": "已成功登出"}), 200

@auth_blueprint.route('/current_user', methods=['GET'])
@login_required
def get_current_user():
    # current_user 由 Flask-Login 提供
    return jsonify({
        "success": True,
        "user": {
            "username": current_user.username,
            "email": current_user.email,
            "points": current_user.points
        }
    }), 200

@auth_blueprint.route('/unauthorized')
def unauthorized():
    # 当Flask-Login需要登录但用户未登录时，会调用此函数
    return jsonify({"success": False, "error": "需要登录"}), 401

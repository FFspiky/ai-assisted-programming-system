from flask import Blueprint, request, jsonify
from models import db, User
from flask_login import login_user, logout_user, login_required, current_user

auth_blueprint = Blueprint('auth', __name__)

@auth_blueprint.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not all([username, email, password]):
        return jsonify({"success": False, "error": "所有字段都不能为空"}), 400

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
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()

    if user is None or not user.check_password(password):
        return jsonify({"success": False, "error": "用户名或密码错误"}), 401

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

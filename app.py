# app.py

import os
import re
import secrets
import sys

import click
from flask import Flask, g, redirect, render_template, request, session, url_for
from flask_cors import CORS
from flask_login import LoginManager, current_user, login_required, logout_user
from flask_migrate import Migrate

# 本机演示：支持从 .env 读取配置（不会影响线上部署）
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

# 1. 先从 models.py 导入 db 对象
from config import ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_USERNAME, CORS_ORIGINS
from models import User, db
from modules.co_create import models as co_create_models  # noqa: F401
from modules.task_room import models as task_room_models  # noqa: F401
from modules.task_room import register_task_room
from routes.api_response import api_error, api_success

# 2. 创建并配置 Flask 应用实例
app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app, resources={r"/api/*": {"origins": CORS_ORIGINS}}, supports_credentials=True)

basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///" + os.path.join(basedir, "app.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)

# 3. 初始化数据库和迁移工具
#    将 db 和 migrate 与 app 实例关联起来
db.init_app(app)
migrate = Migrate(app, db)


def should_auto_create_database():
    if os.getenv("AUTO_CREATE_DATABASE", "1") != "1":
        return False
    return "db" not in sys.argv


# 本机演示：没有执行迁移时也能创建表；管理员仅在显式配置环境变量时初始化。
if should_auto_create_database():
    with app.app_context():
        db.create_all()
        if ADMIN_USERNAME and ADMIN_PASSWORD and ADMIN_EMAIL:
            admin_user = User.query.filter_by(username=ADMIN_USERNAME).first()
            if admin_user is None:
                admin_user = User(username=ADMIN_USERNAME, email=ADMIN_EMAIL, is_admin=True)
                admin_user.set_password(ADMIN_PASSWORD)
                db.session.add(admin_user)
                db.session.commit()

# 4. 初始化登录管理器
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.unauthorized"


@login_manager.unauthorized_handler
def handle_unauthorized():
    return api_error("AUTH_REQUIRED", "需要登录", 401)


@login_manager.user_loader
def load_user(user_id):
    # 这个函数现在可以安全地查询数据库了
    user = db.session.get(User, int(user_id))
    if user and session.get("auth_version", 0) == user.auth_version:
        return user
    return None


@app.cli.command("create-admin")
@click.option("--username", prompt=True)
@click.option("--email", prompt=True)
@click.password_option()
def create_admin(username, email, password):
    existing = User.query.filter((User.username == username) | (User.email == email)).first()
    if existing:
        raise click.ClickException("用户名或邮箱已存在")

    admin_user = User(username=username, email=email, is_admin=True)
    admin_user.set_password(password)
    db.session.add(admin_user)
    db.session.commit()
    click.echo(f"管理员账号已创建: {username}")


@app.cli.command("seed-demo")
def seed_demo():
    from services.demo_problems import seed_demo_problems

    click.echo("新增演示题：" + ", ".join(seed_demo_problems()))


@app.cli.command("seed-library")
def seed_library_command():
    """Import the built-in 60 problems, preserving all existing IDs."""
    from services.problem_library import seed_library

    result = seed_library()
    click.echo(f"新增 {len(result['added'])} 题；已有 {len(result['skipped'])} 题已跳过。")


@app.before_request
def disable_remember_auto_login():
    # 如果用户是通过 remember cookie 自动恢复的非 fresh 会话，强制退出，
    # 保证每次重新打开网站时默认是未登录状态。
    if current_user.is_authenticated and not getattr(current_user, "is_anonymous", True):
        from flask import session

        if not session.get("_fresh", False):
            logout_user()


@app.before_request
def validate_json_request():
    if request.path == "/api/profile/ai-settings":
        request.max_content_length = 16 * 1024
    if request.path.startswith("/api/learning-plan"):
        request.max_content_length = 32 * 1024
    if request.path.startswith("/api/task-room/"):
        request.max_content_length = 160 * 1024
    if request.path == "/api/profile/avatar":
        request.max_content_length = 3 * 1024 * 1024
    if request.path.startswith("/api/") and request.is_json:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return api_error("INVALID_JSON", "请求必须是 JSON 对象", 400)
        for name in (
            "language",
            "code",
            "message",
            "username",
            "email",
            "password",
            "prefix",
            "suffix",
            "problem_id",
        ):
            if name in data and not isinstance(data[name], str):
                return api_error("INVALID_FIELD", f"{name}必须是字符串", 400)
    return None


@app.before_request
def protect_state_changing_requests():
    if request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        return None
    if not request.path.startswith("/api/"):
        return None
    if not current_user.is_authenticated:
        return None

    expected_token = session.get("csrf_token")
    provided_token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
    if not expected_token or not secrets.compare_digest(expected_token, provided_token or ""):
        return api_error("CSRF_INVALID", "CSRF token 无效或缺失", 403)
    return None


@app.get("/api/csrf-token")
@login_required
def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return api_success({"csrf_token": token}, csrf_token=token)


@app.before_request
def require_user_ai_configuration():
    if request.method not in {"GET", "POST"} or not current_user.is_authenticated:
        return None
    ai_paths = {
        "/api/ai-chat-stream",
        "/api/ai-inline-complete-stream",
        "/api/optimize-code",
        "/api/ai_learning_analysis_stream",
        "/api/assess-learning-path",
    }
    is_ai = request.path in ai_paths or (
        request.method == "POST"
        and (
            re.fullmatch(r"/api/submissions/\d+/(diagnosis|help)", request.path)
            or re.fullmatch(
                r"/api/co-create/sessions/[^/]+/(generate|review-generate)", request.path
            )
            or re.fullmatch(r"/api/task-room/projects/[^/]+/messages", request.path)
        )
    )
    if is_ai:
        if (
            request.path.startswith("/api/co-create/")
            and (request.get_json(silent=True) or {}).get("source") == "teaching"
        ):
            return None
        from services.ai_settings import resolve_key

        key = resolve_key(current_user.id)
        if not key:
            return api_error(
                "AI_KEY_REQUIRED",
                "未配置 API Key，请前往个人资料页配置后再使用 AI 功能。",
                428,
                settings_url="/profile.html#ai-settings",
            )
        # Streaming starts after the ORM request session has been torn down.
        g.ai_api_key = key
    return None


# 5. 在所有东西都初始化完毕后，再导入并注册蓝图
#    这是避免循环导入的关键！
from routes.admin import admin_blueprint
from routes.ai_checker import ai_checker_blueprint
from routes.analytics import analytics_blueprint
from routes.assessment import assessment_blueprint
from routes.auth import auth_blueprint
from routes.autocomplete import autocomplete_blueprint
from routes.execute import execute_blueprint
from routes.helper import generate_blueprint
from routes.pages import pages_blueprint
from routes.problems import problems_blueprint
from routes.profile import profile_blueprint
from routes.solution_checker import solution_checker_blueprint
from routes.tutoring import tutoring_blueprint

app.register_blueprint(auth_blueprint, url_prefix="/api")
app.register_blueprint(problems_blueprint, url_prefix="/api")
app.register_blueprint(solution_checker_blueprint, url_prefix="/api")
app.register_blueprint(admin_blueprint, url_prefix="/api/admin")
app.register_blueprint(analytics_blueprint, url_prefix="/api")
app.register_blueprint(pages_blueprint)
app.register_blueprint(execute_blueprint)
app.register_blueprint(ai_checker_blueprint)
app.register_blueprint(generate_blueprint)
app.register_blueprint(assessment_blueprint)
app.register_blueprint(autocomplete_blueprint)
app.register_blueprint(tutoring_blueprint, url_prefix="/api")
app.register_blueprint(profile_blueprint, url_prefix="/api")
from routes.practice_history import practice_history_blueprint

app.register_blueprint(practice_history_blueprint, url_prefix="/api")
register_task_room(app)
from modules.co_create.routes import blueprint as co_create_blueprint

app.register_blueprint(co_create_blueprint)


# 页面路由
@app.route("/")
@app.route("/index.html")
def index():
    return render_template("index.html")


@app.route("/login.html")
def login_page():
    return render_template("login.html")


@app.route("/register.html")
def register_page():
    return render_template("register.html")


@app.route("/admin")
def admin_page():
    if not current_user.is_authenticated or not current_user.is_admin:
        return redirect(url_for("index"))
    return render_template("admin.html")


# 只有在直接运行此脚本时，才启动服务器
if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "5001"))
    app.run(debug=debug, port=port, host=host)

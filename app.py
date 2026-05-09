# app.py

import os
from flask import Flask, render_template, redirect, url_for
from flask_cors import CORS
from flask_migrate import Migrate
from flask_login import LoginManager, current_user, logout_user

# 本机演示：支持从 .env 读取配置（不会影响线上部署）
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

# 1. 先从 models.py 导入 db 对象
from models import db, User
from config import ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL

# 2. 创建并配置 Flask 应用实例
app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'local-demo-secret-key') 

# 3. 初始化数据库和迁移工具
#    将 db 和 migrate 与 app 实例关联起来
db.init_app(app)
migrate = Migrate(app, db)

# 本机演示：确保首次运行能直接注册/登录（没有执行迁移也能用）
with app.app_context():
    db.create_all()
    admin_user = User.query.filter_by(username=ADMIN_USERNAME).first()
    if admin_user is None:
        admin_user = User(username=ADMIN_USERNAME, email=ADMIN_EMAIL, is_admin=True)
        admin_user.set_password(ADMIN_PASSWORD)
        db.session.add(admin_user)
    else:
        admin_user.email = ADMIN_EMAIL
        admin_user.is_admin = True
        admin_user.set_password(ADMIN_PASSWORD)
    db.session.commit()

# 4. 初始化登录管理器
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.unauthorized' 

@login_manager.user_loader
def load_user(user_id):
    # 这个函数现在可以安全地查询数据库了
    return User.query.get(int(user_id))


@app.before_request
def disable_remember_auto_login():
    # 如果用户是通过 remember cookie 自动恢复的非 fresh 会话，强制退出，
    # 保证每次重新打开网站时默认是未登录状态。
    if current_user.is_authenticated and not getattr(current_user, "is_anonymous", True):
        from flask import session
        if not session.get("_fresh", False):
            logout_user()

# 5. 在所有东西都初始化完毕后，再导入并注册蓝图
#    这是避免循环导入的关键！
from routes.execute import execute_blueprint
from routes.ai_checker import ai_checker_blueprint
from routes.helper import generate_blueprint
from routes.autocomplete import autocomplete_blueprint
from routes.solution_checker import solution_checker_blueprint
from routes.auth import auth_blueprint
from routes.problems import problems_blueprint
from routes.pages import pages_blueprint
from routes.admin import admin_blueprint 
from routes.assessment import assessment_blueprint
from routes.analytics import analytics_blueprint

app.register_blueprint(auth_blueprint, url_prefix='/api')
app.register_blueprint(problems_blueprint, url_prefix='/api')
app.register_blueprint(solution_checker_blueprint, url_prefix='/api')
app.register_blueprint(admin_blueprint, url_prefix='/api/admin')
app.register_blueprint(analytics_blueprint, url_prefix='/api')
app.register_blueprint(pages_blueprint)
app.register_blueprint(execute_blueprint)
app.register_blueprint(ai_checker_blueprint)
app.register_blueprint(generate_blueprint)
app.register_blueprint(assessment_blueprint)
app.register_blueprint(autocomplete_blueprint)


# 页面路由
@app.route("/")
@app.route("/index.html")
def index(): 
    return render_template("index.html")
    
@app.route("/login.html")
def login_page(): return render_template("login.html")

@app.route("/register.html")
def register_page(): return render_template("register.html")

@app.route("/admin")
def admin_page():
    if not current_user.is_authenticated or not current_user.is_admin:
        return redirect(url_for('index'))
    return render_template("admin.html")

# 只有在直接运行此脚本时，才启动服务器
if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "5001"))
    app.run(debug=debug, port=port, host=host)

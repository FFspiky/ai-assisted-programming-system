# routes/pages.py
from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user

# 创建蓝图
pages_blueprint = Blueprint("pages", __name__)


# 定义路由
@pages_blueprint.route("/practice.html")
def practice():
    return render_template("practice.html")


@pages_blueprint.route("/learn-analytics.html")
def analytics():
    return render_template("learn-analytics.html")


@pages_blueprint.route("/problem_selector.html")
def selector():
    return render_template("problem_selector.html")


@pages_blueprint.route("/profile.html")
def profile():
    if not current_user.is_authenticated:
        return redirect(url_for("login_page", next="/profile.html"))
    return render_template("profile.html")

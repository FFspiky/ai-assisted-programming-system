# routes/pages.py
from flask import Blueprint, render_template

# 创建蓝图
pages_blueprint = Blueprint('pages', __name__)

# 定义路由
@pages_blueprint.route('/practice.html')
def practice():
    return render_template('practice.html')

@pages_blueprint.route('/learn-analytics.html')
def analytics():
    return render_template('learn-analytics.html')

@pages_blueprint.route('/problem_selector.html')
def selector():
    return render_template('problem_selector.html')


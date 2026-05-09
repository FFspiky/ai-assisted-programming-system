# AI 辅助编程学习系统

一个基于 Flask 的编程学习与 AI 辅助系统，包含用户登录、题库、代码运行、提交判题、积分排行、学习分析、AI 聊天、代码优化和代码补全等功能。

## 环境准备

建议使用 Python 3.11 或更新版本。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

复制环境变量模板：

```bash
cp .env.example .env
```

至少需要配置：

```bash
FLASK_SECRET_KEY=replace-with-a-random-secret
SILICONFLOW_API_KEY=replace-with-your-api-key
```

如需首次启动时自动创建管理员账号，可临时配置：

```bash
ADMIN_USERNAME=admin
ADMIN_PASSWORD=replace-with-a-strong-password
ADMIN_EMAIL=admin@example.com
```

管理员创建完成后，建议删除或更换这些变量，避免后续误用。

## 启动

```bash
python app.py
```

默认访问地址：

```text
http://127.0.0.1:5001
```

## 数据库

项目使用 SQLite 作为本机演示数据库，并包含 Alembic/Flask-Migrate 迁移文件。首次本机运行会自动 `create_all()` 以便快速演示。

生产或多人协作环境中，应使用迁移命令管理数据库结构。

## 安全说明

- `.env`、`app.db`、`__pycache__/`、IDE 配置不会提交到 Git。
- AI API Key 不应写入源码，只从环境变量读取。
- 代码运行接口已经要求登录，并加入基础资源限制；如果部署到公网，仍应使用容器或独立沙箱隔离执行环境。
- 默认 `FLASK_DEBUG=0`，仅本地排查问题时临时开启。

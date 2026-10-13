# AI 辅助编程学习系统

一个基于 Flask 的编程学习与 AI 辅助系统，包含用户登录、题库、代码运行、提交判题、积分排行、学习分析、AI 聊天、代码优化和代码补全等功能。

本轮已加入可视化执行证据诊断：真实用例结果 → AI 疑似原因 → 证据及代码行定位 → 修改后重新判题。参见 [F1 演示与运行说明](docs/EVIDENCE_DEMO.md)。

点击登录后的头像可进入个人主页 `/profile.html`，编辑昵称、用户名、邮箱、简介、所在地和头像，并修改密码。主页展示真实练习时长、去重题数、通过题数、提交次数、通过率、提交日历、语言分布和最近记录；密码修改后所有旧会话失效。头像支持不超过 2 MB 的 PNG/JPG/WebP，保存为 256×256 PNG。旧库升级需执行下方迁移命令并安装新增的 Pillow 依赖。

## 环境准备

建议使用 Python 3.11 或更新版本。代码运行和判题还需要 Docker；本机 macOS 可使用已启动的 Docker Desktop。

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

DeepSeek 官方密钥也沿用上述历史变量名，同时设置：

```dotenv
SILICONFLOW_API_URL=https://api.deepseek.com/chat/completions
SILICONFLOW_MODEL_NAME=deepseek-flash
SILICONFLOW_AUTOCOMPLETE_MODEL_NAME=deepseek-flash
AI_THINKING_MODE=disabled
```

本地 `.env` 不提交。模型名称以账号可用模型为准；本轮已验证 `deepseek-flash`。

构建执行镜像一次（后续只在 `sandbox/` 修改时重建）：

```bash
docker build -t codelab-runner:local sandbox
```

执行器不挂载项目目录、不传入应用密钥，并限制网络、权限、内存、进程、CPU、总时长和输出。Docker 不可用时停止执行并提示，不退回宿主运行。

生产环境建议同时配置 Redis，用于登录失败次数和昂贵接口限流的跨进程共享：

```bash
RATE_LIMIT_REDIS_URL=redis://localhost:6379/0
```

未配置 Redis 时，系统会回退到进程内限流，适合本地演示但不适合多进程生产部署。

如需首次启动时自动创建管理员账号，可临时配置：

```bash
ADMIN_USERNAME=admin
ADMIN_PASSWORD=replace-with-a-strong-password
ADMIN_EMAIL=admin@example.com
```

管理员创建完成后，建议删除或更换这些变量，避免后续误用。

也可以使用 CLI 创建管理员：

```bash
flask --app app create-admin
```

## 启动

```bash
flask --app app db upgrade
flask --app app seed-demo
python app.py
```

默认访问地址：

```text
http://127.0.0.1:5001
```

## 数据库

项目使用 SQLite 作为本机演示数据库，并包含 Alembic/Flask-Migrate 迁移文件。首次本机运行会自动 `create_all()` 以便快速演示。

已有数据库必须先运行 `flask --app app db upgrade`；`create_all()` 不会为旧表补列。升级前备份数据库。`seed-demo` 只插入缺失的 DEMO-01～03，不覆盖已有题目。

新增题目判题模式默认 `text`，不再对所有数字输出隐式应用浮点容差；需要浮点容差的题目请在管理员编辑页明确选 `float`。隐藏用例设 `is_public: false`，其输入、答案及错误输出不进入学生界面或模型上下文。

部署生产环境前请阅读 [部署文档](docs/DEPLOYMENT.md)。

## 开发检查

本地一次性运行语法检查、单元测试和前端 JS 语法检查：

先安装 `requirements-dev.txt` 并构建上述执行镜像；测试使用临时数据库，真实 AI 演示检查需单独启用。

```bash
make check
```

也可以分别运行：

```bash
make compile
make test
make js-check
```

GitHub Actions 会在推送到 `main` 或打开 PR 时执行同样的检查。

## 安全说明

- `.env`、`app.db`、`__pycache__/`、IDE 配置不会提交到 Git。
- AI API Key 不应写入源码，只从环境变量读取。
- 代码运行接口要求登录，使用受限 Docker 容器执行。当前实现面向本机演示；公网部署需遵循部署文档，隔离执行主机与应用服务权限。
- 已登录用户的高风险 POST 接口会校验 CSRF token。
- 生产环境建议配置 `RATE_LIMIT_REDIS_URL`，避免限流状态因进程重启或多进程部署而失效。
- 默认 `FLASK_DEBUG=0`，仅本地排查问题时临时开启。

## 达菲郁编程助手

助手头像与眨眼桌宠素材：作者 [YunYueSama](https://github.com/YunYueSama/codex-deepseek-pet)，经 CSS 裁切与动画展示。许可及修改说明见 [素材署名](static/images/dafeiyu/ATTRIBUTION.md)。语气参考 [dafeiyu-persona](https://github.com/ERUIHNIYHBKBNF/dafeiyu-persona)，保留准确、尊重学生的教学风格。

聊天默认启用模型思考，通过 SSE 分别传输 `reasoning_content` 与回答；思考区支持实时更新、折叠与停止。仅展示模型接口实际返回的内容，不生成角色心声充当推理。其他短任务维持各自的思考设置。

代码自动补全默认开启（登录后使用）：输入停顿 120 毫秒触发，Tab 接受、Esc 取消，Ctrl+空格立即请求。补全显式关闭思考并使用短输出预算；结果逐段显示，近期相同上下文从当前页面的短期缓存读取。

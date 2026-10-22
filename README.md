# 智练 CodeLab · AI 辅助编程学习系统

基于 Flask 的编程学习系统，当前支持 Python 3.11 / C++17，仅连接 DeepSeek 官方 API。首次运行见 [启动说明](docs/COMPETITION_PREVIEW.md)。

提交目录的结构、离线执行镜像导入方式见 [代码交付说明](docs/CODE_DELIVERY.md)。字体和图标已随源码提供，来源与许可见 [本地前端依赖](static/vendor/README.md)。

评委快速配置：Windows 双击 `setup-windows.cmd`，随后运行 `start-windows.cmd`；macOS 在代码目录依次运行 `bash setup-macos.command` 和 `bash start-macos.command`。先安装 Python 3.11+ 并启动 Docker Desktop。随附测试 Key 的选择及共享 10 元额度说明见 [评审使用指南](docs/SUBMISSION_START.md)。

## 当前功能

- 题库练习：分类筛选、代码运行、提交判题、积分排行与学习分析。
- 学习共创：验证 AI 代码、解释修改、独立完成关联练习，记录实际执行依据与复盘。见 [学习共创说明](docs/CO_CREATE_LEARNING.md)。
- 编程辅助：聊天、分级帮助、代码优化、自动补全，以及建议采纳、撤销和正式复测。见 [AI 共创说明](docs/CO_CREATE.md)。
- 实战任务室：9 个项目，包含需求确认、Python/C++ 开发、Docker 验收、变更、交付与档案导出。见 [任务室说明](docs/TASK_ROOM.md)。
- 学习问卷与项目推荐：依据用户自述推荐任务，并显示实际交付进度。见 [问卷说明](docs/LEARNING_PLAN.md)。
- 个人资料、头像和个人 AI 密钥配置；达菲郁聊天与桌宠交互。

用户记录按账号保存。模型建议需通过真实执行验证，有限用例通过不代表已掌握知识或证明教学收益。

## 环境准备

建议使用 Python 3.11 或更新版本。代码运行和判题还需要 Docker；Windows/macOS 可使用 Docker Desktop，Linux 可使用 Docker Engine。

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
DEEPSEEK_API_KEY=replace-with-your-api-key
```

仅支持 DeepSeek 官方 API，接口固定为 `https://api.deepseek.com/chat/completions`。模型配置：

```dotenv
DEEPSEEK_MODEL_NAME=deepseek-flash
DEEPSEEK_AUTOCOMPLETE_MODEL_NAME=deepseek-flash
AI_THINKING_MODE=disabled
```

本地 `.env` 不提交。模型名称以账号可用模型为准；默认使用 `deepseek-flash`。

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
flask --app app seed-library
python app.py
```

默认访问地址：

```text
http://127.0.0.1:5001
```

内置分类题库新增60道自编教学题，含360个用例，支持分类、难度、练习状态筛选及搜索分页。`seed-library`可重复执行，不覆盖已有题号；需先完成数据库迁移。维护和验证方式见 [题库说明](docs/PROBLEM_LIBRARY.md)。

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

GitHub Actions 会在推送到 `main` 或打开、更新面向 `main` 的 PR 时运行完整检查：Ruff、Black、Python 编译与测试、Docker 镜像构建、干净库迁移、JavaScript 语法、Node 控制器回归、Playwright 浏览器流程和 Python/Node 依赖审计。`make check` 仅覆盖编译、Python 测试和 JS 语法，不等于完整 CI。

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

聊天窗口支持标题栏拖动、四边四角缩放、双击标题栏最大化/还原，并记住窗口位置和大小。桌宠拖动时切换到被提起姿势，松手后缓落并站稳；聊天时显示思考/回答状态。右键桌宠（触屏长按）可选择挥手、跳跃、跳舞、吃小鱼干、休息和醒来；空闲时会偶尔活动，长时间无操作后休息。系统开启“减少动态效果”时保留状态姿势并减少动画。

### 个人 API Key 配置

登录后从「个人主页 → 个人资料 → AI 服务配置」选择自有 Key 或项目测试 Key。自有 Key 须属于页面显示的服务商，模型与接口沿用服务端配置。项目测试 Key 使用服务端 `DEEPSEEK_API_KEY`，未设置时不可选择；用户必须显式保存配置后才能调用 AI。保存不代表已验证服务商额度或密钥有效性。

升级安装依赖并执行 `flask --app app db upgrade`；本机自动建表模式也会创建新增配置表。用户 Key 使用 Fernet 加密，默认加密密钥自动生成在 `instance/ai-credentials.key`（已被 Git 忽略）。部署时可通过 `AI_CREDENTIAL_ENCRYPTION_KEY` 指定固定的 Fernet 密钥；多实例必须共享同一密钥。请与数据库一起备份并持久保留加密密钥，丢失或更换后用户需重新填写 Key。测试 Key 不会返回浏览器，切换到测试 Key 或清除配置会移除此前保存的个人 Key。

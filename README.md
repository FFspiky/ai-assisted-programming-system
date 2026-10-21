# AI 辅助编程学习系统

> **2026-10-19 参赛整合版**：整合学习共创与交互改进，当前仅支持 Python 3.11 / C++17。见 [参赛演示与启动说明](docs/COMPETITION_PREVIEW.md)。以下日期条目是原版本历史记录，其中 Java 及三语言验证不代表当前功能。


一个基于 Flask 的编程学习与 AI 辅助系统，包含用户登录、题库、代码运行、提交判题、积分排行、学习分析、AI 聊天、代码优化和代码补全等功能。

2026-10-18 **达菲郁学习共创**：围绕“验证 AI 代码 → 解释修改 → 独立再做一次”组织共创页。学生解释绑定具体代码与运行依据，代码改变时保留旧解释并标记；60 道内置题配有人工编排的关联练习，支持 Python / C++ / Java，沿用真实判题。独立练习暂时收起本页 AI 帮助，保留达菲郁、编辑器与草稿，不更改账号的帮助偏好；复盘卡汇总真实运行、采纳/撤销、正式提交及本人自述帮助情况，可导出 JSON / Markdown。一次通过不推断为已掌握。本次使用现有会话状态与事件表，无新增数据库迁移。详见 [学习共创说明](docs/CO_CREATE_LEARNING.md)。

2026-10-16 **题目共创与三语言支持**：`/co-create.html` 已围绕刷题题库开展用例共创与代码质检，承接题意、公开样例、语言和草稿；支持候选对比、题库验证、差异预览后采纳/撤销及正式复测。Python 3.11、C++17、Java 17 共用 Docker 隔离执行，实战任务室、AI 帮助、草稿和导出同步支持三语言。原场景记录保留查看，达菲郁互动与海洋蓝风格保留。已有数据库先备份并升级至 `l30a20261016`，Java 需重新构建运行镜像。详见 [AI 共创说明](docs/CO_CREATE.md) 和 [语言支持说明](docs/LANGUAGES.md)。

2026-10-14 新增独立的 **AI 实战任务室**，入口 `/task-room.html`，模块代码集中于 `modules/task_room/`。包含 9 个原创项目（6 个入门或基础小练习、3 个综合任务）、AI 客户沟通、规则确认、Python / C++ / Java 开发、Docker 实际验收、版本变更、交付、复盘、保存恢复与 ZIP 导出。聊天和候选代码不会自行更改已确认需求，验收由明确规则计算。使用及维护见 [任务室说明](docs/TASK_ROOM.md)。

学习分析中的编程学习问卷已开放：9 个简短问题，包含 Python / C++ 练习语言偏好，保存后推荐 6 个可进入的项目，已领取和已交付的状态会按语言从任务室同步。旧版问卷继续兼容。推荐不调用 AI；学习分析的 AI 功能改为点击后生成。参见 [问卷与项目推荐](docs/LEARNING_PLAN.md)。

「算法造物工坊」已撤回，学习分析入口恢复。工坊代码归档于 `archive/workshop-20261014/`，已有运行及 AI 候选记录保留，相关接口已停用。首页、刷题与题库流程保留。

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

登录后从「个人主页 → 个人资料 → AI 服务配置」选择自有 Key 或项目测试 Key。自有 Key 须属于页面显示的服务商，模型与接口沿用服务端配置。项目测试 Key 使用服务端 `SILICONFLOW_API_KEY`，未设置时不可选择；用户必须显式保存配置后才能调用 AI。保存不代表已验证服务商额度或密钥有效性。

升级安装依赖并执行 `flask --app app db upgrade`；本机自动建表模式也会创建新增配置表。用户 Key 使用 Fernet 加密，默认加密密钥自动生成在 `instance/ai-credentials.key`（已被 Git 忽略）。部署时可通过 `AI_CREDENTIAL_ENCRYPTION_KEY` 指定固定的 Fernet 密钥；多实例必须共享同一密钥。请与数据库一起备份并持久保留加密密钥，丢失或更换后用户需重新填写 Key。测试 Key 不会返回浏览器，切换到测试 Key 或清除配置会移除此前保存的个人 Key。

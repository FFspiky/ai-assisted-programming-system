# 本地参赛整合版 · 2026-10-19

基于远端主分支 bd463fe，工作分支 codex/competition-python-cpp。整合版通过同名远端分支发布。原本地改动保存在 Git stash（backup local interaction improvements before competition integration），原 app.db 未迁移、未覆盖。

## 当前内容

保留远端题库、学习共创、关联练习、问卷推荐和任务室；合并本地输入法 Enter 保护、流式输出节流与滚动保持、思考内容保留展开、聊天窗口操作、桌宠操作、表单错误提示、编辑器滚动同步和轻量图片。

语言统一为 Python 3.11 / C++17：移除 Java 选项、模板、运行器分支、任务室包装与 JDK 依赖。任务室目录、创建和执行遵守启用语言配置。历史迁移保留，旧 Java 记录不转换为另一种语言。

修复 Redis 限流检查与预约之间的并发窗口；内存限流加锁。题库筛选和分页下推数据库，任务列表不再加载每个项目的全部运行与聊天正文。CI 增加共创、题库、证据工作台、聊天和桌宠浏览器回归。

预览库包含 183 题：本地 P 系列 120 题、远端 CL 系列 60 题、DEMO 3 题。原题仅复制题面和测试用例，不复制用户或提交记录；P 系列保留未分类状态及原用例，尚未按新题库标准逐题复核。数量不代表题目质量相同。

## 可复现启动

安装 requirements-dev.txt 和 npm 依赖，启动 Docker，然后在项目根目录执行：

```sh
docker build -t codelab-runner:local sandbox
python scripts/prepare_competition_preview.py --database tmp/competition.db --legacy-db app.db
PYTHON_DOTENV_DISABLED=1 DATABASE_URL="sqlite:///$PWD/tmp/competition.db" AUTO_CREATE_DATABASE=0 FLASK_SECRET_KEY=local-preview-secret CODE_SANDBOX_IMAGE=codelab-runner:local flask --app app run --host 127.0.0.1 --port 5087
```

准备脚本使用迁移创建独立数据库；重复导入跳过已有题目。若没有原 app.db，可省略 --legacy-db，获得 63 道内置题。不要将已有但未标记迁移版本的数据库作为目标。

当前临时在线预览使用独立 competition.db 和 codelab-competition-runner:20261019 镜像，由本机服务通过临时隧道提供；本机服务或隧道停止后链接失效。代码直接来自当前本地工作区。

## 建议演示顺序（约 4 分钟）

1. 题库选择 CL-BASICS-01「秒数换算」，介绍 Python/C++ 两种语言和分类筛选。
2. 进入代码质检，把分钟写成 t // 60，用输入 3661 运行，展示实际输出与预期的差异。修改为 t // 60 % 60，再执行并查看结果。
3. 在「解释修改」写下修改理由和边界情况，保存与代码版本绑定的解释。
4. 进入「独立再做一次」，完成数位之和；展示真实提交结果和复盘卡。说明独立练习会收起本页 AI 帮助，不代表已经证明学习效果。
5. 用任务室补充展示明确规则、C++ 函数合同、实际验收与导出。主线仍以验证、解释、独立完成为中心。

## 验证证据与边界

- Python 全量首轮 210 项通过；新增限流 2 项及任务室语言限制回归通过。
- 前端控制器 45 项通过。
- 浏览器核心流程 16 项通过；聊天、桌宠、帮助控制 11 项通过（旧测试的自动折叠预期已改为本地保留展开行为，并单独复测通过）。覆盖桌面和窄屏。
- Python/C++ 学习链路真实 Docker 执行 14 次，两条正式目标提交 Accepted；任务室两种语言均通过成绩统计验收和 Unicode/JSON 往返检查。
- Redis 实例上 16 个并发请求竞争 1 个额度，仅 1 个获准，过期后额度恢复。
- AI 请求在回归中使用明确的测试替身；当前公开预览未配置模型密钥。真实 AI 生成质量、真实学生观察及教学收益仍需另行验证。

运行证据保存在 tmp/learning-journey-check/docker-smoke.json 与 tmp/task-room-multilang/docker-verification.json。测试中有意触发的失败日志不等于测试失败。

本版适合功能演示和参赛素材录制。正式提交仍需团队补齐作品说明、演示视频、素材来源与真实用户反馈；暂不宣称已达到生产级并发服务。执行器每个应用进程同时最多两个任务，繁忙时返回重试提示。

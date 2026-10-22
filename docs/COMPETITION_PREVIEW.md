# 当前版本启动与验证

支持 Python 3.11 / C++17，包含题库、学习共创、关联练习、问卷推荐与实战任务室。AI 使用 DeepSeek 官方 API。

## 环境与初始化

需要 Python 3.11、Docker，以及运行前端测试所需的 Node.js/npm。所有命令在项目根目录执行。先创建并激活 Python 虚拟环境，安装依赖：

```sh
python -m pip install -r requirements-dev.txt
npm ci
docker build -t codelab-runner:local sandbox
python scripts/prepare_competition_preview.py --database tmp/competition.db
```

初始化脚本使用迁移创建独立数据库，导入 60 道分类题和 3 道演示题，不需要外部数据库。不要将已有但未标记迁移版本的数据库作为初始化目标。

## 启动服务

复制 `.env.example` 为 `.env`，设置随机的 `FLASK_SECRET_KEY` 和 DeepSeek 官方密钥。下列启动命令保留 `.env` 中的 AI 配置；AI 功能还需要登录后在个人资料页明确选择自有 Key 或项目测试 Key。未配置 AI 时可以手动编程和判题。

Windows PowerShell：

```powershell
$env:DATABASE_URL = 'sqlite:///' + (Resolve-Path 'tmp/competition.db').Path.Replace('\', '/')
$env:AUTO_CREATE_DATABASE = '0'
python -m flask --app app run --host 127.0.0.1 --port 5001
```

macOS/Linux：

```sh
DATABASE_URL="sqlite:///$PWD/tmp/competition.db" AUTO_CREATE_DATABASE=0 python -m flask --app app run --host 127.0.0.1 --port 5001
```

浏览器打开 `http://127.0.0.1:5001`，注册并登录。已有数据库升级前先备份，使用 `python -m flask --app app db upgrade` 升级，勿以测试库覆盖用户数据。

## 核心流程

1. 在题库选择 CL-BASICS-01「秒数换算」，选择 Python 或 C++。
2. 进入代码质检，运行候选代码并比较实际输出与预期。
3. 保存与代码版本绑定的修改理由和边界情况。
4. 在「独立再做一次」完成关联题，查看真实提交结果与复盘。
5. 在任务室体验规则确认、实际验收、交付及导出。

## 可重复验证

```sh
python -m unittest discover -s tests
node --test tests/*.test.cjs
python scripts/verify_problem_co_create.py
python scripts/verify_co_create_learning.py
python -m modules.task_room.verify_languages --languages python cpp
```

Python 测试和验证脚本使用隔离数据库，涉及执行的检查需要 Docker。模型响应使用测试替身，不调用真实付费 AI，不能据此推断模型质量或教学收益。以本次执行结果判断通过状态。

浏览器回归需要先启动上述测试服务：

```sh
npx playwright install chromium
```

PowerShell 执行 `$env:SMOKE_BASE_URL='http://127.0.0.1:5001'` 后运行 `npm run smoke`；macOS/Linux 执行 `SMOKE_BASE_URL=http://127.0.0.1:5001 npm run smoke`。浏览器测试会创建测试账号，应使用独立预览数据库。

执行器每个应用进程最多同时运行两个任务，繁忙时提示重试。公网部署条件见 [部署说明](DEPLOYMENT.md)。

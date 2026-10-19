# AI 实战任务室

> 当前参赛分支仅支持 Python / C++17；历史 Java 和三语言测试记录仅供追溯。当前启动与验证结果见 [参赛说明](COMPETITION_PREVIEW.md)。


这是智练 CodeLab 的独立功能模块，入口为 `/task-room.html`，也可通过 `/task-room` 进入。它有自己的页面、前端资源、API、业务服务、数据库表和测试；复用现有 Flask 应用的登录、CSRF、数据库连接、Docker 隔离执行器和 AI 接口。当前 9 项任务全部支持 Python、C++17、Java 17 的 `solve(data)` 函数合同，不需要安装或制作手机 App，也不是另起一套独立账号服务器。

模块围绕“接任务 → 澄清需求 → 确认合同 → 开发与验收 → 交付 → 应对变更 → 复盘”组织。原项目顶部导航、首页主按钮和核心功能区均可进入「实战任务室」；刷题、学习分析、个人主页也提供相同导航入口。任务室沿用原项目的深蓝海洋主题和品牌资源，页面与业务代码独立维护。

## 从哪里开始

1. 启动项目，在浏览器打开 `http://127.0.0.1:5002/task-room.html`。端口以实际启动信息为准。
2. 可以先浏览任务；接下任务、保存和运行需要登录现有账号。
3. 选择任务后阅读客户资料。客户的初始留言属于预先编写的任务资料；发起 AI 客户沟通后才会请求配置的真实模型。
4. 逐项选择规则。推荐选项只是初始参考，客户聊天也不会代替你的确认。
5. 确认后生成 V1 需求合同；小练习有 6 个、综合任务有 10 个公开验收案例。合同保存当时的规则及期望输出，后续不会因聊天内容而自动改变。
6. 编写或请开发教练提供候选代码。候选代码需要明确采用；采用不是验收通过。代码未继续改动且需求版本一致时，可以撤销采用。
7. 保存草稿，先运行自定义输入，再执行全部验收。逐项查看输入、期望值、实际值和错误。
8. 当前保存的代码通过当前合同全部案例后，才能完成交付。自定义输入通过不能代替完整验收。
9. 在客户变更中选择尚未处理、且确实改变当前规则的请求。确认后生成新的合同版本，旧合同、旧代码快照和旧运行仍保留；新版本需要重新验收与交付。
10. 查看事件时间线及实际运行统计，按需请求 AI 复盘，最后导出项目档案。已有项目可以继续编辑，也可以归档和恢复。

## 9 项任务，从简单项目开始

学习分析页的 9 项问卷（含首选开发语言）会结合自述基础、目标、兴趣和单次练习时间推荐 6 个项目。可以直接打开指定项目介绍，也能继续已有项目；进度来自真实项目记录，详见 [问卷与推荐说明](LEARNING_PLAN.md)。任务大厅提供入门、基础和综合任务筛选。

新增的小练习如下，每个只需实现一个函数，含 2 组规则、6 个公开案例及 2 项可选变更：

| 场景 ID | 小项目 | 练习重点 |
| --- | --- | --- |
| `score_summary` | 成绩统计 | 遍历、总分、最高分及达标人数 |
| `text_counter` | 文本词频 | 分词、大小写处理、字典计数 |
| `shopping_total` | 购物清单 | 整数金额、数量相乘、门槛条件 |
| `todo_sort` | 待办排序 | 筛选、优先级、稳定排序 |
| `study_checkin` | 学习打卡 | 按天汇总、目标判断、去重 |
| `expense_summary` | 支出汇总 | 分类统计、整数分、输出顺序 |

原有三项综合任务保留：

| 场景 ID | 业务场景 | 需要协商的规则 | 可验证的变更 |
| --- | --- | --- | --- |
| `signup_roster` | 社团迎新报名名单清洗 | 按手机号或姓名去重；保留首次或最新；无效行跳过或报告 | 更新分组采用最新提交；改为按姓名合并；补录无效行报告 |
| `event_waitlist` | 校园工作坊录取与候补 | 报名先后或优先级；取消忽略或释放；重复首次或最新 | 开放取消与递补；志愿者优先；重新提交更新优先级 |
| `stock_orders` | 校园市集物资分配 | 库存不足整单拒绝或部分发放；按提交顺序或小单优先；同单首次或最新 | 开放部分领取；小单优先；申请单允许更正 |

综合场景各有 3 组二选一规则、10 个公开案例和 3 个预设变更请求。已经包含在当前合同里的变更不会重复创建合同。9 个项目合计 66 个公开案例、48 种规则组合；任务素材为项目内原创教学场景。

## 代码与验收约定

只需定义返回 JSON 兼容值的函数：

```python
def solve(data):
    # 根据页面中已确认的输入、输出与规则实现。
    return {}
```

不需要读取标准输入，不需要打印最终答案。Python 的每个案例在新的函数命名空间中执行；C++ / Java 在同一次程序中依次调用 solve，因此不要让可变全局或 static 状态影响不同输入。三种语言的标准调试输出与返回值分开处理。完整验收会在一次 Docker 执行中回放该合同的全部案例，宿主根据合同的确定性规则比较返回结果。

- 数组顺序属于合同；对象字段顺序不影响比较。
- 字段必须完整，额外字段也会导致比较失败。
- 布尔值与整数不同，`true` 不能代替 `1`。
- 字符串清理、重复处理顺序、默认字段和错误原因详见各任务的输入输出约定。
- 自定义输入先经过同一规则模型校验；不符合任务格式时会返回输入错误，而不是调用 AI 猜测答案。
- 全部验收案例公开。通过表示满足这些具体案例，不表示对所有输入都已证明正确。
- AI 不生成评分，也不能改变确定性判分规则。验收所记录的运行后端、状态与耗时来自实际执行器。

开发教练可以提供完整候选代码，但只有你选择采用后才会写入草稿。候选保存其生成时的合同与代码指纹：切换合同或改过代码后，过期的采用、撤销会被拒绝，避免覆盖新工作。

## 数据保存与导出

任务室单独使用以下表，不混入刷题提交记录：

- `task_room_project`：项目、草稿、项目版本、草稿版本、交付凭证、归档状态与事件时间线。
- `task_room_contract`：不可变的需求版本与规则、公开验收案例快照。
- `task_room_message`：客户、教练和复盘消息，以及候选代码、操作状态和模型返回的模型标识。
- `task_room_run`：每次实际运行的代码快照、代码指纹、合同版本、案例结果与执行环境记录。

项目归属登录用户，其他用户无法读取、修改或下载。归档只隐藏在活动项目列表中，恢复后可继续工作，不删除历史数据。

导出的 ZIP 含：

- Python：`solution.py` 与 `run.py`；C++：`solution.cpp` 与 `main.cpp`；Java：`Solution.java` 与 `Main.java`。函数代码和本地运行包装分别导出。
- `inputs.json`：当前合同的 JSON 输入数组，供本地回放。
- `project.json`：项目、历次合同、对话、事件、代码快照和实际运行记录。
- `acceptance.json`：当前需求合同与全部公开案例；尚未确认需求时不生成该文件。
- `README.md`：需求与变更、运行概况、沟通复盘及使用说明。

导出的是项目档案。运行代码仍应使用项目的 Docker 隔离环境，导出不会自动执行代码。

## 模块结构与集成

```text
modules/task_room/
  __init__.py                 # register_task_room(app)
  models.py                   # 独立任务室表
  catalog.py                  # 原创任务、枚举规则、合同和确定性 oracle
  ai.py                       # 客户、开发教练、复盘的 AI 适配器
  languages.py                # 三语言函数合同、可信 JSON helper、包装与导出
  verify_languages.py         # 不调用 AI、不接触数据库的真实三语言 Docker 检查
  service.py                  # 状态、版本、保存、运行、交付、变更和导出
  routes.py                   # 页面与 /api/task-room/*
  templates/task_room.html    # 独立页面
  static/                     # 独立样式与交互
migrations/versions/i07a20261014_task_room.py
scripts/verify_task_room.py
tests/test_task_room.py
tests/test_task_room_catalog.py
tests/smoke/task-room.spec.mjs
```

宿主 `app.py` 的接入点只有模块模型导入、注册函数导入与蓝图注册。模型须在 `db.create_all()` 或迁移扫描前导入：

```python
from modules.task_room import models as task_room_models  # noqa: F401
from modules.task_room import register_task_room

# 复用现有 app、db、登录和 CSRF 初始化。
register_task_room(app)
```

迁移版本 `i07a20261014` 接在 `h96a20261014` 之后。升级现有数据库前先保留 SQLite 备份，再执行项目的迁移命令：

```powershell
.\.venv\Scripts\python.exe -m flask --app app db upgrade
```

不要用测试数据库覆盖用户数据库，也不要为接入任务室删除旧表。新增模块不需要把历史工坊数据恢复成可用功能。

## 本地配置与启动

沿用项目已有 `.env`，无需新增供应商变量。以下仅说明配置项，勿把真实密钥写进文档、前端或版本库：

| 配置项 | 用途 |
| --- | --- |
| `SILICONFLOW_API_KEY` | 后端读取的模型密钥；DeepSeek 兼容配置也沿用此变量名 |
| `SILICONFLOW_API_URL` | 已配置的聊天接口地址 |
| `SILICONFLOW_MODEL_NAME` | 请求使用的模型名称 |
| `AI_THINKING_MODE` | 现有供应商适配配置；任务室短回复使用关闭思考的请求 |
| `DATABASE_URL` | 复用项目数据库 |
| `FLASK_SECRET_KEY` | 稳定登录会话与 CSRF 的服务端密钥 |
| `CODE_SANDBOX_IMAGE` | 已构建的执行镜像，默认 `codelab-runner:local` |
| `CODE_RUN_*` | 复用现有超时、内存、输出等隔离执行限制 |

在项目目录打开 PowerShell，确认 Docker Desktop 引擎正在运行，按实际安装位置把 Docker CLI 加入当前窗口路径。当前机器示例：

```powershell
$env:PATH = "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin;$env:PATH"
docker version
docker image inspect codelab-runner:local
$env:FLASK_PORT = "5002"
$env:CORS_ORIGINS = "http://127.0.0.1:5002,http://localhost:5002"
.\.venv\Scripts\python.exe app.py
```

浏览器地址与启动日志中的端口保持一致。服务器窗口需要保持运行。

## 常见问题与恢复

| 情况 | 处理方式 |
| --- | --- |
| 任务能打开，但运行提示环境不可用 | 查看 Docker Desktop 是否显示引擎运行；在启动 Flask 的同一窗口确认 `docker version` 和镜像存在，再重启 Flask |
| Docker CLI 找不到或本地镜像不存在 | 修复当前窗口 PATH，按项目沙箱构建说明构建 `codelab-runner:local`；执行器不会回退到宿主运行 |
| 运行超时、输出超限、内存异常 | 根据真实执行错误缩小输出、修复循环或降低资源使用；不是 AI 判分结果 |
| AI 不可用或回复格式异常 | 规则确认、手写代码、保存、实际验收和导出仍可使用；检查后端供应商配置，稍后重新发起，失败不会伪造客户回复或通过记录 |
| 其他窗口更新导致版本冲突 | 先复制保留本地代码，再刷新并检查最新需求或草稿；不要直接覆盖另一窗口的更新 |
| 改过代码后不能交付 | 保存当前代码，对当前合同重新完整验收；交付校验同时绑定代码指纹和合同版本 |
| 采用或撤销候选提示已过期 | 生成建议后代码或合同已改变；保留当前草稿，重新请求建议 |
| 重启后旧任务仍显示运行中 | 超过 2 分钟的运行在下次读取时标为中断；超过 5 分钟的 AI 请求标为失败，可重新发起，不会伪造成功结果 |

## API 概览

前缀 `/api/task-room`。除目录外需要登录；有状态变更的请求携带现有 `X-CSRF-Token`，正文使用 JSON。标准返回继续采用项目的 `success/data/error` 格式。

| 方法与路径 | 用途与主要参数 |
| --- | --- |
| `GET /catalog` | 公开任务资料、规则选项、起始代码与 AI 配置可用状态 |
| `GET /projects?archived=0` | 当前用户的活动或归档项目 |
| `POST /projects` | 接任务：`scenario_id,language`；language 为 python/cpp/java，省略兼容旧客户端默认为 python |
| `GET /projects/{id}` | 项目详情、合同、草稿、消息、运行与事件 |
| `PATCH /projects/{id}` | 保存：`code,draft_revision`；归档或恢复：`archived,revision` |
| `POST /projects/{id}/freeze` | 首次确认完整规则：`rules,revision` |
| `POST /projects/{id}/messages` | AI 沟通：`intent,message,code,operation_id`；intent 为 `customer/coach/review` |
| `POST /projects/{id}/messages/{message_id}/apply` | 采用候选：`draft_revision` |
| `POST /projects/{id}/messages/{message_id}/undo` | 撤销采用：`draft_revision` |
| `POST /projects/{id}/run` | 运行：`code,kind,contract_id,input`；kind 为 `acceptance/custom`，input 仅自定义运行需要 |
| `POST /projects/{id}/deliver` | 交付：`code,contract_id,revision` |
| `POST /projects/{id}/changes` | 接受受控变更：`change_id,revision` |
| `GET /projects/{id}/export` | 下载 ZIP 项目档案 |

`revision` 管理需求与工作流，`draft_revision` 管理代码草稿。使用数据库条件更新检测并发更改；过期请求返回 409。AI `operation_id` 用于识别同一请求，避免客户端重试重复提交同一轮调用。运行记录保存其实际合同和代码，不会随着页面草稿变化而改写。

边界限制：每用户最多 100 个项目（含归档），每项目最多 100 次运行、100 轮 AI 沟通；代码最多 20000 字、消息最多 2000 字、自定义输入最多 8000 字，任务室请求体最多 160 KiB。每个任务输入最多 100 条记录；库存最多 30 种物资。创建、沟通和运行另受请求频率限制。

## 验证与费用

常规单元测试使用模拟 AI 回复，不会调用收费接口。目录测试只导入任务目录，不启动 Flask 或数据库：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_task_room_catalog tests.test_task_room
```

真实 Docker 回放脚本只执行项目自带参考实现，不连接用户数据库、不导入 `app.py`、不调用 AI。默认覆盖推荐规则及各有效客户变更；`--all-rules` 覆盖 48 组规则、384 个案例：

```powershell
.\.venv\Scripts\python.exe scripts/verify_task_room.py
.\.venv\Scripts\python.exe scripts/verify_task_room.py --all-rules
```

报告默认保存到 `tmp/task-room-check/docker-results.json`，可通过 `--output` 指定位置。只有真实 Docker 成功执行、返回数量与全部结果正确时才算通过，任一失败退出码为 1。

浏览器用例位于 `tests/smoke/task-room.spec.mjs`。测试应使用用户数据库的临时副本或隔离测试数据库与独立服务端口，测试账号只能写入测试副本。按现有浏览器测试配置运行，先为测试服务设置对应的 `SMOKE_BASE_URL`：

```powershell
$env:SMOKE_BASE_URL = "http://127.0.0.1:5007"
.\node_modules\.bin\playwright.cmd test tests/smoke/task-room.spec.mjs
```

浏览器自动测试中的 AI 也应模拟。真实供应商连通性验证需要用户明确允许付费调用后，在页面主动发送一轮消息；应记录实际响应或错误，不以模拟回复充当真实接入证明。模型名称只有供应商确实返回时才作为响应记录，不填造模型标识。


## 三语言项目与旧数据兼容（2026-10-16）

创建项目时选择语言。语言绑定项目，不能通过保存草稿改变。工作区切换语言会先保存原草稿，再恢复同任务、目标语言的活动项目；不存在时创建独立项目。原项目的合同、草稿、消息与证据全部保留。归档项目仍可从“已归档”列表查看及恢复。旧项目和旧运行在迁移时标记为 Python。

页面题目与业务规则相同，语言只改变代码入口和工具。C++ 与 Java 的 JSON 解析、序列化及输入输出包装已由本地可信工具提供，学生无需重写解析器，也不需要第三方 JSON 库。

```cpp
Json solve(const Json& data) {
    Json result = Json::object();
    result["count"] = data["scores"].size();
    // 按选定合同继续实现 total、highest、passed。
    return result;
}
```

C++ JSON API：`data["key"]`、`data[index]`、`as_int()`、`as_number()`、`as_string()`、`as_bool()`、`array_items()`、`object_items()`、`contains(key)`、`size()`；结果使用 `Json::object()`、`Json::array()`、赋值及 `push_back()`。源码仅含函数和辅助代码，不自行定义 `main()`。

```java
class Solution {
    static Json solve(Json data) {
        return Json.object().put("count", data.get("scores").size());
    }
}
```

Java JSON API：`get(key/index)`、`asInt()`（返回 long）、`asNumber()`、`asString()`、`asBool()`、`arrayItems()`、`objectItems()`、`contains(key)`、`size()`；结果使用 `Json.object()`、`Json.array()`、`put()`、`add()`。使用非 public `Solution` 类，不声明 `main`、`package`、`import`；标准库类型使用完整包名。页面会展示当前语言约定。

字符串业务语义仍按合同执行，例如词频任务按 Unicode 字符计数，C++ 的 UTF-8 字符串字节数、Java 的 UTF-16 长度并不自动等于合同的字符数；编写业务代码时要按码点处理。JSON helper 保证传输 Unicode，不代替文本业务逻辑。

AI 提示携带项目语言和准确函数合同。Python 候选进行 AST 结构检查；C++ / Java 候选进行函数签名与入口检查，真实语法、运行和验收以 Docker 结果为准。候选仅是待采纳建议，服务端不会因为 AI 声称通过而记录成功。运行及交付绑定项目语言，旧 Python 验收不能用于另一语言项目。

ZIP 的 README 提供对应启动命令。示例：Python `python run.py < inputs.json`；C++ `g++ -std=c++17 main.cpp -o solution` 后 `solution.exe < inputs.json`（Windows CMD）；Java `javac -encoding UTF-8 Main.java Solution.java` 后 `java Main < inputs.json`。导出不会执行任何代码。

问卷版本 2 将 Python 专属熟悉度改为语言中立的编码熟悉度，并增加首选语言。旧版本 1 的 8 项答案读取时映射到 Python，保留数据库里的原答案和版本；只有明确重新提交才写入新版本。推荐入口携带首选语言，项目完成状态只引用该语言的项目，汇总统计仍反映账号下实际完成的全部语言项目。

真实三语言检查（无 Flask、无用户数据库、无 AI 调用）：

```powershell
.\.venv\Scripts\python.exe -m modules.task_room.verify_languages
```

默认报告保存到 `tmp/task-room-multilang/docker-verification.json`，包括每种语言的成绩统计完整验收，以及嵌套 JSON、整数/布尔/浮点类型、Unicode、调试输出分离回放。失败会退出非零状态。Java 必须使用已包含 JDK 17 及当前执行协议的新沙箱镜像。

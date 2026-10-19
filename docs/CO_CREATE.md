# 达菲郁学习共创：验证、解释与独立尝试

> 当前参赛分支仅支持 Python / C++17；历史 Java 和三语言测试记录仅供追溯。当前启动与验证结果见 [参赛说明](COMPETITION_PREVIEW.md)。


2026-10-18：页面已按“验证 AI 代码 → 解释修改 → 独立再做一次”组织。下述用例推演、代码质检与采纳复测保留在验证阶段；新增解释、关联练习与复盘卡的完整契约见 [学习共创说明](CO_CREATE_LEARNING.md)。阶段可自由返回，学生解释与输出预测不作为强制门槛；现有会话无需重建。

现行入口为 `/co-create.html`，复用原账号、题库、AI 客户端、Docker 执行器及主站海洋风格与达菲郁宠物。新记录选择题库中的具体题目，不再选择去重、筛选、排序三个固定场景。历史场景记录保留读取与导出，旧后端接口仍兼容历史客户端。

## 使用方式

1. 从题库选择题目，或在刷题页点击进入共创。后者带入当前题目、语言、代码草稿、标准输入及可选的本人提交编号。
2. 「例子推演」自动显示题面和公开样例，可另加自定义输入和你的期望输出。公开样例不能改写或删除；学生填写的期望始终标为个人假设。
3. 请求真实 AI 候选。没有草稿时生成两份完整程序；有草稿时保留草稿为一个来源明确的候选，并请求一份 AI 候选。每份候选在 Docker 中运行当前例子，运行失败的代码也保留供质检，不伪装成成功。
4. 对两个候选输入同一份标准输入，观察实际输出是否一致。可以选择候选带回刷题；选择本身不代表程序正确。
5. 「代码质检」使用带入的代码或真实 AI 生成的代码，可直接运行，也可选填判断与预测。填写预测时需同时保存对应输入。AI 的目标是满足题意，不会被要求故意写错。
6. 编辑代码后旧预测失效，需重新保存对应输入的预测。旧运行证据带代码版本与指纹，供修订前后比较。
7. 「题库验证」在 Docker 中对当前候选或质检代码运行题库用例，隐藏用例只显示状态与汇总。
8. 共创验证不创建正式 Submission、不加积分、不伪造学习结果。正式采纳、撤回、提交及复测与刷题原流程衔接。

完整程序采用标准输入/标准输出协议，不再要求 `def solve(data)` 或 JSON 输入输出。Python、C++17、Java 17 使用统一语言约定；Java 入口为 `public class Main`，不声明 package。实际可用语言由主站配置和 Docker 镜像共同决定。

## 判定来源

| 来源 | 含义 | 页面判定 |
| --- | --- | --- |
| `official` | 当前题目的公开样例或题库用例 | 对照题库答案 |
| `reference` | 版本匹配的内置参考程序在独立 Docker 执行后的输出 | 参考程序对照，输入范围由学生确认 |
| `user` | 学生自己填写的期望输出 | 符合/不符合你的期望 |
| `unknown` | 没有可确认的标准答案 | 运行成功或失败；正确性待验证 |

公开样例输入优先使用官方答案，不能通过提交一个错误的 `expected` 覆盖。未知答案的结果 `passed` 为 `null`，即使两个候选输出完全相同，也不会显示“通过”或推断代码正确。个人期望匹配不会计为官方用例通过。

当前内置题库有 60 份 Python 参考解。参考解只在服务端使用，按 canonical 题目 ID、标题、题面、判题模式和全部用例指纹匹配。管理员修改题面或用例后，原参考解自动停用。旧会话也不能继续验证更新后的题目，应新建记录，旧证据继续保留。

自定义输入使用参考程序时需显式提交 `input_validated: true`，表示学生已确认符合题目数据范围；系统没有通用的题意范围解析器。参考程序执行成功不能单独证明输入合法。参考执行失败时只显示未验证，私有源码、标准错误与隐藏答案均不返回页面。

通过一个输入或所有现有用例，只说明这些具体检查通过，不能证明算法对所有合法输入正确。输出不唯一的题目需要合适的题库 checker；当前沿用主站 text、integer、float 判题规则。

## 保存和证据边界

会话新增 `problem_id` 与 `language` 字段，状态 `kind: "problem"` 保存题面快照、公开例子、带入草稿、候选、代码修订、运行和事件。旧 `scenario_id` 记录保持兼容，不重写旧证据。

私有参考源码和隐藏用例内容不进入会话状态、AI 提示、页面详情或 JSON 导出。隐藏验证仅记录编号、是否公开、状态及通过标志；实际输入、期望、输出、错误、源码行均丢弃。AI 仅收到公开题面、公开样例、自定义例子和本人主动带入的草稿。

会话及来源提交均检查所属账号、题目与语言。写操作携带 `revision`，耗时生成或执行先预留版本，完成时用 CAS 再提交，通常增加 2 个版本。过期操作不会覆盖较新的编辑。五分钟以上未完成的生成记录在读取时标为失败，不能伪装成成功。

每个账号最多 80 条会话；每条最多 12 个例子、最近 40 次生成、80 条运行和事件，质检最多 40 条证据及 20 个历史代码版本。源码、输入、输出、请求体和 Docker 时间/内存/输出上限沿用主站限制。

## API 契约

前缀 `/api/co-create`。成功响应 `{success:true,data:{...}}`，错误响应包含 `error.code/message`。除目录外须登录；写请求须 JSON 和 CSRF。

| 路径 | 请求 | 返回 data |
| --- | --- | --- |
| GET `/catalog` | 语言能力、AI 是否可用；旧 scenarios 仅用于兼容 | `{languages,problem_driven,ai_available,problems_url,scenarios}` |
| GET `/sessions` | 本人记录摘要 | `{sessions}` |
| POST `/sessions` | `{mode,problem_id,language,code?,input_text?,submission_id?}` | 201 `{session}` |
| GET `/sessions/<id>` | 恢复本人记录 | `{session}` |
| PATCH `/sessions/<id>` | `{revision,action:"upsert_example",example:{id?,input,expected?}}` 或 delete_example | `{session}` |
| POST `/sessions/<id>/generate` | `{revision,source:"ai"}` | `{session}` |
| POST `/sessions/<id>/compare` | `{revision,input,expected?,input_validated?}` | `{session,run}` |
| POST `/sessions/<id>/select` | `{revision,generation_id,candidate_id}` | `{session}` |
| POST `/sessions/<id>/review` | `{revision,code?,judgment?,prediction?,prediction_input?,clear_prediction?,reflection?}` | `{session}` |
| POST `/sessions/<id>/review-run` | `{revision,input,expected?,input_validated?}` | `{session,run}` |
| POST `/sessions/<id>/review-generate` | `{revision,source:"ai"}` | `{session}` |
| POST `/sessions/<id>/verify` | `{revision,candidate_id?}`；质检省略 ID 使用当前代码 | `{session,run}` |
| POST `/sessions/<id>/handoff` | `{revision,candidate_id}`；质检当前代码使用 `"review"` | `{proposal,problem_id,language}` |

题目 session 顶层含 `problem_id/language/legacy:false/problem/state`，`problem` 有公开样例、指纹、参考可用与题目是否更新。状态 `practice_context` 保存原带入草稿及输入，为刷题采纳流程提供版本基线。历史场景 session 返回 `legacy:true`。

生成状态为 `running/ready/failed`。ready 表示候选已生成并记录当前例子的执行情况，不等于全部正确。候选 `verification.scope == "examples"`；`verified` 仅指本次公开官方例子通过。用户期望和无答案输入不参与此标志。

自定义运行有 `expected_source`、`passed` 和 `verdict`。verdict 为 `passed/failed/matches_user/differs_user/unverified/execution_failed`；不要仅凭底层 runner 的成功退出把程序判为正确。题库 verify 单独返回逐项脱敏结果、total、passed_count、hidden_total/hidden_passed 与代码指纹。

`judgment` 为 `correct/incorrect/unsure`，判断与预测都可省略。没有预测时 `prediction_matched:null`，不编造匹配结果。提供预测时必须绑定保存后的代码版本与对应输入；输入改变后须重新保存预测或显式 `clear_prediction:true`。代码修改会清除旧预测。旧代码历史与证据不重新标记为当前版本。

## 带回刷题与采纳记录

handoff 只准备一条所属本人的 `CodeProposal` 和一条共创事件，不直接改编辑器，不创建正式提交，不加积分。它检查当前会话版本、当前候选、语言和题目快照；质检代码按代码指纹形成稳定标识，重复带回同一候选返回同一提案。

即使还没有任何刷题提交，提案也可以出现在当前题目和语言的过程回顾中，不会伪造一个父提交。本人查看代码差异后，通过原有 `/api/proposals/<id>/actions` 的 accept/reject/undo 操作采纳、拒绝或撤回。accept 要求编辑器仍与带入共创时的草稿基线相同，undo 要求编辑器仍是被采纳的候选；继续编辑或切换语言时会拒绝覆盖。

正式提交复测沿用 `/api/check-solution`，携带 proposal_id/proposal_revision 和 operation_id。只有这个明确的正式判题动作才保存 Submission，并按原规则增加首次通过积分。没有原提交时 parent_submission_id 保持空；重放同一复测操作不会重复判题、写记录或加积分。修改候选后再提交仍保存实际代码，不把结果错误归因于未修改的 AI 候选。

`tests/test_co_create_handoff.py` 使用独立数据库及模拟执行器覆盖此链路，包括空提交历史、版本过期、跨用户/语言、草稿保护、重复带回和正式复测。

## 关键文件与验证

- `problem_service.py`：题目快照、参考版本绑定、三种语言程序执行、例子、质检及脱敏题库验证。
- `ai.py`：真实模型的完整程序协议，忽略模型自行返回的 verified/source 等可信性声明。
- `service.py/catalog.py`：历史场景兼容、通用 CAS 与记录归属。
- `routes.py/models.py`：API、请求限制与模型；迁移由主站统一维护。
- `tests/test_problem_co_create.py`：题目新流程、官方与个人答案分离、未知答案、参考绑定、隐藏数据、账号与版本冲突。
- `tests/test_co_create.py`：旧场景回归，确保历史行为不因新模块失效。

单元测试使用独立 SQLite 与模拟 Docker/AI 传输，不在宿主执行提交代码，不调用付费 API：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_problem_co_create tests.test_co_create -v
```

真实 Docker 验证应使用独立测试库。启动主站前先备份并执行主站迁移，再确认隔离镜像覆盖 Python、C++ 与 Java。没有 Docker 时执行失败，不回退到应用宿主。

`scripts/verify_co_create.py` 保留为历史三场景验证脚本，其结果不能当作新题目驱动或新增 Java 的验证证明。历史 2026-10-15 的 21 次 Docker 与两次真实 AI 验证属于旧版本；新版本以本次实际测试结果为准。

### 2026-10-17 验证记录

全量 Python 回归 193 项通过。新增的前端控制器回归覆盖生成前保存当前草稿、失败后保留输入，以及带回刷题时展开外层记录和差异卡片；已有草稿不会自动替换成候选代码。

`scripts/verify_problem_co_create.py` 使用独立随机 SQLite，共完成 69 次真实 Docker 执行，覆盖 Python / C++ / Java 的生成后用例检查、未知答案、参考对照、隐藏用例脱敏、带回、采纳、撤销、再次采纳及正式复测。该脚本明确使用 `test-stub` 候选，收费 AI 调用为 0，不能代表模型生成验证。

另外在独立浏览器测试库真实调用 DeepSeek 两次：C++ 用例共创和 Java 代码质检。两份模型实现均通过秒数换算题现有 6 个用例；C++ 还完成浏览器内采纳、撤销、再采纳和正式提交，Java 完成无预测直接运行。模型来源记录为 `deepseek-flash`。这只证明上述实际样本和当前用例结果，不证明所有题目的模型答案正确。

本机详细报告保存在 `tmp/problem-co-create-check/docker-verification-latest.json` 和 `tmp/problem-language-check/live-ai-browser.json`。重跑无收费验证：

```powershell
.\.venv\Scripts\python.exe scripts/verify_problem_co_create.py
```

## 保留数据撤回

若暂时隐藏模块，保留共创表、迁移记录和旧会话，只撤回入口与前端集成。不要用旧共创迁移的 downgrade 代替隐藏功能，因为历史迁移会删除会话表。题目被删除或更新时历史快照仍可读取，验证入口会明确停止并要求新建记录。


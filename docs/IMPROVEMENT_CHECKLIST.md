# 项目改进清单

更新时间：2026-05-17

## 当前状态

- 本地仓库已完成多轮安全、测试、前端拆分和后端判题增强。
- 本地 `main` 仍领先远端 `origin/main`，需要在网络恢复后推送。
- 当前基础检查命令：

```bash
make check
```

## 已完成

- 初始化 Git 仓库并提交基线。
- 创建 GitHub 私有仓库。
- 移除源码中的默认 AI API Key。
- 移除硬编码管理员弱密码。
- 管理员创建改为环境变量或 `flask --app app create-admin`。
- 默认关闭 Flask debug。
- 收紧 CORS 来源配置。
- 高风险接口增加登录限制。
- 代码运行增加基础资源限制。
- 代码运行限制改为环境变量配置。
- 请求 payload 增加语言、代码长度、标准输入长度、AI prompt 长度校验。
- 代码运行输出增加截断保护。
- 昂贵接口增加内存版频率限制。
- AI 调用封装到 `services/ai_client.py`。
- AI 代码优化改为优先结构化 JSON，兼容 Markdown 回退。
- 前端拆分：
  - `index.html` 拆出 `static/css/index.css`、`static/js/index.js`
  - `practice.html` 拆出 `static/css/practice.css`、`static/js/practice.js`
  - `learn-analytics.html` 拆出 `static/css/learn-analytics.css`、`static/js/learn-analytics.js`
- 新增公共用户会话脚本 `static/js/user-session.js`。
- 清理首页模拟运行、模拟 AI 优化、模拟提交逻辑。
- 首页入口改为跳转真实题目选择流程。
- 提交判题避免重复 Accepted 无限加分。
- 提交表增加常用查询索引迁移。
- 提交记录查询去除 N+1 查询。
- 判题增强：
  - 忽略行尾空白
  - 支持浮点误差比较
  - 区分 `Compile Error`、`Runtime Error`、`Time Limit Exceeded`
- 新增 `Makefile`。
- 新增 GitHub Actions CI。
- 新增 `pyproject.toml`。
- 单元/API 测试扩展到 17 个。

## P0：必须优先处理

1. 推送本地提交到 GitHub

```bash
git push
```

当前由于网络连接 GitHub 失败，远端还没收到最近提交。

2. 真正代码执行沙箱

当前仍是本机进程级资源限制，不是强隔离。公网部署前应接入以下方案之一：

- Docker 隔离容器
- nsjail
- Firecracker
- Judge0
- 独立 worker + 低权限用户 + 容器网络隔离

3. CSRF 防护

当前使用 Cookie 登录态，POST 接口应增加 CSRF token。

4. 旧 API Key 吊销

如果曾经写在源码中的 SiliconFlow Key 是真实可用 Key，应到平台后台吊销并重新生成。

## P1：高优先级

1. 登录和接口限流持久化

当前限流存在内存中，进程重启会丢失，多进程不共享。建议接 Redis。

2. 后台题目导入增强

当前导入接口还需要返回更详细的结构：

- 成功导入题目列表
- 跳过题目列表
- 跳过原因
- 每题测试用例数量
- 解析失败明细

3. 统一 API 返回格式

建议普通 JSON 接口统一为：

```json
{
  "success": true,
  "data": {},
  "message": ""
}
```

错误统一为：

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "错误说明"
  }
}
```

4. 数据库迁移实测

在干净数据库上执行：

```bash
flask --app app db upgrade
```

确认所有迁移可从空库完整跑通。

5. 判题能力继续增强

- 多合法答案
- Special Judge
- 输出大小限制提示更友好
- 编译耗时和运行耗时分开记录
- 每个测试用例返回结构化结果

## P2：中优先级

1. 前端 AI 流式输出取消按钮

涉及：

- AI 聊天
- AI 学习路径
- AI 学习分析
- AI 补全

2. 统一前端 loading / error / retry

将代码运行、提交、AI 请求的状态反馈统一成共享组件或公共函数。

3. 公共 CSS 抽取

目前页面 CSS 已拆分，但按钮、卡片、导航、用户信息区仍可继续抽为共享样式。

4. 登录/注册页体验优化

- 密码规则提示
- 登录失败次数提示
- 表单校验
- 错误展示替代 `alert`

5. 后台管理页增强

- 题目列表
- 测试用例编辑
- 删除/更新题目
- 导入结果明细展示

6. 学习时长上报增强

- 防刷策略
- 前端心跳上报
- 后端单日最大值限制
- 页面可见性判断

## P3：工程化

1. CI 实际运行 Ruff / Black

当前已有 `pyproject.toml`，但依赖和 CI 尚未实际运行：

```bash
ruff check .
black --check .
```

2. 增加迁移测试

在 CI 中用临时数据库跑：

```bash
flask --app app db upgrade
```

3. 增加 Playwright 冒烟测试

建议覆盖：

- `/index.html`
- `/login.html`
- `/register.html`
- `/problem_selector.html`
- `/practice.html`
- `/learn-analytics.html`

检查内容：

- 页面 200
- 无 JS runtime error
- 核心按钮存在
- 登录态/游客态用户区正常

4. 依赖安全扫描

可接入：

- Dependabot
- pip-audit

5. 发布/部署文档

需要补充：

- 生产环境变量
- 数据库迁移流程
- 管理员创建流程
- 反向代理配置
- HTTPS
- 代码沙箱部署

## P4：产品体验

1. 移动端视觉检查

需要实际检查首页、刷题页、学习分析页在移动端是否有遮挡、溢出、按钮过小等问题。

2. 排行榜产品含义明确

区分：

- 解题数
- 积分
- 学习时长
- 正确率

3. 刷题页导航增强

- 上一题
- 下一题
- 回题库
- 当前题进度
- 已通过标记

4. 学习分析页结果持久化

AI 分析结果可缓存，避免每次刷新都重新请求 AI。

5. 题目详情安全白名单

后台导入时已经做基础清洗，但题目描述 HTML 最好引入严格白名单策略。

## 建议下一步执行顺序

1. `git push` 同步远端。
2. 增强后台题目导入返回明细。
3. 统一 API 返回格式。
4. 增加迁移测试。
5. 接入 CSRF。
6. 设计并接入真正代码沙箱。

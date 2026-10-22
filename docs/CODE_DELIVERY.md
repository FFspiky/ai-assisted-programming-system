# 代码交付与运行镜像

提交预览目录保持展开状态，包含 `CodeLab/` 源码、`runtime/` 执行镜像、`开始使用.md` 和 `文件清单.sha256`。`runtime/*.tar` 是 Docker 导入文件，不是项目压缩包。

## 运行条件

- Python 3.11 或更新版本；首次安装 Python 依赖需要联网。
- Docker 已启动并使用 Linux 容器。随附镜像为 **Linux/amd64**，适合常见的 x86-64 Windows/Linux/macOS 主机。
- ARM 主机需在本机从 `sandbox/` 构建相应架构镜像；不保证模拟运行的时限和性能。
- AI 功能需要能访问 DeepSeek 官方 API 的网络及有效 Key。手动练习、判题不需要 AI Key。
- 页面图标及字体均为本地文件。Node.js/npm 仅前端回归测试需要。

## 使用随附镜像

在 `CodeLab/` 中执行：

```sh
python -m pip install -r requirements.txt
python scripts/runner_image.py load ../runtime
```

导入脚本先校验镜像文件 SHA-256，导入后核对镜像 ID、平台、执行器源码与容器用户，并通过应用执行器运行 Python/C++ 求和样例。此过程不访问镜像仓库、不读取 AI Key。

推荐直接使用 [评审快速配置](SUBMISSION_START.md) 中的 Windows/macOS 脚本，自动完成环境、镜像与数据库准备。代码目录不携带真实用户、演示口令或 API Key。评审专用 Key 可单独随附在 `runtime/reviewer-key.json`，配置弹窗同意后自动启用；个人资料页可改用个人 Key 或停用 AI。

随附专用账户提供所有评委共享的 10 元测试额度，剩余额度以账户余额为准。每次调用先查询余额，余额不足或查询失败时不调用模型。网络异常、认证失败和余额不足分别提示，不将所有失败解释为欠费。接口依据见 [DeepSeek 账户余额](https://api-docs.deepseek.com/zh-cn/api/get-user-balance/) 和 [官方错误码](https://api-docs.deepseek.com/zh-cn/quick_start/error_codes/)。程序不吊销平台 Key，也不以本机累计数值承诺精确扣费上限。

仅有源码、没有 `runtime/` 时，可联网构建并校验：

```sh
docker build -t codelab-runner:local sandbox
python scripts/runner_image.py check
```

镜像来源为 `sandbox/Dockerfile`：官方 Python 3.11 Debian Bookworm 基础镜像、Debian g++ 编译器及本项目执行器。镜像文件保留所包含组件的许可信息，Debian 软件许可位于镜像 `/usr/share/doc/`，Python 许可位于 `/usr/local/lib/python3.11/LICENSE.txt`。导出不包含应用目录、数据库或应用密钥。

## 维护端重新整理目录

在开发仓库中执行，目标目录必须尚不存在：

```sh
python scripts/prepare_submission.py --destination ../submission-preview
```

若需要随附评审 Key，显式增加 `--reviewer-key-file .private/reviewer-key.json`。该私有 JSON 格式为 `{"api_key":"<评审专用 Key>","budget_cny":"10.00"}`；真实文件放入被 Git 忽略的 `.private/`，不得填写到脚本、测试、文档或 `.env.example`。组装脚本仅复制至提交目录的 `runtime/`，不会放进 `CodeLab/`。未提供该参数时不包含 Key。

此脚本按代码与文档清单复制当前工作区（包括尚未提交的代码修改），导出已校验的执行镜像，并生成文件校验清单。不会创建项目 ZIP，也不会修改现有提交目录或执行 Git 提交。

源码清单排除 `.git`、实际 `.env`、`.private/`、`instance/`、用户数据库、密钥、虚拟环境、`node_modules/`、测试输出、官方赛事资料和内部设计过程文档。唯一可显式随附的凭据是上述评审测试 Key。保留当前测试、迁移、依赖声明与第三方许可，便于复核。项目配置只有 `.env.example` 模板。

# 智练 CodeLab · 代码提交目录

此目录保持展开状态，尚未制作项目压缩包。

| 目录或文件 | 内容 |
| --- | --- |
| `CodeLab/` | 源码、Windows/macOS 配置及启动脚本、测试、迁移、题库与本地页面资源 |
| `runtime/` | Linux/amd64 Docker 执行镜像、校验信息及评审专用测试 Key |
| `文件清单.sha256` | 源码、镜像与随附配置文件的 SHA-256 校验清单 |

## 首次配置

请先安装 **Python 3.11+** 和 **Docker Desktop**，打开 Docker Desktop，等待 Linux 容器引擎运行。首次安装 Python 依赖需要联网。无需安装 Node.js，也无需手动编辑 `.env`。

**Windows：**进入 `CodeLab`，双击 `setup-windows.cmd`，完成后双击 `start-windows.cmd`。

**macOS：**打开终端，输入 `cd ` 后将 `CodeLab` 文件夹拖入终端并回车，然后依次执行：

```sh
bash setup-macos.command
bash start-macos.command
```

使用 `bash` 启动不依赖文件的可执行权限。Intel Mac 使用随附镜像；Apple Silicon Mac 会自动构建 arm64 原生镜像，首次构建还需要联网访问 Docker Hub 和 Debian 软件源。

配置脚本会创建独立 Python 环境、生成随机会话密钥、检查执行镜像，并通过数据库迁移导入 63 道题。重复运行会保留已有配置和用户数据，升级已有数据库前自动备份。遇到未纳入迁移管理的旧数据库会停止并提示。

## 评审测试额度

配置时会弹窗询问是否使用随附的 DeepSeek 官方测试 Key：

- **是 / 使用：**自动写入本地配置；注册并登录后即可体验 AI。已有网页个人 Key 或明确停用 AI 的设置仍然优先。
- **否 / 跳过：**跳过此项，保留已有配置。首次配置时可稍后在「个人主页 → 个人资料 → AI 服务配置」填写自己的 DeepSeek Key。

我们准备了一个独立账户，提供**所有评委共享的 10 元测试额度**，不是每位评委各 10 元。实际可用金额以账户剩余余额为准。程序在使用测试 Key 的每次模型调用前查询官方账户余额；余额不足时停止此次调用，并提示改用个人 Key。余额查询失败时也暂不调用模型，可检查网络后重试。

官方 API 提供账户余额查询，不提供单个 Key 累计消费查询或由本程序吊销 Key 的能力。这里依据独立账户余额控制使用；正在执行或并发请求的结算由 DeepSeek 处理，不承诺精确到分的消费上限。请勿再充值该专用账户，以免扩大共享可用额度。

余额不足、Key 失效、网络故障与请求过于频繁会分别提示；**无法使用不一定代表欠费**。额度用尽后，在个人资料页保存自有 Key 即可继续使用 AI。手动编程、运行与判题不依赖 AI Key。

`runtime/reviewer-key.json` 仅供评审使用，脚本将其写入接收方本地 `.env`；页面和日志不会显示完整 Key。它不在源码和 Git 中。请勿将带 Key 的提交目录上传到公开代码仓库。

## 启动与快速核验

日后只需运行对应系统的 `start` 脚本。浏览器会自动打开本地地址（默认 `http://127.0.0.1:5001`，占用时自动选择邻近端口），注册并登录即可使用。关闭服务请在启动窗口按 Ctrl+C。

1. 镜像校验会实际运行 Python/C++ 样例，两者均应输出 `PASS`。
2. 初始化应得到 63 道题。选择「秒数换算」或「整数求和」，编写、运行并提交代码。
3. 查看学习共创、任务室和个人资料；头像支持 PNG/JPEG/WebP。

高级用法：`setup-windows.cmd --reviewer-key skip` 或 `bash setup-macos.command --reviewer-key skip` 跳过弹窗；`--reviewer-key use` 表示明确同意使用随附 Key；启动加 `--no-browser` 可关闭自动打开浏览器。

完整回归命令见 [启动与验证](COMPETITION_PREVIEW.md)，镜像及目录维护见 [代码交付说明](CODE_DELIVERY.md)。前端资源许可见 [本地前端依赖](../static/vendor/README.md)；桌宠许可见 [素材署名](../static/images/dafeiyu/ATTRIBUTION.md)。

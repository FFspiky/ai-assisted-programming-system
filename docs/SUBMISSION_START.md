# 智练 CodeLab · 代码提交目录

此目录保持展开状态，尚未制作项目压缩包。

| 目录或文件 | 内容 |
| --- | --- |
| `CodeLab/` | 源码、Windows/macOS 配置及启动脚本、测试、迁移、题库与本地页面资源 |
| `runtime/` | Linux/amd64 Docker 执行镜像、校验信息及评审专用测试 Key |
| `文件清单.sha256` | 源码、镜像与随附配置文件的 SHA-256 校验清单 |

## 首次配置

无需提前安装 Python、Docker、Homebrew 或 WinGet。直接运行下面的配置脚本即可检查环境；缺少 Python 3.11+ 或 Docker Desktop 时，会询问是否从官方网站下载安装。首次配置需要联网和必要的系统安装权限；已有可用环境会直接复用。无需安装 Node.js，也无需手动编辑 `.env`。

**Windows：**进入 `CodeLab`，双击 `setup-windows.cmd`，完成后双击 `start-windows.cmd`。

**macOS：**打开终端，输入 `cd ` 后将 `CodeLab` 文件夹拖入终端并回车，然后依次执行：

```sh
bash setup-macos.command
bash start-macos.command
```

使用 `bash` 启动不依赖文件的可执行权限。Intel Mac 使用随附镜像；Apple Silicon Mac 会自动构建 arm64 原生镜像，首次构建还需要联网访问 Docker Hub 和 Debian 软件源。

### 缺少系统软件时

1. 按提示输入 `y` 同意安装，直接回车或输入 `n` 会停止本次配置。非交互终端不会自动同意安装。
2. Python 从 python.org 下载 3.13.17 安装包并校验 SHA-256；Windows 为当前用户安装，macOS 会请求登录密码安装官方通用包并配置 HTTPS 证书。
3. Docker 从 Docker 官网下载对应架构的安装包，并校验发布者签名。Windows 同时检查 WSL 2，缺少或过旧时请求管理员授权安装/更新，不额外安装 Ubuntu。
4. 在 Docker Desktop 窗口中完成首次协议确认和系统授权。脚本最多等待引擎 5 分钟，随后继续配置项目；超时后可完成 Docker 设置，再运行相同脚本。
5. **系统要求重启时，请手动重启，再次运行相同 `setup` 脚本。** 已安装的软件会被识别，已有项目配置和数据会保留。脚本不会自动重启，也不会自动修改 BIOS/UEFI 虚拟化设置。

Docker 对操作系统版本、内存和虚拟化有要求，受管电脑的安装策略也可能阻止安装。对应说明见 [Docker Windows 安装要求](https://docs.docker.com/desktop/setup/install/windows-install/)、[Docker macOS 安装要求](https://docs.docker.com/desktop/setup/install/mac-install/) 和 [WSL 官方安装命令](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)。下载失败、签名/哈希校验失败、取消系统授权时，脚本会停止，不会报告配置完成；修复后可重试。Python 安装包及校验值来自 [Python 3.13.17 官方发布页](https://www.python.org/downloads/release/python-31317/)。

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

已由管理员准备好环境时，可给 `setup` 增加 `--skip-prerequisites`，只检查依赖而不安装或启动系统软件。`start` 脚本始终不安装软件；日后启动前请先打开 Docker Desktop。

完整回归命令见 [启动与验证](COMPETITION_PREVIEW.md)，镜像及目录维护见 [代码交付说明](CODE_DELIVERY.md)。前端资源许可见 [本地前端依赖](../static/vendor/README.md)；桌宠许可见 [素材署名](../static/images/dafeiyu/ATTRIBUTION.md)。

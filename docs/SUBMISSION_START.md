# 智练 CodeLab · 代码提交目录

此目录保持展开状态，尚未制作项目压缩包。

| 目录或文件 | 内容 |
| --- | --- |
| `CodeLab/` | Flask 源码、当前测试、迁移、题库、页面、本地字体图标与依赖声明 |
| `runtime/` | Linux/amd64 Docker 执行镜像与校验信息 |
| `文件清单.sha256` | 源码与镜像文件的 SHA-256 校验清单 |

## 首次启动

需要 Python 3.11+、Docker（Linux 容器模式）。Python 依赖首次安装需要联网；AI 使用有效的 DeepSeek 官方 Key。随附镜像适用于 x86-64 主机，ARM 主机的替代构建方式见 [代码交付说明](CODE_DELIVERY.md)。

进入 `CodeLab`，创建并激活虚拟环境：

```sh
python -m venv .venv
```

Windows PowerShell 执行 `.\.venv\Scripts\Activate.ps1`；macOS/Linux 执行 `source .venv/bin/activate`。若 PowerShell 禁止激活脚本，可将后续命令中的 `python` 替换为 `.\.venv\Scripts\python.exe`，无需更改系统执行策略。

```sh
python -m pip install -r requirements.txt
python scripts/runner_image.py load ../runtime
python scripts/prepare_competition_preview.py --database tmp/competition.db
```

将 `.env.example` 复制为 `.env`，将 `FLASK_SECRET_KEY` 替换为随机字符串；可用 `python -c "import secrets; print(secrets.token_hex(32))"` 生成。按需填写 `DEEPSEEK_API_KEY`。密钥与数据库由接收方本地创建，目录不包含现成账号或私人配置。

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

打开 `http://127.0.0.1:5001`，注册并登录即可使用。首次 AI 调用前，在「个人主页 → 个人资料 → AI 服务配置」保存个人 Key 或选择项目测试 Key。未配置 AI 时仍可手动编程、运行与判题。

## 快速核验

1. 导入镜像时，脚本自动检查文件校验值并实际运行 Python/C++ 样例，两者均应输出 `PASS`。
2. 初始化应得到 63 道题。选择「秒数换算」或「整数求和」，编写、运行并提交代码。
3. 查看学习共创、任务室和个人资料；头像支持 PNG/JPEG/WebP。

完整回归命令见 [启动与验证](COMPETITION_PREVIEW.md)。前端资源来源与许可证见 [本地前端依赖](../static/vendor/README.md)；桌宠来源与许可证见 [素材署名](../static/images/dafeiyu/ATTRIBUTION.md)。

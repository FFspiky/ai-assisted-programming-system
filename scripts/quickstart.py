"""Local setup/start shared by the Windows and macOS launchers."""

import argparse
import json
import os
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import urllib.request
import venv
import webbrowser
from contextlib import closing
from datetime import datetime
from pathlib import Path

try:
    from .prerequisites import PrerequisiteError, ensure_docker, refresh_docker_path
    from .reviewer_config import read_reviewer_key
except ImportError:
    from prerequisites import PrerequisiteError, ensure_docker, refresh_docker_path
    from reviewer_config import read_reviewer_key

ROOT = Path(__file__).resolve().parents[1]
TAG = "codelab-runner:local"


class SetupError(Exception):
    pass


def run(command, env=None, **kwargs):
    return subprocess.run(command, cwd=ROOT, env=env, check=True, **kwargs)


def docker_platform():
    if not shutil.which("docker"):
        raise SetupError("请先安装 Docker Desktop，再重新运行配置脚本。")
    try:
        value = subprocess.check_output(
            ["docker", "info", "--format", "{{.OSType}}/{{.Architecture}}"],
            stderr=subprocess.PIPE,
            timeout=20,
            text=True,
            encoding="utf-8",
        ).strip()
    except (subprocess.SubprocessError, OSError) as exc:
        raise SetupError("Docker 未就绪。请启动 Docker Desktop，等待引擎运行后重试。") from exc
    system, _, architecture = value.partition("/")
    architecture = {"x86_64": "amd64", "aarch64": "arm64"}.get(architecture, architecture)
    if system != "linux" or architecture not in {"amd64", "arm64"}:
        raise SetupError(
            "需要 Linux 容器引擎（amd64 或 arm64）；Windows 请切换到 Linux containers。"
        )
    return f"linux/{architecture}"


def ensure_environment(root):
    from dotenv import dotenv_values

    path = root / ".env"
    if not path.exists():
        text = (root / ".env.example").read_text(encoding="utf-8")
        replacements = {
            "FLASK_SECRET_KEY": secrets.token_hex(32),
            "DEEPSEEK_API_KEY": "",
            "DATABASE_URL": "sqlite:///competition.db",
        }
        lines = []
        for line in text.splitlines():
            key = line.partition("=")[0]
            lines.append(f"{key}={replacements[key]}" if key in replacements else line)
        lines.append("AUTO_CREATE_DATABASE=0")
        # Never overwrite a concurrent or previous configuration.
        with path.open("x", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        if os.name != "nt":
            path.chmod(0o600)
        print("已生成本地 .env 和随机会话密钥；AI Key 可稍后在网页中填写。", flush=True)
    settings = {k: v for k, v in dotenv_values(path, interpolate=False).items() if v is not None}
    if settings.get("FLASK_SECRET_KEY", "") in {"", "change-me", "replace-with-a-random-secret"}:
        raise SetupError(
            "已有 .env 的 FLASK_SECRET_KEY 为空或仍是示例值。请设置随机密钥后重试；原配置未覆盖。"
        )
    return settings


def ask_reviewer_key(existing=False):
    message = (
        "是否直接使用随附的 DeepSeek 评审测试 Key？\n\n"
        "所有评委共享 10 元测试额度，用尽后请在个人资料页填写自己的 Key。\n"
        "选择“否 / 跳过”将跳过此项，保留已有配置。"
    )
    if existing:
        message += "\n选择“是 / 使用”将替换本地已有的服务器 Key；网页中的个人 Key 不受影响。"
    try:
        if sys.platform == "win32":
            import ctypes

            return (
                ctypes.windll.user32.MessageBoxW(None, message, "智练 CodeLab · 评审配置", 0x124)
                == 6
            )
        if sys.platform == "darwin":
            script = (
                "on run argv\n"
                'set result to display dialog (item 1 of argv) with title "智练 CodeLab · 评审配置" '
                'buttons {"跳过", "使用"} default button "跳过" cancel button "跳过"\n'
                "return button returned of result\nend run"
            )
            result = subprocess.run(
                ["osascript", "-e", script, message], capture_output=True, text=True
            )
            return result.returncode == 0 and result.stdout.strip() == "使用"
    except (OSError, AttributeError):
        pass
    if not sys.stdin.isatty():
        return False
    print(message, flush=True)
    return input("使用测试 Key？输入 y 确认，直接回车跳过：").strip().lower() == "y"


def configure_reviewer_key(root, settings, choice="ask"):
    from dotenv import dotenv_values, set_key

    bundle = root.parent / "runtime" / "reviewer-key.json"
    if choice == "skip":
        return settings
    if not bundle.exists():
        if choice == "use":
            raise SetupError("缺少 runtime/reviewer-key.json，无法使用随附测试 Key。")
        return settings
    if choice == "ask" and not ask_reviewer_key(bool(settings.get("DEEPSEEK_API_KEY"))):
        print("已跳过测试 Key 配置；可在个人资料页填写自己的 Key。", flush=True)
        return settings
    key = read_reviewer_key(bundle)
    path = root / ".env"
    set_key(path, "DEEPSEEK_API_KEY", key)
    set_key(path, "REVIEWER_TEST_KEY_ENABLED", "1")
    if os.name != "nt":
        path.chmod(0o600)
    print("已启用共享 10 元评审测试额度；每次模型调用前会检查账户余额。", flush=True)
    return {k: v for k, v in dotenv_values(path, interpolate=False).items() if v is not None}


def database_path(root, settings):
    from sqlalchemy.engine import make_url

    try:
        url = make_url(settings.get("DATABASE_URL", "sqlite:///competition.db"))
    except Exception as exc:
        raise SetupError("DATABASE_URL 无效，请检查本地配置。") from exc
    if url.drivername != "sqlite" or not url.database or url.database == ":memory:" or url.query:
        raise SetupError("快速配置仅支持本地 SQLite 文件；其他数据库请按部署说明手动初始化。")
    path = Path(url.database)
    path = (path if path.is_absolute() else root / "instance" / path).resolve()
    if not path.is_relative_to(root.resolve()):
        raise SetupError("数据库位于项目目录外，快速配置不会修改它。请使用独立的代码提交目录。")
    return path


def backup_database(path):
    if not path.exists() or path.stat().st_size == 0:
        return None
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as source:
        tables = {
            row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if not tables:
            return None
        if "alembic_version" not in tables:
            raise SetupError(
                "检测到未由迁移管理的旧数据库，已停止且未改动它。请使用干净的提交目录。"
            )
        backup_dir = path.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        backup = (
            backup_dir / f"{path.stem}-{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(3)}.db"
        )
        with closing(sqlite3.connect(backup)) as target:
            source.backup(target)
    return backup


def runner_action(platform, bundled_platform, installed_platform):
    if installed_platform == platform:
        return "check"
    return "load" if bundled_platform == platform else "build"


def ensure_runner(platform, settings, env):
    image = settings.get("CODE_SANDBOX_IMAGE", TAG)
    helper = [sys.executable, "-B", "scripts/runner_image.py"]
    if image != TAG:
        run([*helper, "check", "--image", image], env)
        return
    try:
        installed = subprocess.check_output(
            ["docker", "image", "inspect", TAG, "--format", "{{.Os}}/{{.Architecture}}"],
            stderr=subprocess.PIPE,
            timeout=20,
            text=True,
            encoding="utf-8",
        ).strip()
    except subprocess.CalledProcessError:
        installed = ""
    runtime = ROOT.parent / "runtime"
    metadata = runtime / "runner-image.json"
    bundled = (
        json.loads(metadata.read_text(encoding="utf-8"))["platform"] if metadata.exists() else ""
    )
    action = runner_action(platform, bundled, installed)
    if action == "check":
        try:
            run([*helper, "check"], env)
            return
        except subprocess.CalledProcessError:
            print("已有镜像未通过当前源码校验，准备重新导入或构建。", flush=True)
            action = runner_action(platform, bundled, "")
    if action == "load":
        print("导入随附镜像并验证 Python/C++（无需访问 Docker Hub）……", flush=True)
        run([*helper, "load", str(runtime)], env)
    else:
        print(
            f"需要 {platform} 原生镜像。首次构建需联网访问 Docker Hub 和 Debian 软件源。",
            flush=True,
        )
        run(["docker", "build", "--platform", platform, "-t", TAG, "sandbox"], env)
        run([*helper, "check"], env)


def child_environment(settings):
    env = dict(os.environ)
    env.update(settings)
    env.update(
        PYTHONUTF8="1",
        PYTHONIOENCODING="utf-8",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHON_DOTENV_DISABLED="1",
        AUTO_CREATE_DATABASE="0",
        FLASK_DEBUG="0",
    )
    return env


def choose_port(preferred):
    if not 1024 <= preferred <= 65535:
        raise SetupError("FLASK_PORT 必须是 1024 到 65535 之间的端口。")
    for port in range(preferred, min(preferred + 20, 65536)):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise SetupError("附近端口均被占用，请关闭已有服务后重试。")


def open_when_ready(url, finished):
    for _ in range(60):
        if finished.wait(0.5):
            return
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except OSError:
            continue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["setup", "start"])
    parser.add_argument(
        "--reviewer-key",
        choices=["ask", "use", "skip"],
        default="ask",
        help="Setup consent: show a dialog (default), use or skip the bundled test key",
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="Do not open the browser on start"
    )
    parser.add_argument(
        "--skip-prerequisites",
        action="store_true",
        help="Only check prerequisites; never install or launch system software",
    )
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        raise SetupError("需要 Python 3.11 或更新版本。请安装后重新运行。")
    refresh_docker_path()
    if args.action == "setup" and not args.skip_prerequisites:
        ensure_docker()
    platform = docker_platform()
    virtualenv = ROOT / ".venv"
    python = virtualenv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        if args.action == "start":
            raise SetupError("尚未配置，请先运行 setup-windows.cmd 或 setup-macos.command。")
        if virtualenv.exists():
            raise SetupError("已有 .venv 不完整，请将其改名保留后重新配置。")
        print("[1/5] 创建项目专用 Python 环境……", flush=True)
        venv.EnvBuilder(with_pip=True).create(virtualenv)
    if Path(sys.prefix).resolve() != virtualenv.resolve():
        command = [str(python), "-B", str(Path(__file__).resolve()), args.action]
        command.extend(["--reviewer-key", args.reviewer_key])
        if args.no_browser:
            command.append("--no-browser")
        # Prerequisites were already checked by the parent process.
        command.append("--skip-prerequisites")
        result = subprocess.run(command, cwd=ROOT, env=child_environment({}))
        return result.returncode
    if args.action == "setup":
        print("[2/5] 安装应用依赖（首次需要联网）……", flush=True)
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-r",
                "requirements.txt",
            ]
        )
    elif not (ROOT / ".env").exists():
        raise SetupError("缺少配置，请先运行配置脚本。")
    settings = ensure_environment(ROOT)
    if args.action == "setup":
        settings = configure_reviewer_key(ROOT, settings, args.reviewer_key)
    path = database_path(ROOT, settings)
    env = child_environment(settings)
    if args.action == "setup":
        print("[3/5] 检查执行镜像……", flush=True)
        ensure_runner(platform, settings, env)
        print("[4/5] 初始化或升级本地数据库……", flush=True)
        backup = backup_database(path)
        if backup:
            print(f"已有数据库已备份：{backup.relative_to(ROOT)}", flush=True)
        run(
            [
                sys.executable,
                "-B",
                "scripts/prepare_competition_preview.py",
                "--database",
                str(path),
            ],
            env,
        )
        print("[5/5] 配置完成。运行 start-windows.cmd 或 start-macos.command 启动。", flush=True)
        print("打开网页后注册账号；个人资料页可查看或更换 AI 服务配置。", flush=True)
        return 0
    if not path.exists():
        raise SetupError("数据库尚未初始化，请先运行配置脚本。")
    # Starting is quick and does not install packages or upgrade existing databases.
    run(
        [
            sys.executable,
            "-B",
            "scripts/runner_image.py",
            "check",
            "--image",
            settings.get("CODE_SANDBOX_IMAGE", TAG),
        ],
        env,
    )
    port = choose_port(int(settings.get("FLASK_PORT", "5001")))
    origins = settings.get("CORS_ORIGINS", "").split(",")
    origins.extend([f"http://127.0.0.1:{port}", f"http://localhost:{port}"])
    env["CORS_ORIGINS"] = ",".join(filter(None, origins))
    url = f"http://127.0.0.1:{port}/"
    print(f"启动地址：{url} ；停止服务请按 Ctrl+C。", flush=True)
    finished = threading.Event()
    if not args.no_browser:
        threading.Thread(target=open_when_ready, args=(url, finished), daemon=True).start()
    try:
        run(
            [
                sys.executable,
                "-B",
                "-m",
                "flask",
                "--app",
                "app",
                "run",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            env,
        )
    finally:
        finished.set()
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n服务已停止。")
        raise SystemExit(0) from None
    except (
        SetupError,
        PrerequisiteError,
        subprocess.SubprocessError,
        OSError,
        ValueError,
        ImportError,
    ) as exc:
        # Never print environment values or keys. Steps can safely be retried.
        if isinstance(exc, (SetupError, PrerequisiteError)):
            message = str(exc)
        elif isinstance(exc, ImportError):
            message = "应用依赖不完整，请重新运行配置脚本完成安装。"
        elif isinstance(exc, subprocess.SubprocessError):
            message = "命令执行失败。请检查上方安装/镜像输出和网络连接；修复后可重新运行同一脚本。"
        else:
            message = "本地文件或配置不可用，请检查文件权限、磁盘空间及配置格式。"
        print("\n未完成：" + message, file=sys.stderr)
        raise SystemExit(1) from None

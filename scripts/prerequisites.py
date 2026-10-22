"""Install missing Docker prerequisites with consent, before app dependencies exist.

Uses only the Python standard library. Installers come from the official HTTPS
endpoints and must pass native publisher verification before execution.
"""

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


class PrerequisiteError(Exception):
    pass


def confirm(message):
    print(message, flush=True)
    if not sys.stdin.isatty():
        raise PrerequisiteError("当前没有交互终端。请直接运行 setup 脚本以确认安装系统软件。")
    if input("继续安装？[y/N] ").strip().lower() not in {"y", "yes"}:
        raise PrerequisiteError("已跳过安装；准备好后可再次运行相同配置脚本。")


def desktop_paths():
    if sys.platform == "win32":
        return [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/DockerDesktop",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker/Docker",
        ]
    if sys.platform == "darwin":
        return [Path("/Applications/Docker.app"), Path.home() / "Applications/Docker.app"]
    return []


def refresh_docker_path():
    """New installers do not update the PATH of the already running launcher."""
    folders = [root / "resources/bin" for root in desktop_paths()]
    if sys.platform == "darwin":
        folders = [root / "Contents/Resources/bin" for root in desktop_paths()]
        folders.append(Path.home() / ".docker/bin")
    existing = os.environ.get("PATH", "").split(os.pathsep)
    for folder in folders:
        if folder.is_dir() and str(folder) not in existing:
            existing.insert(0, str(folder))
    os.environ["PATH"] = os.pathsep.join(existing)


def engine_ready():
    if not shutil.which("docker"):
        return False
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.OSType}}"],
            capture_output=True,
            timeout=10,
        )
        # A running Windows engine is left intact; quickstart explains the required switch.
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def ps_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def powershell(script):
    exe = (
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    return subprocess.run(
        [str(exe), "-NoProfile", "-Command", "$ErrorActionPreference = 'Stop'; " + script],
        check=True,
    )


def wsl_version():
    try:
        version = subprocess.run(["wsl.exe", "--version"], capture_output=True, timeout=20)
        encoding = "utf-16-le" if b"\x00" in version.stdout else "utf-8"
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", version.stdout.decode(encoding, errors="replace"))
        return tuple(map(int, match.groups())) if version.returncode == 0 and match else None
    except (OSError, subprocess.SubprocessError):
        return None


def wsl_ready():
    version = wsl_version()
    if version is None or version < (2, 1, 5):
        return False
    try:
        return (
            subprocess.run(["wsl.exe", "--status"], capture_output=True, timeout=20).returncode == 0
        )
    except (OSError, subprocess.SubprocessError):
        return False


def ensure_wsl():
    if wsl_ready():
        return
    confirm(
        "Docker 需要 WSL 2。将请求 Windows 管理员授权以安装/更新 WSL（不安装 Ubuntu）；可能需要重启。"
    )
    # Existing WSL may only need an update; new machines also need Windows features.
    actions = (
        ["'--update'", "'--install','--no-distribution'"]
        if wsl_version()
        else ["'--install','--no-distribution'", "'--update'"]
    )
    for arguments in actions:
        try:
            powershell(
                "$p = Start-Process -FilePath 'wsl.exe' -Verb RunAs -WindowStyle Hidden "
                f"-Wait -PassThru -ArgumentList {arguments}; exit $p.ExitCode"
            )
        except subprocess.CalledProcessError as exc:
            if exc.returncode in {3010, 1641}:
                raise PrerequisiteError(
                    "WSL 安装需要重启。请重启 Windows 后重新运行 setup-windows.cmd。"
                ) from exc
            raise PrerequisiteError(
                "WSL 安装未完成或授权被取消。请检查系统提示后重试；不会自动重启电脑。"
            ) from exc
        if wsl_ready():
            return
    raise PrerequisiteError(
        "WSL 尚未就绪。请重启 Windows 后重试；仍失败时检查 BIOS/UEFI 虚拟化是否开启。"
    )


def download(url, destination):
    print("正在从 Docker 官网下载安装包，首次下载可能需要数分钟……", flush=True)
    try:
        with urllib.request.urlopen(url, timeout=60) as response, destination.open("wb") as output:
            if not response.url.startswith("https://"):
                raise PrerequisiteError("安装包下载被重定向到非 HTTPS 地址，已停止。")
            total = 0
            last_notice = time.monotonic()
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                total += len(chunk)
                if time.monotonic() - last_notice >= 10:
                    print(f"已下载 {total // (1024 * 1024)} MiB……", flush=True)
                    last_notice = time.monotonic()
    except OSError as exc:
        raise PrerequisiteError(
            "Docker 安装包下载失败。请检查网络、代理和可用磁盘空间，再次运行配置脚本。"
        ) from exc


def docker_architecture():
    machine = platform.machine().lower()
    if sys.platform == "win32":
        machine = os.environ.get(
            "PROCESSOR_ARCHITEW6432", os.environ.get("PROCESSOR_ARCHITECTURE", machine)
        ).lower()
    elif sys.platform == "darwin" and machine == "x86_64":
        # A Python interpreter running under Rosetta must still install native Apple Silicon Docker.
        result = subprocess.run(["sysctl", "-n", "hw.optional.arm64"], capture_output=True)
        if result.returncode == 0 and result.stdout.strip() == b"1":
            machine = "arm64"
    if machine in {"arm64", "aarch64"}:
        return "arm64"
    if machine in {"amd64", "x86_64"}:
        return "amd64"
    raise PrerequisiteError("Docker Desktop 自动安装仅支持 64 位 Intel/AMD 或 ARM 电脑。")


def install_windows_docker(folder):
    ensure_wsl()
    installer = folder / "Docker Desktop Installer.exe"
    download(
        f"https://desktop.docker.com/win/main/{docker_architecture()}/Docker%20Desktop%20Installer.exe",
        installer,
    )
    # Reject unsigned installers and valid signatures belonging to other publishers.
    try:
        powershell(
            f"$s = Get-AuthenticodeSignature -LiteralPath {ps_literal(installer)}; "
            "if ($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch '(?:CN|O)=Docker Inc\\.?[, ]') { exit 1 }"
        )
    except subprocess.CalledProcessError as exc:
        raise PrerequisiteError(
            "Docker 安装包签名或发布者校验失败，未运行安装程序。请重新下载。"
        ) from exc
    result = subprocess.run([str(installer), "install", "--user", "--backend=wsl-2"])
    if result.returncode in {3010, 1641}:
        raise PrerequisiteError("Docker 安装需要重启。请重启后再次运行 setup-windows.cmd。")
    if result.returncode:
        raise PrerequisiteError("Docker Desktop 安装未完成或被取消。请检查安装窗口后重试。")


def install_macos_docker(folder):
    installer = folder / "Docker.dmg"
    mount = folder / "mounted"
    mount.mkdir()
    download(f"https://desktop.docker.com/mac/main/{docker_architecture()}/Docker.dmg", installer)
    subprocess.run(
        ["hdiutil", "attach", str(installer), "-nobrowse", "-readonly", "-mountpoint", str(mount)],
        check=True,
    )
    try:
        app = mount / "Docker.app"
        subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
        signature = subprocess.run(
            ["codesign", "-dv", "--verbose=4", str(app)], capture_output=True, check=True
        )
        if b"TeamIdentifier=9BNSXJN65R" not in signature.stderr.splitlines():
            raise PrerequisiteError("Docker 安装包发布者校验失败，未运行安装程序。")
        print("系统可能要求输入 Mac 登录密码（输入时不显示字符）。", flush=True)
        subprocess.run(["sudo", str(app / "Contents/MacOS/install")], check=True)
    finally:
        subprocess.run(["hdiutil", "detach", str(mount)], check=True)


def start_desktop():
    for root in desktop_paths():
        if sys.platform == "win32" and (root / "Docker Desktop.exe").is_file():
            # The desktop window is needed to complete Docker's first-run setup.
            subprocess.Popen([str(root / "Docker Desktop.exe")])
            return True
        if sys.platform == "darwin" and root.is_dir():
            subprocess.run(["open", str(root)], check=True)
            return True
    return False


def uses_wsl():
    # Preserve an existing explicit Hyper-V configuration; new Windows installs use WSL.
    settings = Path(os.environ.get("APPDATA", "")) / "Docker/settings-store.json"
    try:
        return (
            json.loads(settings.read_text(encoding="utf-8")).get("wslEngineEnabled", True)
            is not False
        )
    except (OSError, ValueError, AttributeError):
        return True


def ensure_docker():
    refresh_docker_path()
    if engine_ready():
        return
    if sys.platform not in {"win32", "darwin"}:
        raise PrerequisiteError("请安装并启动 Docker 的 Linux 容器引擎，再运行配置脚本。")
    installed = any(root.exists() for root in desktop_paths())
    if not installed:
        confirm("未检测到可用的 Docker Desktop。将从 Docker 官网下载安装，并打开首次设置窗口。")
        with tempfile.TemporaryDirectory(prefix="codelab-docker-") as folder:
            if sys.platform == "win32":
                install_windows_docker(Path(folder))
            else:
                install_macos_docker(Path(folder))
    elif sys.platform == "win32" and uses_wsl():
        ensure_wsl()
    refresh_docker_path()
    if not start_desktop():
        raise PrerequisiteError(
            "未找到 Docker Desktop。请确认安装已完成，或手动启动现有 Docker 引擎后重试。"
        )
    print(
        "请在 Docker Desktop 中完成协议确认和系统授权；正在等待 Linux 容器引擎（最多 5 分钟）……",
        flush=True,
    )
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        refresh_docker_path()
        if engine_ready():
            print("Docker 引擎已就绪，继续配置项目。", flush=True)
            return
        time.sleep(3)
    raise PrerequisiteError(
        "Docker 引擎尚未就绪。请完成 Docker 首次设置；Windows 检查 WSL/虚拟化，必要时重启后再运行配置脚本。"
    )

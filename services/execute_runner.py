"""Bounded Docker runner; never falls back to executing on the application host."""

import base64
import os
import selectors
import subprocess
import threading
import time
import uuid

from config import (
    CODE_RUN_CPU_SECONDS,
    CODE_RUN_FILE_SIZE_MB,
    CODE_RUN_MAX_OUTPUT_CHARS,
    CODE_RUN_MAX_PROCESSES,
    CODE_RUN_MEMORY_MB,
    CODE_RUN_TIMEOUT_SECONDS,
    CODE_SANDBOX_IMAGE,
)

_SLOTS = threading.BoundedSemaphore(2)


def _remove_container(name):
    try:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass


def run_code(code: str, language: str = "Python", input_text: str = None) -> dict:
    language = language.lower()
    if language not in {"python", "cpp"}:
        return {"success": False, "status": "Environment Error", "error": "不支持的语言"}
    if not _SLOTS.acquire(blocking=False):
        return {"success": False, "status": "Busy", "error": "执行任务较多，请稍后重试"}
    name = "codelab-run-" + uuid.uuid4().hex
    process = None
    selector = selectors.DefaultSelector()
    buffers = {"output": bytearray(), "error": bytearray()}
    flags = {"output_truncated": False, "error_truncated": False}
    started = time.monotonic()
    status = None
    limit = max(1024, CODE_RUN_MAX_OUTPUT_CHARS)
    memory = max(64, CODE_RUN_MEMORY_MB)
    command = [
        "docker",
        "run",
        "--rm",
        "--pull=never",
        "--name",
        name,
        "--interactive",
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--user=65534:65534",
        "--log-driver=none",
        "--pids-limit",
        str(max(8, CODE_RUN_MAX_PROCESSES)),
        "--cpus=1",
        "--memory",
        f"{memory}m",
        "--memory-swap",
        f"{memory}m",
        "--ulimit",
        f"cpu={max(1, CODE_RUN_CPU_SECONDS)}:{max(1, CODE_RUN_CPU_SECONDS)}",
        "--ulimit",
        f"fsize={max(1, CODE_RUN_FILE_SIZE_MB) * 1024 * 1024}",
        "--tmpfs",
        "/work:rw,exec,nosuid,nodev,size=16m,mode=1777",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777",
        CODE_SANDBOX_IMAGE,
        language,
        base64.b64encode(code.encode()).decode(),
    ]
    try:
        process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        for pipe, key in [(process.stdout, "output"), (process.stderr, "error")]:
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, key)
        pending = memoryview((input_text or "").encode())
        if pending:
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
        else:
            process.stdin.close()
        while selector.get_map():
            if time.monotonic() - started > max(1, CODE_RUN_TIMEOUT_SECONDS):
                status = "Time Limit Exceeded"
                break
            for key, _ in selector.select(timeout=0.1):
                if key.data == "stdin":
                    try:
                        written = os.write(key.fd, pending[:4096])
                        pending = pending[written:]
                    except BrokenPipeError:
                        pending = memoryview(b"")
                    if not pending:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    continue
                chunk = os.read(key.fd, 4096)
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                remaining = limit - len(buffers[key.data])
                buffers[key.data].extend(chunk[:remaining])
                if len(chunk) > remaining:
                    flags[key.data + "_truncated"] = True
                    status = "Output Limit Exceeded"
                    break
            if status:
                break
        if status:
            _remove_container(name)
            process.kill()
        try:
            returncode = process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            status = "Time Limit Exceeded"
            process.kill()
            returncode = process.wait(timeout=2)
        if not status:
            if returncode == 0:
                status = "Accepted"
            elif returncode == 125:
                status = "Environment Error"
            elif returncode == 65 and language == "cpp":
                status = "Compile Error"
            elif returncode in {137, 152}:
                status = "Resource Limit Exceeded"
            else:
                status = "Runtime Error"
        output = buffers["output"].decode("utf-8", errors="replace")
        error = buffers["error"].decode("utf-8", errors="replace")
        if status == "Environment Error":
            error = "隔离执行环境未就绪，请启动 Docker 并构建 codelab-runner:local 镜像"
        elif status == "Time Limit Exceeded":
            error = "代码执行超时，任务已终止"
        elif status == "Output Limit Exceeded":
            error = "输出超过上限，任务已终止"
        elif status == "Resource Limit Exceeded":
            error = "代码超过 CPU 或内存限制，任务已终止"
        if flags["output_truncated"]:
            output += "\n... 输出过长，已截断"
        elapsed = round((time.monotonic() - started) * 1000, 2)
        return {
            "success": status == "Accepted",
            "status": status,
            "output": output,
            "error": error,
            "time": elapsed,
            "compile_time": 0 if language == "python" else None,
            "run_time": None,
            "execution_backend": "docker",
            **flags,
        }
    except (OSError, subprocess.SubprocessError):
        return {
            "success": False,
            "status": "Environment Error",
            "error": "隔离执行服务不可用，请启动 Docker 并检查运行镜像",
        }
    finally:
        selector.close()
        _remove_container(name)
        if process:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=2)
            for pipe in (process.stdin, process.stdout, process.stderr):
                if pipe:
                    pipe.close()
        _SLOTS.release()

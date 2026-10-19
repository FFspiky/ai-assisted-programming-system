"""Bounded Docker runner; never falls back to executing on the application host."""

import json
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
from services.language_support import enabled_language_ids, language_spec, normalize_language

_SLOTS = threading.BoundedSemaphore(2)


def _remove_container(name):
    try:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass


def run_code(code: str, language: str = "Python", input_text: str = None) -> dict:
    language = normalize_language(language)
    if language not in enabled_language_ids():
        return {"success": False, "status": "Environment Error", "error": "不支持的语言"}
    if not _SLOTS.acquire(blocking=False):
        return {"success": False, "status": "Busy", "error": "执行任务较多，请稍后重试"}
    name = "codelab-run-" + uuid.uuid4().hex
    process = None
    workers = []
    buffers = {"output": bytearray(), "error": bytearray()}
    flags = {"output_truncated": False, "error_truncated": False}
    started = time.monotonic()
    status = None
    limit = max(1024, CODE_RUN_MAX_OUTPUT_CHARS)
    memory = max(64, CODE_RUN_MEMORY_MB)
    file_limit = max(1, CODE_RUN_FILE_SIZE_MB) * 1024 * 1024
    compile_file_limit = max(16 * 1024 * 1024, file_limit)
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
        f"fsize={compile_file_limit}:{compile_file_limit}",
        "--tmpfs",
        "/work:rw,exec,nosuid,nodev,size=16m,mode=1777",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777",
        CODE_SANDBOX_IMAGE,
        language,
    ]
    try:
        process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        # Windows select() accepts sockets, not subprocess pipes. Separate readers
        # drain both streams concurrently while retaining only bounded output.
        output_exceeded = threading.Event()
        io_errors = []

        def read_pipe(pipe, key):
            try:
                while chunk := pipe.read1(4096):
                    remaining = limit - len(buffers[key])
                    buffers[key].extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        flags[key + "_truncated"] = True
                        output_exceeded.set()
                        break
            except OSError as exc:
                io_errors.append(exc)

        def write_input():
            try:
                # Source travels over stdin rather than a command argument:
                # Windows limits the whole command line to about 32 KiB.
                payload = json.dumps(
                    {"code": code, "input": input_text or "", "file_size_limit": file_limit},
                    ensure_ascii=False,
                )
                process.stdin.write(payload.encode("utf-8"))
                process.stdin.flush()
            except BrokenPipeError:
                pass  # A submission may exit without consuming its input.
            except OSError as exc:
                io_errors.append(exc)
            finally:
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass

        for pipe, key in [(process.stdout, "output"), (process.stderr, "error")]:
            workers.append(threading.Thread(target=read_pipe, args=(pipe, key), daemon=True))
        workers.append(threading.Thread(target=write_input, daemon=True))
        for worker in workers:
            worker.start()
        while any(worker.is_alive() for worker in workers):
            if output_exceeded.is_set():
                status = "Output Limit Exceeded"
                break
            if io_errors:
                raise io_errors[0]
            if time.monotonic() - started > max(1, CODE_RUN_TIMEOUT_SECONDS):
                status = "Time Limit Exceeded"
                break
            time.sleep(0.01)
        if output_exceeded.is_set():
            status = "Output Limit Exceeded"
        if io_errors and not status:
            raise io_errors[0]
        if status:
            _remove_container(name)
            process.kill()
        try:
            returncode = process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            status = "Time Limit Exceeded"
            process.kill()
            returncode = process.wait(timeout=2)
        for worker in workers:
            worker.join(timeout=2)
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
            "language": language,
            "language_version": language_spec(language)["version"],
            **flags,
        }
    except (OSError, subprocess.SubprocessError):
        return {
            "success": False,
            "status": "Environment Error",
            "error": "隔离执行服务不可用，请启动 Docker 并检查运行镜像",
        }
    finally:
        try:
            _remove_container(name)
            if process:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=2)
                # Retry removal after the CLI exits: an early failure can race
                # with Docker creating the container.
                _remove_container(name)
                for worker in workers:
                    worker.join(timeout=2)
                for pipe in (process.stdin, process.stdout, process.stderr):
                    if pipe:
                        pipe.close()
        finally:
            _SLOTS.release()

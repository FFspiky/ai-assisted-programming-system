import subprocess
import sys
import time
import tempfile
import os
import shutil

from config import (
    CODE_RUN_CPU_SECONDS,
    CODE_RUN_FILE_SIZE_MB,
    CODE_RUN_MAX_OUTPUT_CHARS,
    CODE_RUN_MAX_PROCESSES,
    CODE_RUN_MEMORY_MB,
    CODE_RUN_TIMEOUT_SECONDS,
)


def _truncate_output(text):
    text = text or ""
    if len(text) <= CODE_RUN_MAX_OUTPUT_CHARS:
        return text
    return text[:CODE_RUN_MAX_OUTPUT_CHARS] + "\n... 输出过长，已截断"


def _truncate_output_with_flag(text):
    text = text or ""
    truncated = len(text) > CODE_RUN_MAX_OUTPUT_CHARS
    return _truncate_output(text), truncated


def _limit_child_process():
    try:
        import resource

        cpu_seconds = max(1, CODE_RUN_CPU_SECONDS)
        memory_bytes = max(32, CODE_RUN_MEMORY_MB) * 1024 * 1024
        file_size_bytes = max(1, CODE_RUN_FILE_SIZE_MB) * 1024 * 1024
        max_processes = max(1, CODE_RUN_MAX_PROCESSES)

        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        resource.setrlimit(resource.RLIMIT_FSIZE, (file_size_bytes, file_size_bytes))
        resource.setrlimit(resource.RLIMIT_NPROC, (max_processes, max_processes))
    except Exception:
        pass

# 1. 修改函数签名，增加 input_text 参数
def run_code(code: str, language: str = "Python", input_text: str = None) -> dict:
    tmp_dir = tempfile.mkdtemp(prefix="code-run-")
    try:
        start_time = time.time()
        compile_time = 0
        run_env = {
            "PATH": os.getenv("PATH", ""),
            "PYTHONIOENCODING": "utf-8",
            "LANG": "C.UTF-8",
        }

        if language.lower() == "python":
            run_start = time.time()
            result = subprocess.run(
                [sys.executable, "-I", "-c", code],
                capture_output=True,
                text=True,
                timeout=CODE_RUN_TIMEOUT_SECONDS,
                input=input_text, # 2. 将 input_text 传递给进程
                cwd=tmp_dir,
                env=run_env,
                preexec_fn=_limit_child_process if os.name == "posix" else None,
            )
            run_time = round((time.time() - run_start) * 1000, 2)
        elif language.lower() == "cpp":
            with tempfile.NamedTemporaryFile(mode='w', suffix='.cpp', dir=tmp_dir, delete=False) as f:
                f.write(code)
                file_path = f.name
            output_file = os.path.splitext(file_path)[0]

            # 3. 优化编译命令
            compile_start = time.time()
            compile_result = subprocess.run(
                ["g++", "-std=c++17", file_path, "-o", output_file],
                capture_output=True,
                text=True,
                timeout=CODE_RUN_TIMEOUT_SECONDS,
                cwd=tmp_dir,
                env=run_env,
            )
            compile_time = round((time.time() - compile_start) * 1000, 2)
            if compile_result.returncode != 0:
                error, error_truncated = _truncate_output_with_flag(compile_result.stderr)
                return {
                    "success": False,
                    "status": "Compile Error",
                    "error": error,
                    "error_truncated": error_truncated,
                    "time": compile_time,
                    "compile_time": compile_time,
                    "run_time": 0,
                }

            run_start = time.time()
            result = subprocess.run(
                [output_file],
                capture_output=True,
                text=True,
                timeout=CODE_RUN_TIMEOUT_SECONDS,
                input=input_text, # 2. 将 input_text 传递给进程
                cwd=tmp_dir,
                env=run_env,
                preexec_fn=_limit_child_process if os.name == "posix" else None,
            )
            run_time = round((time.time() - run_start) * 1000, 2)
        else:
            return {
                "success": False,
                "error": f"不支持的语言: {language}（本机演示版本仅支持 Python / C++）"
            }

        elapsed_time = round((time.time() - start_time) * 1000, 2)
        output, output_truncated = _truncate_output_with_flag(result.stdout)
        error, error_truncated = _truncate_output_with_flag(result.stderr)

        return {
            "success": result.returncode == 0,
            "status": "Accepted" if result.returncode == 0 else "Runtime Error",
            "output": output,
            "error": error,
            "time": elapsed_time,
            "compile_time": compile_time,
            "run_time": run_time,
            "output_truncated": output_truncated,
            "error_truncated": error_truncated,
            "memory": "N/A"
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "status": "Time Limit Exceeded",
            "error": f"Execution timed out after {CODE_RUN_TIMEOUT_SECONDS} seconds"
        }
    except FileNotFoundError:
        return {
            "success": False,
            "status": "Environment Error",
            "error": f"未找到执行 {language} 代码所需的命令，请确保已安装相应的编译器或解释器。"
        }
    except Exception as e:
        return {
            "success": False,
            "status": "Runtime Error",
            "error": str(e)
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

# 保留命令行功能
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", required=True)
    parser.add_argument("--language", default="Python")
    args = parser.parse_args()
    
    result = run_code(args.code, args.language)
    print(result)

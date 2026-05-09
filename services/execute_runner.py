import subprocess
import sys
import time
import tempfile
import os
import shutil


def _limit_child_process():
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
    except Exception:
        pass

# 1. 修改函数签名，增加 input_text 参数
def run_code(code: str, language: str = "Python", input_text: str = None) -> dict:
    tmp_dir = tempfile.mkdtemp(prefix="code-run-")
    try:
        start_time = time.time()
        run_env = {
            "PATH": os.getenv("PATH", ""),
            "PYTHONIOENCODING": "utf-8",
            "LANG": "C.UTF-8",
        }

        if language.lower() == "python":
            result = subprocess.run(
                [sys.executable, "-I", "-c", code],
                capture_output=True,
                text=True,
                timeout=10,
                input=input_text, # 2. 将 input_text 传递给进程
                cwd=tmp_dir,
                env=run_env,
                preexec_fn=_limit_child_process if os.name == "posix" else None,
            )
        elif language.lower() == "cpp":
            with tempfile.NamedTemporaryFile(mode='w', suffix='.cpp', dir=tmp_dir, delete=False) as f:
                f.write(code)
                file_path = f.name
            output_file = os.path.splitext(file_path)[0]

            # 3. 优化编译命令
            compile_result = subprocess.run(
                ["g++", "-std=c++17", file_path, "-o", output_file],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=tmp_dir,
                env=run_env,
            )
            if compile_result.returncode != 0:
                return {
                    "success": False,
                    "error": compile_result.stderr
                }

            result = subprocess.run(
                [output_file],
                capture_output=True,
                text=True,
                timeout=10,
                input=input_text, # 2. 将 input_text 传递给进程
                cwd=tmp_dir,
                env=run_env,
                preexec_fn=_limit_child_process if os.name == "posix" else None,
            )
        else:
            return {
                "success": False,
                "error": f"不支持的语言: {language}（本机演示版本仅支持 Python / C++）"
            }

        elapsed_time = round((time.time() - start_time) * 1000, 2)

        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr,
            "time": elapsed_time,
            "memory": "N/A"
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Execution timed out after 10 seconds"
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"未找到执行 {language} 代码所需的命令，请确保已安装相应的编译器或解释器。"
        }
    except Exception as e:
        return {
            "success": False,
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

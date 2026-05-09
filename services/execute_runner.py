import subprocess
import sys
import time
import tempfile
import os

# 1. 修改函数签名，增加 input_text 参数
def run_code(code: str, language: str = "Python", input_text: str = None) -> dict:
    try:
        start_time = time.time()

        if language.lower() == "python":
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=10,
                input=input_text # 2. 将 input_text 传递给进程
            )
        elif language.lower() == "cpp":
            with tempfile.NamedTemporaryFile(mode='w', suffix='.cpp', delete=False) as f:
                f.write(code)
                file_path = f.name
            output_file = os.path.splitext(file_path)[0]

            # 3. 优化编译命令
            compile_result = subprocess.run(
                ["g++", "-std=c++17", file_path, "-o", output_file],
                capture_output=True,
                text=True,
                timeout=10
            )
            if compile_result.returncode != 0:
                os.remove(file_path)
                return {
                    "success": False,
                    "error": compile_result.stderr
                }
            
            result = subprocess.run(
                [output_file],
                capture_output=True,
                text=True,
                timeout=10,
                input=input_text # 2. 将 input_text 传递给进程
            )
            os.remove(file_path)
            os.remove(output_file)
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

# 保留命令行功能
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", required=True)
    parser.add_argument("--language", default="Python")
    args = parser.parse_args()
    
    result = run_code(args.code, args.language)
    print(result)

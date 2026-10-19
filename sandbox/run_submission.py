"""Container entry point. Only source and stdin enter the isolated environment."""

import json
import os
import resource
import subprocess
import sys

language = sys.argv[1]
if language not in {"python", "cpp"}:
    sys.exit(64)
payload = json.load(sys.stdin)
source = payload["code"]


def restore_submission_limits():
    # Compilers need space for object files; student code retains the configured
    # soft AND hard limit, so it cannot subsequently raise its writing allowance.
    # The field was added after the stdin transport; older in-flight servers use
    # the original one-MiB submission limit until they are restarted.
    limit = payload.get("file_size_limit", 1024 * 1024)
    resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))


# Restore submission stdin after the transport envelope is consumed. Source and
# input never need to fit a host command line, and EOF remains deterministic.
with open("/work/stdin.txt", "wb") as f:
    f.write(payload["input"].encode("utf-8"))
with open("/work/stdin.txt", "rb") as f:
    os.dup2(f.fileno(), 0)
if language == "python":
    with open("/work/solution.py", "w", encoding="utf-8") as f:
        f.write(source)
    restore_submission_limits()
    os.execv(sys.executable, [sys.executable, "-I", "/work/solution.py"])
if language == "cpp":
    with open("/work/main.cpp", "w", encoding="utf-8") as f:
        f.write(source)
    result = subprocess.run(["g++", "-std=c++17", "/work/main.cpp", "-o", "/work/main"])
    if result.returncode:
        sys.exit(65)
    restore_submission_limits()
    os.execv("/work/main", ["/work/main"])
sys.exit(64)

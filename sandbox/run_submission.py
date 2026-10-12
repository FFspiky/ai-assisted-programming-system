"""Container entry point. Only source and stdin enter the isolated environment."""

import base64
import os
import subprocess
import sys

language, encoded = sys.argv[1:3]
source = base64.b64decode(encoded).decode("utf-8")
if language == "python":
    os.execv(sys.executable, [sys.executable, "-I", "-c", source])
if language == "cpp":
    with open("/work/main.cpp", "w", encoding="utf-8") as f:
        f.write(source)
    result = subprocess.run(["g++", "-std=c++17", "/work/main.cpp", "-o", "/work/main"])
    if result.returncode:
        sys.exit(65)
    os.execv("/work/main", ["/work/main"])
sys.exit(64)

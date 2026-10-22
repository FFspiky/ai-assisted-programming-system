#!/bin/bash
cd -- "$(dirname -- "$0")/.." || exit 1
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1
runner=""
if [ -x .venv/bin/python ]; then
    runner=.venv/bin/python
else
    for candidate in python3 python3.14 python3.13 python3.12 python3.11; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
            runner="$candidate"
            break
        fi
    done
fi
if [ -z "$runner" ]; then
    printf '%s\n' 'Python 3.11+ was not found. Install Python, then run this script again.'
    result=1
else
    "$runner" -B scripts/quickstart.py "$@"
    result=$?
fi
if [ -t 0 ] && [ "${CODELAB_NO_PAUSE:-0}" != "1" ]; then
    read -r -p 'Press Enter to close this window... ' _
fi
exit "$result"

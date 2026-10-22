#!/bin/bash
cd -- "$(dirname -- "$0")/.." || exit 1
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1
source ./scripts/bootstrap-macos.sh || exit 1
runner=$(codelab_find_python)
skip_install=0
for argument in "$@"; do
    [ "$argument" = '--skip-prerequisites' ] && skip_install=1
done
if [ -z "$runner" ] && [ "$1" = 'setup' ] && [ "$skip_install" = 0 ]; then
    codelab_install_python && runner=$(codelab_find_python)
fi
if [ -z "$runner" ]; then
    printf '%s\n' 'Python 3.11+ was not found. Run setup-macos.command to install it, or install from https://www.python.org/downloads/.'
    result=1
else
    "$runner" -B scripts/quickstart.py "$@"
    result=$?
fi
if [ -t 0 ] && [ "${CODELAB_NO_PAUSE:-0}" != "1" ]; then
    read -r -p 'Press Enter to close this window... ' _
fi
exit "$result"

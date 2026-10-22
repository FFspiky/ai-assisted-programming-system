#!/bin/bash
# Native bootstrap: works before any Python or Homebrew installation exists.
codelab_find_python() {
    local candidate
    for candidate in .venv/bin/python python3 python3.14 python3.13 python3.12 python3.11 \
        /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 \
        /opt/homebrew/bin/python3 /usr/local/bin/python3; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

codelab_confirm_python() {
    if [ ! -t 0 ]; then
        printf '%s\n' 'Python 3.11+ was not found. Run setup interactively to install it.' >&2
        return 1
    fi
    local answer
    read -r -p '未找到 Python 3.11+，是否从 python.org 下载并安装 Python 3.13.17？[y/N] ' answer
    case "$answer" in y|Y|yes|YES) return 0 ;; *) printf '%s\n' '已跳过 Python 安装；准备好后请重新运行配置脚本。' >&2; return 1 ;; esac
}

codelab_install_certificates() {
    /bin/bash '/Applications/Python 3.13/Install Certificates.command'
}

codelab_install_python() (
    codelab_confirm_python || exit 1
    local folder package digest
    if [ "$(uname -s)" != 'Darwin' ]; then
        printf '%s\n' '自动安装仅支持 macOS。' >&2
        exit 1
    fi
    folder=$(mktemp -d "${TMPDIR:-/tmp}/codelab-python.XXXXXX") || exit 1
    package="$folder/python.pkg"
    trap 'rm -f -- "$package"; rmdir -- "$folder"' EXIT
    printf '%s\n' '正在下载 Python 官方安装包（Intel / Apple Silicon 通用）……'
    curl --fail --location --proto '=https' --tlsv1.2 --retry 2 --connect-timeout 20 --max-time 1800 \
        --output "$package" 'https://www.python.org/ftp/python/3.13.17/python-3.13.17-macos11.pkg' || exit 1
    digest=$(shasum -a 256 "$package") || exit 1
    if [ "${digest%% *}" != '3053592af66128269efab37fe7851a4894920b27c442aeec99ce4d34d17c07e3' ]; then
        printf '%s\n' 'Python 安装包校验失败，未安装。请检查网络后重试。' >&2
        exit 1
    fi
    printf '%s\n' '系统可能要求输入 Mac 登录密码（输入时不显示字符）。'
    sudo /usr/sbin/installer -pkg "$package" -target / || exit 1
    # The python.org distribution needs its CA bundle for pip and HTTPS.
    codelab_install_certificates || exit 1
)

"""Private delivery credential format (this module contains no credential)."""

import json
import re


def read_reviewer_key(path):
    try:
        packet = json.loads(path.read_text(encoding="utf-8"))
        key = packet["api_key"]
        if not isinstance(key, str) or not re.fullmatch(r"sk-[A-Za-z0-9_-]{16,200}", key):
            raise ValueError
        if packet.get("budget_cny") != "10.00":
            raise ValueError
        return key
    except (OSError, ValueError, TypeError, KeyError):
        raise ValueError("评审 Key 文件无效，请使用完整提交目录或跳过测试 Key 配置。") from None

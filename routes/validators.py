from flask import jsonify

from config import (
    MAX_AI_PROMPT_CHARS,
    MAX_AUTOCOMPLETE_PREFIX_CHARS,
    MAX_AUTOCOMPLETE_SUFFIX_CHARS,
    MAX_CODE_CHARS,
    MAX_STDIN_CHARS,
    SUPPORTED_LANGUAGES,
)


def normalize_language(language):
    normalized = (language or "python").strip().lower()
    if normalized in {"c++", "cpp"}:
        return "cpp"
    if normalized in {"py", "python3"}:
        return "python"
    return normalized


def validate_language(language):
    normalized = normalize_language(language)
    if normalized not in SUPPORTED_LANGUAGES:
        return None, jsonify({
            "success": False,
            "error": f"不支持的语言: {language}",
        }), 400
    return normalized, None, None


def validate_text_size(value, max_chars, field_name):
    text = "" if value is None else str(value)
    if len(text) > max_chars:
        return None, jsonify({
            "success": False,
            "error": f"{field_name}长度不能超过 {max_chars} 个字符",
        }), 400
    return text, None, None


def validate_code_payload(data):
    language, response, status = validate_language(data.get("language", "python"))
    if response:
        return None, None, None, (response, status)

    code, response, status = validate_text_size(data.get("code", ""), MAX_CODE_CHARS, "代码")
    if response:
        return None, None, None, (response, status)

    input_text, response, status = validate_text_size(data.get("input_text"), MAX_STDIN_CHARS, "标准输入")
    if response:
        return None, None, None, (response, status)

    return code, language, input_text, None


def validate_ai_prompt(value):
    return validate_text_size(value, MAX_AI_PROMPT_CHARS, "消息内容")


def trim_autocomplete_context(prefix, suffix):
    prefix = (prefix or "").strip("\x00")
    suffix = suffix or ""
    return (
        prefix[-MAX_AUTOCOMPLETE_PREFIX_CHARS:],
        suffix[:MAX_AUTOCOMPLETE_SUFFIX_CHARS],
    )

from config import (
    MAX_AI_PROMPT_CHARS,
    MAX_AUTOCOMPLETE_PREFIX_CHARS,
    MAX_AUTOCOMPLETE_SUFFIX_CHARS,
    MAX_CODE_CHARS,
    MAX_STDIN_CHARS,
    SUPPORTED_LANGUAGES,
)
from routes.api_response import api_error
from services.language_support import LANGUAGE_IDS, normalize_language


def validate_language(language):
    normalized = normalize_language(language)
    if normalized not in SUPPORTED_LANGUAGES or normalized not in LANGUAGE_IDS:
        response, status = api_error(
            "UNSUPPORTED_LANGUAGE",
            f"不支持的语言: {language}",
        )
        return None, response, status
    return normalized, None, None


def validate_text_size(value, max_chars, field_name):
    if value is not None and not isinstance(value, str):
        response, status = api_error("INVALID_FIELD", f"{field_name}必须是字符串")
        return None, response, status
    text = value or ""
    if len(text) > max_chars:
        response, status = api_error(
            "PAYLOAD_TOO_LARGE",
            f"{field_name}长度不能超过 {max_chars} 个字符",
        )
        return None, response, status
    return text, None, None


def validate_code_payload(data):
    if not isinstance(data, dict):
        return None, None, None, api_error("INVALID_JSON", "请求必须是 JSON 对象")
    language, response, status = validate_language(data.get("language", "python"))
    if response:
        return None, None, None, (response, status)

    code, response, status = validate_text_size(data.get("code", ""), MAX_CODE_CHARS, "代码")
    if response:
        return None, None, None, (response, status)

    input_text, response, status = validate_text_size(
        data.get("input_text"), MAX_STDIN_CHARS, "标准输入"
    )
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

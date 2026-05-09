import json
import re

from config import MODEL_NAME
from services.ai_client import AIClientError, chat_completion


def _extract_json_object(text: str) -> dict | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None


def _normalize_structured_response(data: dict) -> dict | None:
    if not isinstance(data, dict):
        return None

    feedback = data.get("feedback") or data.get("overall_feedback") or ""
    versions = data.get("optimizedVersions") or data.get("optimized_versions") or []
    normalized_versions = []

    if isinstance(versions, list):
        for item in versions[:5]:
            if not isinstance(item, dict):
                continue
            description = str(item.get("description") or item.get("title") or "").strip()
            code = str(item.get("code") or "").strip()
            if description or code:
                normalized_versions.append({"description": description, "code": code})

    if not feedback and not normalized_versions:
        return None

    if not normalized_versions:
        normalized_versions.append({
            "description": "AI已提供反馈，但未返回可应用的优化代码版本。",
            "code": "",
        })

    return {
        "success": True,
        "feedback": str(feedback).strip(),
        "optimizedVersions": normalized_versions,
    }


def _parse_legacy_markdown(ai_response_content: str) -> dict:
    overall_feedback = ai_response_content.strip()
    optimized_versions = []
    code_block_pattern = re.compile(r"```[a-zA-Z0-9_+-]*\s*([\s\S]*?)```")

    for index, match in enumerate(code_block_pattern.finditer(ai_response_content), 1):
        code = match.group(1).strip()
        if not code:
            continue

        preceding_text = ai_response_content[:match.start()].strip().splitlines()
        description = f"优化版本 {index}"
        for line in reversed(preceding_text[-5:]):
            clean_line = re.sub(r"^#+\s*", "", line).strip()
            if clean_line:
                description = clean_line
                break

        optimized_versions.append({
            "description": description,
            "code": code,
        })

    if not optimized_versions:
        optimized_versions.append({
            "description": "AI已提供反馈，但未能解析到具体优化代码版本。",
            "code": "",
        })

    return {
        "success": True,
        "feedback": overall_feedback,
        "optimizedVersions": optimized_versions,
    }


def parse_ai_code_response(ai_response_content: str) -> dict:
    structured = _extract_json_object(ai_response_content)
    normalized = _normalize_structured_response(structured) if structured else None
    if normalized:
        return normalized
    return _parse_legacy_markdown(ai_response_content)


def check_code(code: str, language: str):
    full_prompt = f"""
你是一位经验丰富的编程助教，请分析并优化以下 {language} 代码。

请只返回一个 JSON 对象，不要 Markdown，不要代码围栏，不要解释 JSON 之外的内容。
JSON 结构必须是：
{{
  "feedback": "对错误、风险、风格和整体评价的中文总结",
  "optimizedVersions": [
    {{"description": "版本1的优化点", "code": "完整代码"}},
    {{"description": "版本2的优化点", "code": "完整代码"}},
    {{"description": "版本3的优化点", "code": "完整代码"}}
  ]
}}

要求：
1. optimizedVersions 至少返回 3 个版本。
2. 即使原代码存在错误，也要给出可运行的优化版本。
3. code 字段只放源代码文本，不要放 Markdown 代码围栏。

待分析代码：
{code}
"""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "你是一名擅长教学和编程指导的助理，必须按用户要求输出 JSON。"},
            {"role": "user", "content": full_prompt},
        ],
        "temperature": 0.3,
    }

    try:
        ai_response_content = chat_completion(payload, timeout=120)
        return parse_ai_code_response(ai_response_content)
    except AIClientError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"AI响应解析失败: {str(e)}"}

import json
import logging

import requests
from flask import g, has_request_context
from flask_login import current_user

from config import AI_THINKING_MODE, API_KEY, API_URL

logger = logging.getLogger(__name__)


class AIClientError(Exception):
    pass


def ensure_ai_configured():
    if has_request_context():
        if getattr(g, "ai_api_key", None):
            return g.ai_api_key
        from services.ai_settings import resolve_key

        key = resolve_key(current_user.id) if current_user.is_authenticated else ""
        if not key:
            raise AIClientError("未配置 API Key，请前往个人资料页配置")
        return key
    if not API_KEY:
        raise AIClientError("未配置 DEEPSEEK_API_KEY（可在 .env 或环境变量中设置）")
    return API_KEY


def _provider_payload(payload):
    prepared = dict(payload)
    enabled = prepared.pop("enable_thinking", None)
    mode = AI_THINKING_MODE if enabled is None else ("enabled" if enabled else "disabled")
    prepared.setdefault("thinking", {"type": mode})
    return prepared


def chat_completion(payload, timeout=120, metadata=None):
    key = ensure_ai_configured()
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    try:
        with requests.post(
            API_URL, headers=headers, json=_provider_payload(payload), timeout=timeout
        ) as response:
            response.raise_for_status()
            packet = response.json()
            content = packet["choices"][0]["message"]["content"]
            if metadata is not None and isinstance(packet.get("model"), str):
                metadata["response_model"] = packet["model"]
        if not isinstance(content, str) or not content.strip():
            raise AIClientError("AI未返回有效文本，请重试")
        return content
    except requests.exceptions.Timeout as exc:
        raise AIClientError("AI服务响应超时") from exc
    except requests.exceptions.RequestException as exc:
        raise AIClientError(f"AI服务请求失败: {exc}") from exc
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise AIClientError(f"AI响应格式异常: {exc}") from exc


def stream_chat_events(payload, timeout=120):
    """Keep provider reasoning separate from the assistant's visible answer."""
    key = ensure_ai_configured()
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    stream_payload = {**_provider_payload(payload), "stream": True}

    try:
        with requests.post(
            API_URL,
            headers=headers,
            json=stream_payload,
            stream=True,
            timeout=timeout,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines(chunk_size=1):
                if not line or not line.startswith(b"data:"):
                    continue
                raw = line[5:].decode("utf-8").strip()
                if raw.strip() == "[DONE]":
                    break
                try:
                    packet = json.loads(raw)
                    if packet.get("error"):
                        raise AIClientError("模型服务返回错误，请稍后重试")
                    choices = packet.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                except (
                    json.JSONDecodeError,
                    KeyError,
                    IndexError,
                    TypeError,
                    AttributeError,
                ) as exc:
                    logger.debug("Skipping malformed AI stream chunk: %s", exc)
                    continue
                for field, kind in (("reasoning_content", "reasoning"), ("content", "content")):
                    value = delta.get(field)
                    if isinstance(value, str) and value:
                        yield {"type": kind, "text": value}
    except requests.exceptions.Timeout as exc:
        raise AIClientError("AI服务响应超时") from exc
    except requests.exceptions.RequestException as exc:
        raise AIClientError(f"AI服务请求失败: {exc}") from exc


def stream_chat_deltas(payload, timeout=120):
    for event in stream_chat_events(payload, timeout=timeout):
        if event["type"] == "content":
            yield event["text"]

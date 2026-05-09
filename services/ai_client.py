import json
import logging

import requests

from config import API_KEY, API_URL


logger = logging.getLogger(__name__)


class AIClientError(Exception):
    pass


def ensure_ai_configured():
    if not API_KEY:
        raise AIClientError("未配置 SILICONFLOW_API_KEY（可在 .env 或环境变量中设置）")


def chat_completion(payload, timeout=120):
    ensure_ai_configured()
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout as exc:
        raise AIClientError("AI服务响应超时") from exc
    except requests.exceptions.RequestException as exc:
        raise AIClientError(f"AI服务请求失败: {exc}") from exc
    except (KeyError, IndexError, ValueError) as exc:
        raise AIClientError(f"AI响应格式异常: {exc}") from exc


def stream_chat_deltas(payload, timeout=120):
    ensure_ai_configured()
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    stream_payload = {**payload, "stream": True}

    try:
        with requests.post(
            API_URL,
            headers=headers,
            json=stream_payload,
            stream=True,
            timeout=timeout,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith(b"data: "):
                    continue
                raw = line[6:].decode("utf-8")
                if raw.strip() == "[DONE]":
                    break
                try:
                    delta = json.loads(raw)["choices"][0]["delta"].get("content", "")
                except (json.JSONDecodeError, KeyError, IndexError) as exc:
                    logger.debug("Skipping malformed AI stream chunk: %s", exc)
                    continue
                if delta:
                    yield delta
    except requests.exceptions.Timeout as exc:
        raise AIClientError("AI服务响应超时") from exc
    except requests.exceptions.RequestException as exc:
        raise AIClientError(f"AI服务请求失败: {exc}") from exc

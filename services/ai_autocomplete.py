import json
import requests
from config import API_KEY, API_URL, AUTOCOMPLETE_MODEL_NAME


def stream_inline_completion(prefix: str, suffix: str, language: str, max_tokens: int = 128):
    if not API_KEY:
        yield "【AI未配置】：缺少 SILICONFLOW_API_KEY（可在 .env 或环境变量中设置）"
        return

    system_prompt = (
        "你是代码补全引擎。只输出要插入到光标处的文本，不要解释，不要Markdown，不要代码围栏，"
        "不要输出思考过程或任何分析。"
    )
    user_prompt = f"""
语言：{language}

要求：
1. 仅输出应插入到光标处的补全文本，不要重复已有内容。
2. 最多输出 8 行。
3. 不确定时输出空字符串。

光标前内容：
{prefix}

光标后内容：
{suffix}
"""

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": AUTOCOMPLETE_MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "enable_thinking": False,
        "stream": True,
    }

    try:
        with requests.post(API_URL, headers=headers, json=payload, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            in_think = False
            for line in resp.iter_lines():
                if line and line.startswith(b"data: "):
                    raw = line[6:].decode("utf-8")
                    if raw.strip() == "[DONE]":
                        break
                    delta = json.loads(raw)["choices"][0]["delta"].get("content", "")
                    if not delta:
                        continue
                    # 过滤模型可能返回的 <think>...</think> 思考内容
                    output = ""
                    i = 0
                    while i < len(delta):
                        if delta.startswith("<think>", i):
                            in_think = True
                            i += len("<think>")
                            continue
                        if delta.startswith("</think>", i):
                            in_think = False
                            i += len("</think>")
                            continue
                        if not in_think:
                            output += delta[i]
                        i += 1
                    if output:
                        yield output
    except Exception as e:
        yield f"\n【补全失败】：{str(e)}"

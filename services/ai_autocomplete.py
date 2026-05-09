from config import AUTOCOMPLETE_MODEL_NAME
from services.ai_client import AIClientError, stream_chat_deltas


def stream_inline_completion(prefix: str, suffix: str, language: str, max_tokens: int = 128):
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

    payload = {
        "model": AUTOCOMPLETE_MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "enable_thinking": False,
    }

    try:
        in_think = False
        for delta in stream_chat_deltas(payload, timeout=60):
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
    except AIClientError as e:
        yield f"\n【补全失败】：{str(e)}"

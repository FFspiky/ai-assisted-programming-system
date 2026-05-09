from config import MODEL_NAME
from services.ai_client import AIClientError, stream_chat_deltas


def stream_code_from_prompt(prompt: str, language: str) -> str:
    full_prompt = f"""
你是一个经验丰富的编程助手，擅长使用 {language} 语言，并能帮助用户解答各种编程相关的问题，包括但不限于：

- 代码编写与调试
- 算法实现与优化
- 错误分析与解决方案
- 性能分析与提升建议
- 编程风格与最佳实践
- 库函数使用与框架指导

【用户问题】：{prompt}

请根据问题内容，使用中文给出详细解答，必要时附上完整的代码示例。代码需使用 Markdown 格式（例如 ```{language.lower()}```），并添加适当注释，帮助用户理解关键部分。

回答应具备以下特点：
1. 逻辑清晰，分点列出重要信息；
2. 语言简洁明了，适合初中级开发者阅读；
3. 如果问题模糊或信息不足，请合理假设并说明你的推理过程；
4. 若有多种解决方案，请进行比较分析，指出各自的优缺点与适用场景。
"""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": f"你是一名擅长教学和编程指导的助理，善于用清晰中文解释复杂问题"},
            {"role": "user", "content": full_prompt}
        ],
        "temperature": 0.4,
    }

    try:
        yield from stream_chat_deltas(payload, timeout=120)
    except AIClientError as e:
        yield f"\n【流式输出失败】：{str(e)}"

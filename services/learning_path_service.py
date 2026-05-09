# services/learning_path_service.py
import requests
import json
import logging
from config import API_KEY, API_URL, MODEL_NAME


logger = logging.getLogger(__name__)

def _stream_ai_for_path(prompt: str): # 改为流式函数
    """
    一个私有辅助函数，专门用于为学习路径功能流式调用AI模型。
    """
    if not API_KEY:
        error_message = {"error": "未配置 SILICONFLOW_API_KEY（可在 .env 或环境变量中设置）"}
        yield f"data: {json.dumps(error_message, ensure_ascii=False)}\n\n"
        return

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "你是一名擅长教学和规划的助理，善于用清晰中文解释复杂问题"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4,
        "stream": True # <-- 关键：开启流式响应
    }

    try:
        # 使用 with requests.post(...) 来确保连接被正确关闭
        with requests.post(API_URL, headers=headers, json=payload, stream=True, timeout=300) as resp:
            resp.raise_for_status()
            # 迭代处理返回的每一行数据
            for line in resp.iter_lines():
                if line and line.startswith(b"data: "):
                    raw = line[6:].decode("utf-8")
                    if raw.strip() == "[DONE]":
                        break
                    delta = json.loads(raw)["choices"][0]["delta"].get("content", "")
                    if delta:
                        # --- 修改开始 ---
                        # 将原始文本包装成带 'content' 键的 JSON 对象，并格式化为 SSE
                        message = {"content": delta}
                        # SSE 格式要求以 "data: " 开头，并以两个换行符结尾
                        yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
                        # --- 修改结束 ---
    except Exception as e:
        logger.exception("Error calling AI service")
        # --- 修改开始 ---
        # 同样将错误信息包装成 SSE 事件
        error_message = {"error": f"AI服务调用失败：{str(e)}"}
        yield f"data: {json.dumps(error_message, ensure_ascii=False)}\n\n"
        # --- 修改结束 ---


def generate_learning_path(answers: list): # 这个函数现在也变成一个生成器
    """
    构建提示词并流式生成学习路径。
    """
    # prompt 的构建逻辑保持不变
    prompt = f"""
    基于用户提供的编程能力评估结果，请生成一个详细的分阶段学习路径计划...
    """ # (省略完整的prompt内容)

    # 使用 yield from 将子生成器的内容直接返回
    yield from _stream_ai_for_path(prompt)

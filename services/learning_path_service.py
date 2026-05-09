# services/learning_path_service.py
import json
import logging
from config import MODEL_NAME
from services.ai_client import AIClientError, stream_chat_deltas


logger = logging.getLogger(__name__)


def _stream_ai_for_path(prompt: str): # 改为流式函数
    """
    一个私有辅助函数，专门用于为学习路径功能流式调用AI模型。
    """
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "你是一名擅长教学和规划的助理，善于用清晰中文解释复杂问题"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4,
    }

    try:
        for delta in stream_chat_deltas(payload, timeout=300):
            message = {"content": delta}
            yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
    except AIClientError as e:
        logger.exception("Error calling AI service")
        error_message = {"error": f"AI服务调用失败：{str(e)}"}
        yield f"data: {json.dumps(error_message, ensure_ascii=False)}\n\n"


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

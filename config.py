import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    # 本机演示不强依赖 python-dotenv；没有也可以通过系统环境变量配置
    pass


API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
API_URL = os.getenv("SILICONFLOW_API_URL", "https://api.siliconflow.cn/v1/chat/completions")
MODEL_NAME = os.getenv("SILICONFLOW_MODEL_NAME", "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B")
AUTOCOMPLETE_MODEL_NAME = os.getenv("SILICONFLOW_AUTOCOMPLETE_MODEL_NAME", "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B")

# 管理员账号
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://127.0.0.1:5001,http://localhost:5001").split(",")
    if origin.strip()
]

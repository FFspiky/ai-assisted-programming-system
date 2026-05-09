import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    # 本机演示不强依赖 python-dotenv；没有也可以通过系统环境变量配置
    pass


API_KEY = os.getenv("SILICONFLOW_API_KEY", "sk-gzehcnyqccwtrzlvgyhbomtxuyxkxaornkrrfhjidsrbkykt")
API_URL = os.getenv("SILICONFLOW_API_URL", "https://api.siliconflow.cn/v1/chat/completions")
MODEL_NAME = os.getenv("SILICONFLOW_MODEL_NAME", "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B")
AUTOCOMPLETE_MODEL_NAME = os.getenv("SILICONFLOW_AUTOCOMPLETE_MODEL_NAME", "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B")

# 管理员账号
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "123456"
ADMIN_EMAIL = "admin@example.com"

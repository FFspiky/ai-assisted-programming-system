import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    # 本机演示不强依赖 python-dotenv；没有也可以通过系统环境变量配置
    pass


def _int_env(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


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

SUPPORTED_LANGUAGES = {
    item.strip().lower()
    for item in os.getenv("SUPPORTED_LANGUAGES", "python,cpp").split(",")
    if item.strip()
}

MAX_CODE_CHARS = _int_env("MAX_CODE_CHARS", 20000)
MAX_STDIN_CHARS = _int_env("MAX_STDIN_CHARS", 10000)
MAX_AI_PROMPT_CHARS = _int_env("MAX_AI_PROMPT_CHARS", 8000)
MAX_AUTOCOMPLETE_PREFIX_CHARS = _int_env("MAX_AUTOCOMPLETE_PREFIX_CHARS", 2000)
MAX_AUTOCOMPLETE_SUFFIX_CHARS = _int_env("MAX_AUTOCOMPLETE_SUFFIX_CHARS", 800)

CODE_RUN_TIMEOUT_SECONDS = _int_env("CODE_RUN_TIMEOUT_SECONDS", 10)
CODE_RUN_CPU_SECONDS = _int_env("CODE_RUN_CPU_SECONDS", 3)
CODE_RUN_MEMORY_MB = _int_env("CODE_RUN_MEMORY_MB", 256)
CODE_RUN_FILE_SIZE_MB = _int_env("CODE_RUN_FILE_SIZE_MB", 1)
CODE_RUN_MAX_PROCESSES = _int_env("CODE_RUN_MAX_PROCESSES", 32)
CODE_RUN_MAX_OUTPUT_CHARS = _int_env("CODE_RUN_MAX_OUTPUT_CHARS", 20000)
RATE_LIMIT_REDIS_URL = os.getenv("RATE_LIMIT_REDIS_URL") or os.getenv("REDIS_URL", "")

try:
    JUDGE_FLOAT_TOLERANCE = float(os.getenv("JUDGE_FLOAT_TOLERANCE", "1e-6"))
except (TypeError, ValueError):
    JUDGE_FLOAT_TOLERANCE = 1e-6

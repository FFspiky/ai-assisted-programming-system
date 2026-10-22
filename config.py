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


API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
REVIEWER_TEST_KEY_ENABLED = os.getenv("REVIEWER_TEST_KEY_ENABLED", "0") == "1"
# Only the official DeepSeek endpoint is supported; no provider URL override.
API_URL = "https://api.deepseek.com/chat/completions"
MODEL_NAME = os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-flash")
AUTOCOMPLETE_MODEL_NAME = os.getenv("DEEPSEEK_AUTOCOMPLETE_MODEL_NAME", "deepseek-flash")
AI_THINKING_MODE = os.getenv("AI_THINKING_MODE", "disabled")

# 管理员账号
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://127.0.0.1:5001,http://localhost:5001").split(
        ","
    )
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

CODE_SANDBOX_IMAGE = os.getenv("CODE_SANDBOX_IMAGE", "codelab-runner:local")

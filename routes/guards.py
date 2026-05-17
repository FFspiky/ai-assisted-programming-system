from functools import wraps

from flask import jsonify, request
from flask_login import current_user
from services.rate_limiter import _MEMORY_BUCKETS as _RATE_BUCKETS
from services.rate_limiter import allow_request


def rate_limit(max_calls: int, window_seconds: int):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if request.method == "OPTIONS":
                return f(*args, **kwargs)

            user_key = current_user.get_id() if current_user.is_authenticated else request.remote_addr
            key = f"{f.__module__}.{f.__name__}:{user_key or 'anonymous'}"
            if not allow_request(key, max_calls, window_seconds):
                return jsonify({
                    "success": False,
                    "error": "请求过于频繁，请稍后再试",
                }), 429

            return f(*args, **kwargs)

        return wrapped

    return decorator

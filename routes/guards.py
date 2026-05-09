import time
from collections import defaultdict
from functools import wraps

from flask import jsonify, request
from flask_login import current_user


_RATE_BUCKETS = defaultdict(list)


def rate_limit(max_calls: int, window_seconds: int):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if request.method == "OPTIONS":
                return f(*args, **kwargs)

            user_key = current_user.get_id() if current_user.is_authenticated else request.remote_addr
            key = f"{f.__module__}.{f.__name__}:{user_key or 'anonymous'}"
            now = time.time()
            calls = [
                timestamp
                for timestamp in _RATE_BUCKETS[key]
                if now - timestamp < window_seconds
            ]
            if len(calls) >= max_calls:
                _RATE_BUCKETS[key] = calls
                return jsonify({
                    "success": False,
                    "error": "请求过于频繁，请稍后再试",
                }), 429

            calls.append(now)
            _RATE_BUCKETS[key] = calls
            return f(*args, **kwargs)

        return wrapped

    return decorator

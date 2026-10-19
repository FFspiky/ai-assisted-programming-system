import logging
import threading
import time
import uuid
from collections import defaultdict

from config import RATE_LIMIT_REDIS_URL

logger = logging.getLogger(__name__)


_MEMORY_BUCKETS = defaultdict(list)
_MEMORY_LOCK = threading.Lock()
_REDIS_CLIENT = None
_REDIS_DISABLED = False


def _get_redis_client():
    global _REDIS_CLIENT, _REDIS_DISABLED
    if _REDIS_DISABLED or not RATE_LIMIT_REDIS_URL:
        return None
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT

    try:
        import redis

        client = redis.Redis.from_url(RATE_LIMIT_REDIS_URL, decode_responses=True)
        client.ping()
        _REDIS_CLIENT = client
        return _REDIS_CLIENT
    except Exception as exc:
        logger.warning("Redis rate limiter unavailable, falling back to memory: %s", exc)
        _REDIS_DISABLED = True
        return None


def _allow_with_memory(key: str, max_calls: int, window_seconds: int, now: float) -> bool:
    with _MEMORY_LOCK:
        calls = [
            timestamp for timestamp in _MEMORY_BUCKETS[key] if now - timestamp < window_seconds
        ]
        if len(calls) >= max_calls:
            _MEMORY_BUCKETS[key] = calls
            return False

        calls.append(now)
        _MEMORY_BUCKETS[key] = calls
        return True


def _allow_with_redis(client, key: str, max_calls: int, window_seconds: int, now: float) -> bool:
    script = """
    redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1] - ARGV[2])
    if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[3]) then
        return 0
    end
    redis.call('ZADD', KEYS[1], ARGV[1], ARGV[4])
    redis.call('EXPIRE', KEYS[1], ARGV[2])
    return 1
    """
    return bool(
        client.eval(
            script, 1, f"rate-limit:{key}", now, window_seconds, max_calls, uuid.uuid4().hex
        )
    )


def allow_request(key: str, max_calls: int, window_seconds: int) -> bool:
    now = time.time()
    client = _get_redis_client()
    if client is None:
        return _allow_with_memory(key, max_calls, window_seconds, now)

    try:
        return _allow_with_redis(client, key, max_calls, window_seconds, now)
    except Exception as exc:
        logger.warning("Redis rate limit check failed, falling back to memory: %s", exc)
        return _allow_with_memory(key, max_calls, window_seconds, now)


def reset_limit(key: str) -> None:
    client = _get_redis_client()
    if client is not None:
        try:
            client.delete(f"rate-limit:{key}")
        except Exception as exc:
            logger.warning("Redis rate limit reset failed: %s", exc)
    with _MEMORY_LOCK:
        _MEMORY_BUCKETS.pop(key, None)


def clear_memory_limits() -> None:
    with _MEMORY_LOCK:
        _MEMORY_BUCKETS.clear()

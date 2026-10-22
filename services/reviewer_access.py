"""Check the dedicated reviewer account without logging or returning its credential."""

import secrets
from decimal import Decimal, InvalidOperation

import requests
from flask import g, has_request_context

from config import REVIEWER_TEST_KEY_ENABLED

BALANCE_URL = "https://api.deepseek.com/user/balance"
EXHAUSTED = (
    "共享评审测试额度已用尽或余额不足，请在个人资料 → AI 服务配置中填写自己的 DeepSeek Key。"
)


class ReviewerAccessError(Exception):
    def __init__(self, message, code="REVIEWER_BALANCE_UNAVAILABLE", status=503):
        super().__init__(message)
        self.code = code
        self.status = status


def is_reviewer_key(key):
    from services.ai_client import API_KEY

    return bool(
        REVIEWER_TEST_KEY_ENABLED and API_KEY and key and secrets.compare_digest(key, API_KEY)
    )


def provider_error(status):
    if status == 402:
        return ReviewerAccessError(EXHAUSTED, "REVIEWER_BALANCE_EXHAUSTED", 402)
    if status in {401, 403}:
        return ReviewerAccessError(
            "评审测试 Key 已失效或无权访问，请在个人资料 → AI 服务配置中填写自己的 DeepSeek Key。",
            "REVIEWER_KEY_INVALID",
            503,
        )
    if status == 429:
        return ReviewerAccessError(
            "评审测试账户请求过于频繁，请稍后再试。", "REVIEWER_RATE_LIMIT", 429
        )
    return ReviewerAccessError("DeepSeek 服务暂不可用，请稍后再试。")


def check_balance(key):
    try:
        with requests.get(
            BALANCE_URL,
            headers={"Authorization": f"Bearer {key}"},
            timeout=(5, 10),
            allow_redirects=False,
        ) as response:
            if response.status_code != 200:
                raise provider_error(response.status_code)
            packet = response.json()
        if not isinstance(packet, dict) or type(packet.get("is_available")) is not bool:
            raise ValueError("invalid availability")
        if not packet["is_available"]:
            raise provider_error(402)
        balances = packet["balance_infos"]
        if not isinstance(balances, list):
            raise ValueError("invalid balances")
        amounts = [Decimal(item["total_balance"]) for item in balances if item["currency"] == "CNY"]
        if len(amounts) != 1 or not amounts[0].is_finite():
            raise ValueError("missing or invalid CNY balance")
        if amounts[0] <= 0:
            raise provider_error(402)
        return amounts[0]
    except requests.RequestException:
        raise ReviewerAccessError(
            "无法查询评审测试余额，请检查网络后重试；本次未调用模型。"
        ) from None
    except (ValueError, TypeError, KeyError, InvalidOperation):
        raise ReviewerAccessError("评审余额查询返回异常，本次未调用模型，请稍后重试。") from None


def preflight(key):
    """Allow HTTP errors before a streaming response starts; permit only its first call."""
    if is_reviewer_key(key):
        check_balance(key)
        g.reviewer_checked_key = key


def before_completion(key):
    if not is_reviewer_key(key):
        return
    # Consume, never cache: a second model call in the same request checks again.
    checked = g.pop("reviewer_checked_key", None) if has_request_context() else None
    if checked != key:
        check_balance(key)

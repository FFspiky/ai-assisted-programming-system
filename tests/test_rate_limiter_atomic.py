"""Quota reservations must not admit competing requests beyond the same limit."""

import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

from services import rate_limiter


class AtomicRateLimiterTest(unittest.TestCase):
    def tearDown(self):
        rate_limiter.clear_memory_limits()

    def test_concurrent_memory_requests_reserve_exactly_one_slot(self):
        barrier = threading.Barrier(16)

        def request(_):
            barrier.wait()
            return rate_limiter._allow_with_memory("concurrent", 1, 60, 100)

        with ThreadPoolExecutor(max_workers=16) as pool:
            self.assertEqual(sum(pool.map(request, range(16))), 1)
        self.assertFalse(rate_limiter._allow_with_memory("concurrent", 1, 60, 159))
        self.assertTrue(rate_limiter._allow_with_memory("concurrent", 1, 60, 160))

    def test_redis_reserves_in_one_atomic_script_and_honors_result(self):
        client = Mock()
        client.eval.side_effect = [1, 0]
        self.assertTrue(rate_limiter._allow_with_redis(client, "key", 1, 60, 100))
        self.assertFalse(rate_limiter._allow_with_redis(client, "key", 1, 60, 100))
        self.assertEqual(client.eval.call_count, 2)
        client.pipeline.assert_not_called()
        first, second = [call.args for call in client.eval.call_args_list]
        self.assertEqual(first[1:6], (1, "rate-limit:key", 100, 60, 1))
        self.assertNotEqual(first[-1], second[-1])
        for operation in ("ZREMRANGEBYSCORE", "ZCARD", "ZADD", "EXPIRE"):
            self.assertIn(operation, first[0])

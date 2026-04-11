"""Tests for logger, concurrency limiter, and error mapping."""
import asyncio
import json
import sys
from io import StringIO
from unittest.mock import patch

import pytest

from dsers_mcp_product.logger import log, _emit, _current_level, VALID_LEVELS
from dsers_mcp_product.concurrency import p_limit
from dsers_mcp_product.error_map import format_error_for_agent


# ── Logger ──

class TestLogger:
    def test_info_emits_json_to_stderr(self):
        buf = StringIO()
        with patch.object(sys, "stderr", buf):
            _emit("info", "hello", {"key": 1})
        line = buf.getvalue().strip()
        record = json.loads(line)
        assert record["level"] == "info"
        assert record["msg"] == "hello"
        assert record["ctx"]["key"] == 1
        assert "time" in record

    def test_debug_suppressed_at_default_level(self):
        buf = StringIO()
        with patch.object(sys, "stderr", buf), patch.dict("os.environ", {"LOG_LEVEL": ""}, clear=False):
            import dsers_mcp_product.logger as mod
            mod._cached_level = None  # reset cache
            _emit("debug", "should not appear")
        assert buf.getvalue() == ""

    def test_error_always_emitted(self):
        buf = StringIO()
        with patch.object(sys, "stderr", buf):
            _emit("error", "crash")
        assert "crash" in buf.getvalue()


# ── Concurrency limiter ──

class TestPLimit:
    def test_limits_concurrency(self):
        async def run():
            active = 0
            max_active = 0
            results = []

            async def task(i):
                nonlocal active, max_active
                active += 1
                max_active = max(max_active, active)
                await asyncio.sleep(0.01)
                active -= 1
                return i

            limit = p_limit(3)
            results = await asyncio.gather(*[limit(lambda i=i: task(i)) for i in range(10)])
            return sorted(results), max_active

        results, max_active = asyncio.run(run())
        assert results == list(range(10))
        assert max_active <= 3


# ── Error mapping ──

class TestErrorMap:
    def test_known_reason_maps(self):
        msg = format_error_for_agent("SELLER_NOT_FOUND: product 12345")
        assert "Product not found" in msg

    def test_unknown_error_sanitized(self):
        msg = format_error_for_agent("token=abc123secret something failed")
        assert "abc123secret" not in msg
        assert "REDACTED" in msg

    def test_truncation(self):
        long_msg = "x" * 1000
        result = format_error_for_agent(long_msg)
        assert len(result) <= 510  # "Error: " prefix + 500 chars

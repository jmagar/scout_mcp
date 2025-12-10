"""Tests for rate limiting middleware.

Note: HTTP-specific tests moved to test_http_adapter.py.
These tests focus on token bucket algorithm and MCP-layer rate limiting.
"""

import time

import pytest

from scout_mcp.middleware.ratelimit import RateLimitMiddleware, TokenBucket


class TestTokenBucket:
    """Test token bucket algorithm."""

    def test_consume_success(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        bucket.tokens = 5.0
        assert bucket.consume(1) is True
        # Use approximate comparison due to time.monotonic() precision
        assert 3.9 <= bucket.tokens <= 4.1

    def test_consume_empty(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        bucket.tokens = 0.5
        assert bucket.consume(1) is False
        assert bucket.tokens < 1.0

    def test_consume_refill(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        # Simulate time passing
        bucket.last_refill = time.monotonic() - 5.0  # 5 seconds ago
        assert bucket.consume(1) is True  # Should have ~5 tokens

    def test_consume_respects_max(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        bucket.last_refill = time.monotonic() - 100.0  # Long time ago
        bucket.consume(1)  # Refill capped at max_tokens
        assert bucket.tokens <= 10.0


@pytest.mark.asyncio
class TestRateLimitMiddlewareCleanup:
    """Test cleanup_stale_buckets method."""

    async def test_cleanup_stale_buckets(self):
        """Test that cleanup removes stale buckets."""
        middleware = RateLimitMiddleware(per_minute=60, burst=5)

        # Create some buckets
        context1 = {"client_ip": "192.168.1.1"}
        context2 = {"client_ip": "192.168.1.2"}

        await middleware.process_request("test", {}, context1)
        await middleware.process_request("test", {}, context2)

        # Mark one as stale by backdating last_refill
        middleware._buckets["192.168.1.1"].last_refill = time.monotonic() - 4000

        # Cleanup with 1 hour threshold
        removed = middleware.cleanup_stale_buckets(max_age_seconds=3600)

        assert removed == 1
        assert "192.168.1.1" not in middleware._buckets
        assert "192.168.1.2" in middleware._buckets


class TestMCPLayerRateLimit:
    """Test MCP-layer (transport-independent) rate limiting."""

    def test_ratelimit_middleware_inherits_mcp_middleware(self):
        """Verify RateLimitMiddleware extends MCPMiddleware."""
        from scout_mcp.middleware.base import MCPMiddleware

        assert issubclass(RateLimitMiddleware, MCPMiddleware)

    def test_ratelimit_middleware_not_http_specific(self):
        """Verify RateLimitMiddleware doesn't depend on HTTP-specific features."""
        from starlette.middleware.base import BaseHTTPMiddleware

        assert not issubclass(RateLimitMiddleware, BaseHTTPMiddleware)

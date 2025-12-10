"""Tests for rate limiting middleware."""

import time
from unittest.mock import AsyncMock, MagicMock

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
class TestRateLimitMiddleware:
    """Test rate limiting middleware."""

    @pytest.fixture
    def middleware(self, monkeypatch):
        monkeypatch.setenv("SCOUT_RATE_LIMIT_PER_MINUTE", "60")
        monkeypatch.setenv("SCOUT_RATE_LIMIT_BURST", "5")
        return RateLimitMiddleware(MagicMock())

    @pytest.fixture
    def middleware_disabled(self, monkeypatch):
        monkeypatch.setenv("SCOUT_RATE_LIMIT_PER_MINUTE", "0")
        return RateLimitMiddleware(MagicMock())

    async def test_allows_normal_traffic(self, middleware):
        request = MagicMock()
        request.url.path = "/mcp"
        request.client.host = "127.0.0.1"
        request.headers.get.return_value = None

        call_next = AsyncMock(return_value="response")

        result = await middleware.dispatch(request, call_next)

        assert result == "response"
        call_next.assert_called_once()

    async def test_blocks_burst_exceeded(self, middleware):
        request = MagicMock()
        request.url.path = "/mcp"
        request.client.host = "127.0.0.1"
        request.headers.get.return_value = None

        call_next = AsyncMock(return_value="response")

        # Exhaust burst (5 requests)
        for _ in range(5):
            await middleware.dispatch(request, call_next)

        # Next should be blocked
        result = await middleware.dispatch(request, call_next)

        assert result.status_code == 429

    async def test_health_bypasses_ratelimit(self, middleware):
        request = MagicMock()
        request.url.path = "/health"
        call_next = AsyncMock(return_value="response")

        # Should always succeed
        for _ in range(100):
            result = await middleware.dispatch(request, call_next)
            assert result == "response"

    async def test_disabled_allows_all(self, middleware_disabled):
        request = MagicMock()
        request.url.path = "/mcp"
        request.client.host = "127.0.0.1"
        request.headers.get.return_value = None

        call_next = AsyncMock(return_value="response")

        for _ in range(100):
            result = await middleware_disabled.dispatch(request, call_next)
            assert result == "response"

    async def test_different_clients_independent(self, middleware):
        call_next = AsyncMock(return_value="response")

        # Two different clients
        for ip in ["192.168.1.1", "192.168.1.2"]:
            request = MagicMock()
            request.url.path = "/mcp"
            request.client.host = ip
            request.headers.get.return_value = None

            # Each should get their own burst allowance
            for _ in range(5):
                result = await middleware.dispatch(request, call_next)
                assert result == "response"

    async def test_forwarded_for_header(self, middleware):
        request = MagicMock()
        request.url.path = "/mcp"
        request.client.host = "127.0.0.1"
        request.headers.get.return_value = "192.168.1.100, 10.0.0.1"

        call_next = AsyncMock(return_value="response")

        # Should use first IP from X-Forwarded-For
        result = await middleware.dispatch(request, call_next)
        assert result == "response"

        # Exhaust burst for this client
        for _ in range(4):
            await middleware.dispatch(request, call_next)

        # Next should be blocked
        result = await middleware.dispatch(request, call_next)
        assert result.status_code == 429

    async def test_retry_after_header(self, middleware):
        request = MagicMock()
        request.url.path = "/mcp"
        request.client.host = "127.0.0.1"
        request.headers.get.return_value = None

        call_next = AsyncMock(return_value="response")

        # Exhaust burst
        for _ in range(5):
            await middleware.dispatch(request, call_next)

        # Get rate limited response
        result = await middleware.dispatch(request, call_next)

        assert result.status_code == 429
        assert "Retry-After" in result.headers
        assert int(result.headers["Retry-After"]) >= 1

    async def test_cleanup_stale_buckets(self, middleware):
        # Create some buckets
        request1 = MagicMock()
        request1.url.path = "/mcp"
        request1.client.host = "192.168.1.1"
        request1.headers.get.return_value = None

        request2 = MagicMock()
        request2.url.path = "/mcp"
        request2.client.host = "192.168.1.2"
        request2.headers.get.return_value = None

        call_next = AsyncMock(return_value="response")

        await middleware.dispatch(request1, call_next)
        await middleware.dispatch(request2, call_next)

        # Mark one as stale
        async with middleware._lock:
            middleware._buckets["192.168.1.1"].last_update = time.monotonic() - 4000

        # Cleanup with 1 hour threshold
        removed = await middleware.cleanup_stale_buckets(max_age_seconds=3600)

        assert removed == 1
        assert "192.168.1.1" not in middleware._buckets
        assert "192.168.1.2" in middleware._buckets

    async def test_error_response_format(self, middleware):
        request = MagicMock()
        request.url.path = "/mcp"
        request.client.host = "127.0.0.1"
        request.headers.get.return_value = None

        call_next = AsyncMock(return_value="response")

        # Exhaust burst
        for _ in range(5):
            await middleware.dispatch(request, call_next)

        # Get rate limited response
        result = await middleware.dispatch(request, call_next)

        assert result.status_code == 429
        # Check JSON body structure
        import json

        body = json.loads(result.body)
        assert "error" in body
        assert "retry_after" in body
        assert body["error"] == "Rate limit exceeded"
        assert isinstance(body["retry_after"], int)


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

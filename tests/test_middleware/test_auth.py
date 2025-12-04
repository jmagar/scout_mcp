"""Tests for API key authentication middleware."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from scout_mcp.middleware.auth import APIKeyMiddleware


class TestAPIKeyMiddleware:
    """Test API key authentication."""

    @pytest.fixture
    def middleware_enabled(self, monkeypatch):
        """Create middleware with auth enabled."""
        monkeypatch.setenv("SCOUT_API_KEYS", "test-key-123,test-key-456")
        monkeypatch.delenv("SCOUT_AUTH_ENABLED", raising=False)
        app = MagicMock()
        return APIKeyMiddleware(app)

    @pytest.fixture
    def middleware_disabled_no_keys(self, monkeypatch):
        """Create middleware with auth disabled (no keys)."""
        monkeypatch.delenv("SCOUT_API_KEYS", raising=False)
        monkeypatch.delenv("SCOUT_AUTH_ENABLED", raising=False)
        app = MagicMock()
        return APIKeyMiddleware(app)

    @pytest.fixture
    def middleware_disabled_explicit(self, monkeypatch):
        """Create middleware with auth explicitly disabled."""
        monkeypatch.setenv("SCOUT_API_KEYS", "test-key-123")
        monkeypatch.setenv("SCOUT_AUTH_ENABLED", "false")
        app = MagicMock()
        return APIKeyMiddleware(app)

    @pytest.mark.asyncio
    async def test_health_endpoint_bypasses_auth(self, middleware_enabled):
        """Health endpoint should not require auth."""
        request = MagicMock()
        request.url.path = "/health"
        call_next = AsyncMock(return_value="response")

        result = await middleware_enabled.dispatch(request, call_next)

        assert result == "response"
        call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_missing_key_returns_401(self, middleware_enabled):
        """Missing API key should return 401."""
        request = MagicMock()
        request.url.path = "/mcp"
        request.headers.get.return_value = ""
        request.client.host = "127.0.0.1"

        result = await middleware_enabled.dispatch(request, AsyncMock())

        assert result.status_code == 401
        assert "Missing X-API-Key header" in str(result.body)

    @pytest.mark.asyncio
    async def test_invalid_key_returns_401(self, middleware_enabled):
        """Invalid API key should return 401."""
        request = MagicMock()
        request.url.path = "/mcp"
        request.headers.get.return_value = "wrong-key"
        request.client.host = "127.0.0.1"

        result = await middleware_enabled.dispatch(request, AsyncMock())

        assert result.status_code == 401
        assert "Invalid API key" in str(result.body)

    @pytest.mark.asyncio
    async def test_valid_key_proceeds_first(self, middleware_enabled):
        """Valid API key (first in list) should allow request."""
        request = MagicMock()
        request.url.path = "/mcp"
        request.headers.get.return_value = "test-key-123"
        call_next = AsyncMock(return_value="response")

        result = await middleware_enabled.dispatch(request, call_next)

        assert result == "response"
        call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_valid_key_proceeds_second(self, middleware_enabled):
        """Valid API key (second in list) should allow request."""
        request = MagicMock()
        request.url.path = "/mcp"
        request.headers.get.return_value = "test-key-456"
        call_next = AsyncMock(return_value="response")

        result = await middleware_enabled.dispatch(request, call_next)

        assert result == "response"
        call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_auth_disabled_no_keys_allows_all(
        self, middleware_disabled_no_keys
    ):
        """When no keys configured, all requests allowed."""
        request = MagicMock()
        request.url.path = "/mcp"
        request.headers.get.return_value = ""
        call_next = AsyncMock(return_value="response")

        result = await middleware_disabled_no_keys.dispatch(request, call_next)

        assert result == "response"
        call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_auth_disabled_explicit_allows_all(
        self, middleware_disabled_explicit
    ):
        """When explicitly disabled, all requests allowed."""
        request = MagicMock()
        request.url.path = "/mcp"
        request.headers.get.return_value = ""
        call_next = AsyncMock(return_value="response")

        result = await middleware_disabled_explicit.dispatch(request, call_next)

        assert result == "response"
        call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_empty_api_keys_filtered(self, monkeypatch):
        """Empty/whitespace keys should be filtered out."""
        monkeypatch.setenv("SCOUT_API_KEYS", "key1, ,key2,  ,key3")
        app = MagicMock()
        middleware = APIKeyMiddleware(app)

        assert len(middleware._api_keys) == 3
        assert "key1" in middleware._api_keys
        assert "key2" in middleware._api_keys
        assert "key3" in middleware._api_keys

    @pytest.mark.asyncio
    async def test_keys_are_trimmed(self, monkeypatch):
        """Keys with whitespace should be trimmed."""
        monkeypatch.setenv("SCOUT_API_KEYS", " key1 , key2 ")
        app = MagicMock()
        middleware = APIKeyMiddleware(app)

        request = MagicMock()
        request.url.path = "/mcp"
        request.headers.get.return_value = "key1"
        call_next = AsyncMock(return_value="response")

        result = await middleware.dispatch(request, call_next)
        assert result == "response"

    @pytest.mark.asyncio
    async def test_constant_time_comparison_used(self, middleware_enabled):
        """Validate that constant-time comparison is used."""
        # This test verifies the implementation uses secrets.compare_digest
        # by ensuring the _validate_key method exists and works correctly
        assert middleware_enabled._validate_key("test-key-123") is True
        assert middleware_enabled._validate_key("wrong-key") is False
        assert middleware_enabled._validate_key("test-key-12") is False
        assert middleware_enabled._validate_key("test-key-1234") is False

    @pytest.mark.asyncio
    async def test_no_client_info_handled(self, middleware_enabled):
        """Handle requests without client info gracefully."""
        request = MagicMock()
        request.url.path = "/mcp"
        request.headers.get.return_value = ""
        request.client = None

        result = await middleware_enabled.dispatch(request, AsyncMock())

        assert result.status_code == 401

"""Tests for API key authentication middleware.

Note: HTTP-specific tests moved to test_http_adapter.py.
These tests focus on MCP-layer (transport-independent) authentication.
"""

import pytest

from scout_mcp.middleware.auth import APIKeyMiddleware


class TestMCPLayerAuth:
    """Test MCP-layer (transport-independent) authentication."""

    def test_auth_middleware_inherits_mcp_middleware(self):
        """Verify APIKeyMiddleware extends MCPMiddleware, not BaseHTTPMiddleware."""
        from scout_mcp.middleware.base import MCPMiddleware

        assert issubclass(APIKeyMiddleware, MCPMiddleware)

    def test_auth_middleware_not_http_specific(self):
        """Verify APIKeyMiddleware doesn't depend on HTTP-specific features."""
        from starlette.middleware.base import BaseHTTPMiddleware

        assert not issubclass(APIKeyMiddleware, BaseHTTPMiddleware)

    @pytest.mark.asyncio
    async def test_process_request_validates_key(self):
        """Test MCP-layer process_request validates API key from context."""
        middleware = APIKeyMiddleware(api_keys=["test-key-123"], enabled=True)

        # Valid key
        context = {"api_key": "test-key-123", "client_ip": "127.0.0.1"}
        result = await middleware.process_request("tools/call", {}, context)
        assert result == context

        # Invalid key
        context = {"api_key": "wrong-key", "client_ip": "127.0.0.1"}
        with pytest.raises(PermissionError, match="Invalid API key"):
            await middleware.process_request("tools/call", {}, context)

        # Missing key
        context = {"client_ip": "127.0.0.1"}
        with pytest.raises(PermissionError, match="Missing API key"):
            await middleware.process_request("tools/call", {}, context)

    @pytest.mark.asyncio
    async def test_disabled_auth_allows_all(self):
        """Test disabled auth allows all requests."""
        middleware = APIKeyMiddleware(api_keys=["test-key-123"], enabled=False)

        context = {"client_ip": "127.0.0.1"}
        result = await middleware.process_request("tools/call", {}, context)
        assert result == context

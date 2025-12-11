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


class TestAPIKeyLoggingSecurity:
    """Test that API keys are never logged in plaintext.

    OWASP A07:2021 - Identification and Authentication Failures
    """

    @pytest.mark.asyncio
    async def test_invalid_key_not_logged_plaintext(self, caplog):
        """Invalid API keys must NOT appear in log messages."""
        import logging

        secret_key = "super-secret-api-key-12345"
        middleware = APIKeyMiddleware(api_keys=["valid-key"], enabled=True)

        with caplog.at_level(logging.WARNING):
            context = {"api_key": secret_key, "client_ip": "192.168.1.100"}
            with pytest.raises(PermissionError):
                await middleware.process_request("tools/call", {}, context)

        # The secret key must NOT appear anywhere in logs
        log_output = caplog.text
        assert secret_key not in log_output, (
            f"API key '{secret_key}' was logged in plaintext! "
            f"Log output: {log_output}"
        )

    @pytest.mark.asyncio
    async def test_invalid_key_logs_hash_instead(self, caplog):
        """Invalid API key attempts should log a hash for debugging."""
        import hashlib
        import logging

        secret_key = "another-secret-key-67890"
        expected_hash = hashlib.sha256(secret_key.encode()).hexdigest()[:8]
        middleware = APIKeyMiddleware(api_keys=["valid-key"], enabled=True)

        with caplog.at_level(logging.WARNING):
            context = {"api_key": secret_key, "client_ip": "10.0.0.1"}
            with pytest.raises(PermissionError):
                await middleware.process_request("tools/call", {}, context)

        # Hash should appear in logs for debugging
        log_output = caplog.text
        assert expected_hash in log_output, (
            f"Expected hash '{expected_hash}' not found in logs. "
            f"Log output: {log_output}"
        )

    @pytest.mark.asyncio
    async def test_valid_key_not_logged(self, caplog):
        """Valid API keys should not be logged at all."""
        import logging

        valid_key = "my-valid-api-key-99999"
        middleware = APIKeyMiddleware(api_keys=[valid_key], enabled=True)

        with caplog.at_level(logging.DEBUG):
            context = {"api_key": valid_key, "client_ip": "127.0.0.1"}
            await middleware.process_request("tools/call", {}, context)

        # Valid key must not appear in logs
        log_output = caplog.text
        assert valid_key not in log_output, (
            f"Valid API key '{valid_key}' was logged! "
            f"Log output: {log_output}"
        )

    @pytest.mark.asyncio
    async def test_client_ip_logged_on_invalid_attempt(self, caplog):
        """Client IP should be logged for invalid key attempts (for auditing)."""
        import logging

        client_ip = "203.0.113.42"
        middleware = APIKeyMiddleware(api_keys=["valid-key"], enabled=True)

        with caplog.at_level(logging.WARNING):
            context = {"api_key": "bad-key", "client_ip": client_ip}
            with pytest.raises(PermissionError):
                await middleware.process_request("tools/call", {}, context)

        # Client IP should be logged for security auditing
        assert client_ip in caplog.text, (
            f"Client IP '{client_ip}' not found in security log"
        )

    def test_hash_key_for_logging_function_exists(self):
        """Verify _hash_key_for_logging helper function exists."""
        from scout_mcp.middleware.auth import _hash_key_for_logging

        # Should return 8-character hash
        result = _hash_key_for_logging("test-key")
        assert isinstance(result, str)
        assert len(result) == 8

    def test_hash_key_for_logging_is_deterministic(self):
        """Same key should produce same hash."""
        from scout_mcp.middleware.auth import _hash_key_for_logging

        key = "my-secret-key"
        hash1 = _hash_key_for_logging(key)
        hash2 = _hash_key_for_logging(key)
        assert hash1 == hash2

    def test_hash_key_for_logging_different_keys_different_hashes(self):
        """Different keys should produce different hashes."""
        from scout_mcp.middleware.auth import _hash_key_for_logging

        hash1 = _hash_key_for_logging("key-one")
        hash2 = _hash_key_for_logging("key-two")
        assert hash1 != hash2

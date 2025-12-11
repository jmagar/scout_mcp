"""API key authentication middleware for MCP requests.

Works at MCP layer (transport-independent).
"""
import hashlib
import logging
import secrets
from typing import Any

from scout_mcp.middleware.base import MCPMiddleware

logger = logging.getLogger(__name__)


def _hash_key_for_logging(key: str) -> str:
    """Hash an API key for safe logging.

    Returns first 8 characters of SHA-256 hash.
    This allows identifying failed attempts without exposing the key.

    Args:
        key: The API key to hash

    Returns:
        8-character hex string hash
    """
    return hashlib.sha256(key.encode()).hexdigest()[:8]


class APIKeyMiddleware(MCPMiddleware):
    """MCP-layer API key authentication.

    Validates API keys from transport-specific context.
    Uses constant-time comparison to prevent timing attacks.
    """

    def __init__(self, api_keys: list[str], enabled: bool = True):
        """Initialize auth middleware.

        Args:
            api_keys: List of valid API keys
            enabled: Whether to enforce authentication
        """
        self.api_keys = api_keys
        self.enabled = enabled

    async def process_request(
        self,
        method: str,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate API key from context."""
        if not self.enabled or not self.api_keys:
            return context

        # Extract API key from context
        api_key = context.get("api_key")

        if not api_key:
            raise PermissionError("Missing API key")

        if not self._validate_key(api_key):
            logger.warning(
                "Invalid API key attempt (hash: %s) from %s",
                _hash_key_for_logging(api_key),
                context.get("client_ip", "unknown"),
            )
            raise PermissionError("Invalid API key")

        return context

    def _validate_key(self, provided_key: str) -> bool:
        """Validate key using constant-time comparison."""
        for valid_key in self.api_keys:
            if secrets.compare_digest(provided_key, valid_key):
                return True
        return False

"""API key authentication middleware for Scout MCP."""

import logging
import os
import secrets
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """ASGI middleware for API key authentication.

    Requires X-API-Key header with valid key from SCOUT_API_KEYS env var.

    Environment Variables:
        SCOUT_API_KEYS: Comma-separated list of valid API keys
        SCOUT_AUTH_ENABLED: Set to "false" to disable auth (default: true if keys set)
    """

    def __init__(self, app: Any) -> None:
        """Initialize API key middleware.

        Args:
            app: The ASGI application to wrap.
        """
        super().__init__(app)
        self._api_keys: set[str] = set()
        self._auth_enabled = False
        self._load_keys()

    def _load_keys(self) -> None:
        """Load API keys from environment."""
        keys_str = os.getenv("SCOUT_API_KEYS", "").strip()
        auth_enabled = os.getenv("SCOUT_AUTH_ENABLED", "").lower()

        if keys_str:
            self._api_keys = {k.strip() for k in keys_str.split(",") if k.strip()}
            self._auth_enabled = auth_enabled != "false"

            if self._auth_enabled:
                logger.info(
                    "API key authentication enabled (%d key(s) configured)",
                    len(self._api_keys),
                )
            else:
                logger.warning(
                    "API key authentication DISABLED via SCOUT_AUTH_ENABLED=false"
                )
        else:
            self._auth_enabled = False
            logger.warning(
                "No API keys configured (SCOUT_API_KEYS not set). "
                "Authentication disabled - server is open to all requests!"
            )

    def _validate_key(self, provided_key: str) -> bool:
        """Validate API key using constant-time comparison.

        Args:
            provided_key: The API key to validate.

        Returns:
            True if the key is valid, False otherwise.
        """
        for valid_key in self._api_keys:
            if secrets.compare_digest(provided_key, valid_key):
                return True
        return False

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Validate API key before processing request.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or handler in the chain.

        Returns:
            The HTTP response from the next handler or a 401 error.
        """
        # Skip health checks
        if request.url.path == "/health":
            response: Response = await call_next(request)
            return response

        # Skip if auth disabled
        if not self._auth_enabled:
            response = await call_next(request)
            return response

        # Get API key from header
        api_key = request.headers.get("X-API-Key", "")

        if not api_key:
            logger.warning(
                "Request rejected: missing X-API-Key header from %s",
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                {"error": "Missing X-API-Key header"},
                status_code=401,
            )

        if not self._validate_key(api_key):
            logger.warning(
                "Request rejected: invalid API key from %s",
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                {"error": "Invalid API key"},
                status_code=401,
            )

        # Key valid - proceed
        logger.debug("API key validated for request to %s", request.url.path)
        response = await call_next(request)
        return response

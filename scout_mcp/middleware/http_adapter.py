"""HTTP transport adapter for MCP middleware.

Bridges HTTP-specific middleware (Starlette) with MCP-layer middleware.
Extracts HTTP context (client IP, headers) and makes available to MCP middleware.
"""
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from scout_mcp.middleware.base import MCPMiddleware
from scout_mcp.middleware.ratelimit import RateLimitError


class HTTPMiddlewareAdapter(BaseHTTPMiddleware):
    """Adapter to run MCP middleware in HTTP transport.

    Extracts HTTP-specific context (client IP, headers) and passes
    to MCP-layer middleware.
    """

    def __init__(self, app: Any, mcp_middleware: MCPMiddleware):
        super().__init__(app)
        self.mcp_middleware = mcp_middleware

    async def dispatch(
        self,
        request: Request,
        call_next: Any,
    ) -> Response:
        """Extract HTTP context and delegate to MCP middleware.

        Health check endpoint bypasses all middleware for monitoring.
        """
        # Skip middleware for health checks
        if request.url.path == "/health":
            return await call_next(request)

        # Build context from HTTP request
        context = {
            "client_ip": self._get_client_ip(request),
            "api_key": request.headers.get("X-API-Key"),
            "headers": dict(request.headers),
            "method": request.method,
            "path": request.url.path,
        }

        try:
            # Let MCP middleware process (may raise exception)
            await self.mcp_middleware.process_request(
                method="http",  # Simplified for HTTP transport
                params={},
                context=context,
            )

            # Continue to handler
            response = await call_next(request)

            return response

        except RateLimitError as e:
            # Rate limit error with structured retry_after
            retry_after_seconds = int(e.retry_after) + 1

            return JSONResponse(
                status_code=429,
                content={"error": str(e)},
                headers={"Retry-After": str(retry_after_seconds)},
            )

        except PermissionError as e:
            # Auth error (no retry)
            return JSONResponse(
                status_code=401,
                content={"error": str(e)},
            )

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Check X-Forwarded-For header first (if behind proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"

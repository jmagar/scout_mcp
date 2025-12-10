"""HTTP transport adapter for MCP middleware.

Bridges HTTP-specific middleware (Starlette) with MCP-layer middleware.
Extracts HTTP context (client IP, headers) and makes available to MCP middleware.
"""
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from scout_mcp.middleware.base import MCPMiddleware


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
        """Extract HTTP context and delegate to MCP middleware."""
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

        except PermissionError as e:
            # Rate limit or auth error
            error_msg = str(e)

            # Extract retry_after from error message if present
            retry_after_seconds = None
            if "Retry after" in error_msg:
                try:
                    # Extract the float value from "Retry after X.X seconds."
                    parts = error_msg.split("after ")[1].split(" ")
                    retry_after_seconds = int(float(parts[0])) + 1
                except (IndexError, ValueError):
                    retry_after_seconds = 1

            headers = {}
            if retry_after_seconds:
                headers["Retry-After"] = str(retry_after_seconds)

            return JSONResponse(
                status_code=429 if "Rate limit" in error_msg else 401,
                content={"error": error_msg},
                headers=headers,
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

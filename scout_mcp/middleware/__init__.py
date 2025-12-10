"""Scout MCP middleware components."""

from scout_mcp.middleware.auth import APIKeyMiddleware
from scout_mcp.middleware.base import MCPMiddleware, ScoutMiddleware
from scout_mcp.middleware.errors import ErrorHandlingMiddleware
from scout_mcp.middleware.http_adapter import HTTPMiddlewareAdapter
from scout_mcp.middleware.logging import LoggingMiddleware
from scout_mcp.middleware.ratelimit import (
    RateLimitError,
    RateLimitMiddleware,
    TokenBucket,
)
from scout_mcp.middleware.timing import DetailedTimingMiddleware, TimingMiddleware

__all__ = [
    "APIKeyMiddleware",
    "DetailedTimingMiddleware",
    "ErrorHandlingMiddleware",
    "HTTPMiddlewareAdapter",
    "LoggingMiddleware",
    "MCPMiddleware",
    "RateLimitError",
    "RateLimitMiddleware",
    "ScoutMiddleware",
    "TimingMiddleware",
    "TokenBucket",
]

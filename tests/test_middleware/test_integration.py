"""Integration tests for middleware with the server."""

from scout_mcp.middleware import (
    LoggingMiddleware,
    TimingMiddleware,
)
from scout_mcp.server import configure_middleware, mcp


def test_configure_middleware_adds_all_middleware() -> None:
    """configure_middleware adds timing, logging, and error middleware."""
    # Reset middleware stack
    mcp.middleware.clear()

    configure_middleware(mcp)

    # Should have 3 middleware
    assert len(mcp.middleware) == 3


def test_configure_middleware_order() -> None:
    """Middleware is added in correct order (error -> timing -> logging)."""
    mcp.middleware.clear()

    configure_middleware(mcp)

    # Order: ErrorHandling first (runs last on way in, first on way out)
    # Then Timing, then Logging (logs at outermost layer)
    middleware_types = [type(m).__name__ for m in mcp.middleware]

    # Error handling should be innermost (added first)
    assert middleware_types[0] == "ErrorHandlingMiddleware"
    assert middleware_types[1] == "TimingMiddleware"
    assert middleware_types[2] == "LoggingMiddleware"


def test_configure_middleware_respects_env_vars(monkeypatch) -> None:
    """Middleware configuration respects environment variables."""
    monkeypatch.setenv("SCOUT_LOG_PAYLOADS", "true")
    monkeypatch.setenv("SCOUT_SLOW_THRESHOLD_MS", "500")

    mcp.middleware.clear()

    configure_middleware(mcp)

    # Find logging middleware and check config
    logging_mw = next(m for m in mcp.middleware if isinstance(m, LoggingMiddleware))
    assert logging_mw.include_payloads is True

    timing_mw = next(m for m in mcp.middleware if isinstance(m, TimingMiddleware))
    assert timing_mw.slow_threshold_ms == 500.0

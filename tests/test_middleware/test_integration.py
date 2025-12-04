"""Integration tests for middleware with the server."""

from scout_mcp.middleware import LoggingMiddleware
from scout_mcp.server import configure_middleware, mcp


def test_configure_middleware_adds_all_middleware() -> None:
    """configure_middleware adds logging and error middleware."""
    # Reset middleware stack
    mcp.middleware.clear()

    configure_middleware(mcp)

    # Should have 2 middleware (ErrorHandling + Logging with integrated timing)
    assert len(mcp.middleware) == 2


def test_configure_middleware_order() -> None:
    """Middleware is added in correct order (error -> logging)."""
    mcp.middleware.clear()

    configure_middleware(mcp)

    # Order: ErrorHandling first (runs last on way in, first on way out)
    # Then Logging (logs at outermost layer, includes timing)
    middleware_types = [type(m).__name__ for m in mcp.middleware]

    # Error handling should be innermost (added first)
    assert middleware_types[0] == "ErrorHandlingMiddleware"
    assert middleware_types[1] == "LoggingMiddleware"


def test_configure_middleware_respects_env_vars(monkeypatch) -> None:
    """Middleware configuration respects environment variables."""
    monkeypatch.setenv("SCOUT_LOG_PAYLOADS", "true")
    monkeypatch.setenv("SCOUT_SLOW_THRESHOLD_MS", "500")

    mcp.middleware.clear()

    configure_middleware(mcp)

    # Find logging middleware and check config
    logging_mw = next(m for m in mcp.middleware if isinstance(m, LoggingMiddleware))
    assert logging_mw.include_payloads is True
    # LoggingMiddleware now has integrated timing
    assert logging_mw.slow_threshold_ms == 500.0

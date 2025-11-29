"""Tests for middleware base classes."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from scout_mcp.middleware.base import ScoutMiddleware


class ConcreteMiddleware(ScoutMiddleware):
    """Concrete implementation for testing."""

    async def on_message(self, context, call_next):
        return await call_next(context)


def test_scout_middleware_has_logger() -> None:
    """ScoutMiddleware provides a logger attribute."""
    middleware = ConcreteMiddleware()
    assert hasattr(middleware, "logger")
    assert middleware.logger is not None


def test_scout_middleware_accepts_custom_logger() -> None:
    """ScoutMiddleware accepts custom logger."""
    custom_logger = MagicMock()
    middleware = ConcreteMiddleware(logger=custom_logger)
    assert middleware.logger is custom_logger

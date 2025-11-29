"""Tests for timing middleware."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from scout_mcp.middleware.timing import TimingMiddleware


@pytest.fixture
def timing_middleware() -> TimingMiddleware:
    """Create a timing middleware instance."""
    return TimingMiddleware()


@pytest.fixture
def mock_context() -> MagicMock:
    """Create a mock middleware context."""
    context = MagicMock()
    context.method = "tools/call"
    context.message = MagicMock()
    context.message.name = "scout"
    return context


@pytest.mark.asyncio
async def test_timing_middleware_measures_duration(
    timing_middleware: TimingMiddleware,
    mock_context: MagicMock,
) -> None:
    """TimingMiddleware measures request duration."""
    call_next = AsyncMock(return_value="result")

    result = await timing_middleware.on_request(mock_context, call_next)

    assert result == "result"
    call_next.assert_called_once_with(mock_context)


@pytest.mark.asyncio
async def test_timing_middleware_logs_duration(
    mock_context: MagicMock,
) -> None:
    """TimingMiddleware logs timing information."""
    mock_logger = MagicMock()
    middleware = TimingMiddleware(logger=mock_logger)
    call_next = AsyncMock(return_value="result")

    await middleware.on_request(mock_context, call_next)

    # Should have logged with timing info
    mock_logger.info.assert_called_once()
    log_call = mock_logger.info.call_args
    assert "tools/call" in str(log_call)


@pytest.mark.asyncio
async def test_timing_middleware_handles_exceptions(
    timing_middleware: TimingMiddleware,
    mock_context: MagicMock,
) -> None:
    """TimingMiddleware still logs timing on exceptions."""
    call_next = AsyncMock(side_effect=ValueError("test error"))

    with pytest.raises(ValueError, match="test error"):
        await timing_middleware.on_request(mock_context, call_next)


@pytest.mark.asyncio
async def test_timing_middleware_logs_slow_requests(
    mock_context: MagicMock,
) -> None:
    """TimingMiddleware warns on slow requests."""
    mock_logger = MagicMock()
    middleware = TimingMiddleware(logger=mock_logger, slow_threshold_ms=10.0)

    async def slow_handler(ctx):
        time.sleep(0.02)  # 20ms
        return "slow result"

    await middleware.on_request(mock_context, slow_handler)

    # Should log warning for slow request
    mock_logger.warning.assert_called_once()

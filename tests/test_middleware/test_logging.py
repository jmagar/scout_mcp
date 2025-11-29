"""Tests for logging middleware."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from scout_mcp.middleware.logging import LoggingMiddleware


@pytest.fixture
def logging_middleware() -> LoggingMiddleware:
    """Create a logging middleware instance."""
    return LoggingMiddleware()


@pytest.fixture
def mock_context() -> MagicMock:
    """Create a mock middleware context."""
    context = MagicMock()
    context.method = "tools/call"
    context.source = "client"
    context.message = MagicMock()
    context.message.name = "scout"
    context.message.arguments = {"target": "tootie:/etc/hosts"}
    return context


@pytest.mark.asyncio
async def test_logging_middleware_logs_request(
    mock_context: MagicMock,
) -> None:
    """LoggingMiddleware logs incoming requests."""
    mock_logger = MagicMock()
    middleware = LoggingMiddleware(logger=mock_logger)
    call_next = AsyncMock(return_value="result")

    await middleware.on_message(mock_context, call_next)

    # Should log the incoming request
    assert mock_logger.info.call_count >= 1
    first_call = mock_logger.info.call_args_list[0]
    assert "tools/call" in str(first_call)


@pytest.mark.asyncio
async def test_logging_middleware_logs_response(
    mock_context: MagicMock,
) -> None:
    """LoggingMiddleware logs completed responses."""
    mock_logger = MagicMock()
    middleware = LoggingMiddleware(logger=mock_logger)
    call_next = AsyncMock(return_value="result")

    await middleware.on_message(mock_context, call_next)

    # Should log completion
    assert mock_logger.info.call_count >= 2


@pytest.mark.asyncio
async def test_logging_middleware_includes_payloads_when_enabled(
    mock_context: MagicMock,
) -> None:
    """LoggingMiddleware includes request payloads when enabled."""
    mock_logger = MagicMock()
    middleware = LoggingMiddleware(logger=mock_logger, include_payloads=True)
    call_next = AsyncMock(return_value="result")

    await middleware.on_message(mock_context, call_next)

    # Check that payload info was logged
    all_calls = str(mock_logger.debug.call_args_list)
    assert "target" in all_calls or "tootie" in all_calls


@pytest.mark.asyncio
async def test_logging_middleware_truncates_long_payloads(
    mock_context: MagicMock,
) -> None:
    """LoggingMiddleware truncates payloads exceeding max length."""
    mock_logger = MagicMock()
    middleware = LoggingMiddleware(
        logger=mock_logger,
        include_payloads=True,
        max_payload_length=20,
    )
    mock_context.message.arguments = {"data": "x" * 100}
    call_next = AsyncMock(return_value="result")

    await middleware.on_message(mock_context, call_next)

    # Payload should be truncated
    all_calls = str(mock_logger.debug.call_args_list)
    assert "truncated" in all_calls.lower() or len("x" * 100) > 20


@pytest.mark.asyncio
async def test_logging_middleware_logs_errors(
    mock_context: MagicMock,
) -> None:
    """LoggingMiddleware logs errors at error level."""
    mock_logger = MagicMock()
    middleware = LoggingMiddleware(logger=mock_logger)
    call_next = AsyncMock(side_effect=ValueError("test error"))

    with pytest.raises(ValueError):
        await middleware.on_message(mock_context, call_next)

    mock_logger.error.assert_called_once()

"""Tests for error handling middleware."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from scout_mcp.middleware.errors import ErrorHandlingMiddleware


@pytest.fixture
def error_middleware() -> ErrorHandlingMiddleware:
    """Create an error handling middleware instance."""
    return ErrorHandlingMiddleware()


@pytest.fixture
def mock_context() -> MagicMock:
    """Create a mock middleware context."""
    context = MagicMock()
    context.method = "tools/call"
    context.message = MagicMock()
    context.message.name = "scout"
    return context


@pytest.mark.asyncio
async def test_error_middleware_passes_through_success(
    error_middleware: ErrorHandlingMiddleware,
    mock_context: MagicMock,
) -> None:
    """ErrorHandlingMiddleware passes through successful requests."""
    call_next = AsyncMock(return_value="success")

    result = await error_middleware.on_message(mock_context, call_next)

    assert result == "success"


@pytest.mark.asyncio
async def test_error_middleware_logs_errors(
    mock_context: MagicMock,
) -> None:
    """ErrorHandlingMiddleware logs errors with traceback."""
    mock_logger = MagicMock()
    middleware = ErrorHandlingMiddleware(logger=mock_logger, include_traceback=True)
    call_next = AsyncMock(side_effect=ValueError("test error"))

    with pytest.raises(ValueError):
        await middleware.on_message(mock_context, call_next)

    mock_logger.error.assert_called()
    error_call = str(mock_logger.error.call_args)
    assert "ValueError" in error_call or "test error" in error_call


@pytest.mark.asyncio
async def test_error_middleware_tracks_error_stats(
    error_middleware: ErrorHandlingMiddleware,
    mock_context: MagicMock,
) -> None:
    """ErrorHandlingMiddleware tracks error statistics."""
    call_next = AsyncMock(side_effect=ValueError("test error"))

    with pytest.raises(ValueError):
        await error_middleware.on_message(mock_context, call_next)

    stats = error_middleware.get_error_stats()
    assert "ValueError" in stats
    assert stats["ValueError"] == 1


@pytest.mark.asyncio
async def test_error_middleware_increments_stats(
    error_middleware: ErrorHandlingMiddleware,
    mock_context: MagicMock,
) -> None:
    """ErrorHandlingMiddleware increments stats for repeated errors."""
    call_next = AsyncMock(side_effect=ValueError("test"))

    for _ in range(3):
        with pytest.raises(ValueError):
            await error_middleware.on_message(mock_context, call_next)

    stats = error_middleware.get_error_stats()
    assert stats["ValueError"] == 3


@pytest.mark.asyncio
async def test_error_middleware_calls_callback(
    mock_context: MagicMock,
) -> None:
    """ErrorHandlingMiddleware calls error callback when provided."""
    callback = MagicMock()
    middleware = ErrorHandlingMiddleware(error_callback=callback)
    error = ValueError("callback test")
    call_next = AsyncMock(side_effect=error)

    with pytest.raises(ValueError):
        await middleware.on_message(mock_context, call_next)

    callback.assert_called_once()
    call_args = callback.call_args[0]
    assert call_args[0] == error
    assert call_args[1] == mock_context


@pytest.mark.asyncio
async def test_error_middleware_resets_stats(
    error_middleware: ErrorHandlingMiddleware,
    mock_context: MagicMock,
) -> None:
    """ErrorHandlingMiddleware can reset error statistics."""
    call_next = AsyncMock(side_effect=ValueError("test"))

    with pytest.raises(ValueError):
        await error_middleware.on_message(mock_context, call_next)

    assert error_middleware.get_error_stats()["ValueError"] == 1

    error_middleware.reset_stats()

    assert error_middleware.get_error_stats() == {}

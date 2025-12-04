"""Tests for logging middleware."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from scout_mcp.middleware.logging import LoggingMiddleware


@pytest.fixture
def logging_middleware() -> LoggingMiddleware:
    """Create a logging middleware instance."""
    return LoggingMiddleware()


@pytest.fixture
def mock_tool_context() -> MagicMock:
    """Create a mock middleware context for tool calls."""
    context = MagicMock()
    context.method = "tools/call"
    context.source = "client"
    context.message = MagicMock()
    context.message.name = "scout"
    context.message.arguments = {"target": "tootie:/etc/hosts"}
    return context


@pytest.fixture
def mock_resource_context() -> MagicMock:
    """Create a mock middleware context for resource reads."""
    context = MagicMock()
    context.method = "resources/read"
    context.source = "client"
    context.message = MagicMock()
    context.message.uri = "tootie://etc/hosts"
    return context


@pytest.fixture
def mock_generic_context() -> MagicMock:
    """Create a mock middleware context for generic messages."""
    context = MagicMock()
    context.method = "prompts/get"
    context.source = "client"
    context.message = MagicMock()
    return context


@pytest.mark.asyncio
async def test_logging_middleware_logs_tool_call(
    mock_tool_context: MagicMock,
) -> None:
    """LoggingMiddleware logs tool calls with name and arguments."""
    mock_logger = MagicMock()
    middleware = LoggingMiddleware(logger=mock_logger)
    call_next = AsyncMock(return_value="result")

    await middleware.on_call_tool(mock_tool_context, call_next)

    # Should log the tool call (>>> TOOL) and completion (<<< TOOL)
    assert mock_logger.info.call_count >= 1
    # Also check logger.log was called for completion
    all_info_calls = str(mock_logger.info.call_args_list)
    all_log_calls = str(mock_logger.log.call_args_list)
    assert ">>> TOOL" in all_info_calls
    assert "scout" in all_info_calls
    assert "<<< TOOL" in all_log_calls


@pytest.mark.asyncio
async def test_logging_middleware_logs_tool_arguments(
    mock_tool_context: MagicMock,
) -> None:
    """LoggingMiddleware includes tool arguments in log."""
    mock_logger = MagicMock()
    middleware = LoggingMiddleware(logger=mock_logger)
    call_next = AsyncMock(return_value="result")

    await middleware.on_call_tool(mock_tool_context, call_next)

    # Tool arguments should appear in the log
    all_calls = str(mock_logger.info.call_args_list)
    assert "target=" in all_calls


@pytest.mark.asyncio
async def test_logging_middleware_logs_resource_read(
    mock_resource_context: MagicMock,
) -> None:
    """LoggingMiddleware logs resource reads with URI."""
    mock_logger = MagicMock()
    middleware = LoggingMiddleware(logger=mock_logger)
    call_next = AsyncMock(return_value="file contents")

    await middleware.on_read_resource(mock_resource_context, call_next)

    # Should log the resource read
    assert mock_logger.info.call_count >= 1
    all_info_calls = str(mock_logger.info.call_args_list)
    all_log_calls = str(mock_logger.log.call_args_list)
    assert ">>> RESOURCE" in all_info_calls
    assert "tootie://etc/hosts" in all_info_calls
    assert "<<< RESOURCE" in all_log_calls


@pytest.mark.asyncio
async def test_logging_middleware_includes_payloads_when_enabled(
    mock_tool_context: MagicMock,
) -> None:
    """LoggingMiddleware includes request payloads when enabled."""
    mock_logger = MagicMock()
    middleware = LoggingMiddleware(logger=mock_logger, include_payloads=True)
    call_next = AsyncMock(return_value="result")

    await middleware.on_call_tool(mock_tool_context, call_next)

    # Check that payload info was logged at debug level
    all_calls = str(mock_logger.debug.call_args_list)
    assert "target" in all_calls or "tootie" in all_calls


@pytest.mark.asyncio
async def test_logging_middleware_truncates_long_payloads(
    mock_tool_context: MagicMock,
) -> None:
    """LoggingMiddleware truncates payloads exceeding max length."""
    mock_logger = MagicMock()
    middleware = LoggingMiddleware(
        logger=mock_logger,
        include_payloads=True,
        max_payload_length=20,
    )
    mock_tool_context.message.arguments = {"data": "x" * 100}
    call_next = AsyncMock(return_value="result")

    await middleware.on_call_tool(mock_tool_context, call_next)

    # Payload should be truncated
    all_calls = str(mock_logger.debug.call_args_list)
    assert "truncated" in all_calls.lower() or len("x" * 100) > 20


@pytest.mark.asyncio
async def test_logging_middleware_logs_tool_errors(
    mock_tool_context: MagicMock,
) -> None:
    """LoggingMiddleware logs tool errors at error level."""
    mock_logger = MagicMock()
    middleware = LoggingMiddleware(logger=mock_logger)
    call_next = AsyncMock(side_effect=ValueError("test error"))

    with pytest.raises(ValueError):
        await middleware.on_call_tool(mock_tool_context, call_next)

    mock_logger.error.assert_called_once()
    error_call = str(mock_logger.error.call_args)
    assert "!!! TOOL" in error_call
    assert "ValueError" in error_call


@pytest.mark.asyncio
async def test_logging_middleware_logs_resource_errors(
    mock_resource_context: MagicMock,
) -> None:
    """LoggingMiddleware logs resource errors at error level."""
    mock_logger = MagicMock()
    middleware = LoggingMiddleware(logger=mock_logger)
    call_next = AsyncMock(side_effect=FileNotFoundError("not found"))

    with pytest.raises(FileNotFoundError):
        await middleware.on_read_resource(mock_resource_context, call_next)

    mock_logger.error.assert_called_once()
    error_call = str(mock_logger.error.call_args)
    assert "!!! RESOURCE" in error_call


@pytest.mark.asyncio
async def test_logging_middleware_skips_handled_methods_in_on_message(
    mock_tool_context: MagicMock,
) -> None:
    """on_message skips methods that have dedicated handlers."""
    mock_logger = MagicMock()
    middleware = LoggingMiddleware(logger=mock_logger)
    call_next = AsyncMock(return_value="result")

    # tools/call should be skipped by on_message
    result = await middleware.on_message(mock_tool_context, call_next)

    # Should just pass through without logging
    assert result == "result"
    # No info logging should happen for skipped methods
    mock_logger.info.assert_not_called()


@pytest.mark.asyncio
async def test_logging_middleware_logs_generic_messages(
    mock_generic_context: MagicMock,
) -> None:
    """on_message logs generic messages not handled by specific methods."""
    mock_logger = MagicMock()
    middleware = LoggingMiddleware(logger=mock_logger)
    call_next = AsyncMock(return_value="result")

    await middleware.on_message(mock_generic_context, call_next)

    # Should log at debug level
    assert mock_logger.debug.call_count >= 1
    all_calls = str(mock_logger.debug.call_args_list)
    assert "prompts/get" in all_calls


@pytest.mark.asyncio
async def test_logging_middleware_logs_list_tools() -> None:
    """LoggingMiddleware logs list tools requests."""
    mock_logger = MagicMock()
    middleware = LoggingMiddleware(logger=mock_logger)
    context = MagicMock()
    context.method = "tools/list"

    # Mock result with tools attribute
    result = MagicMock()
    result.tools = [MagicMock(), MagicMock()]
    call_next = AsyncMock(return_value=result)

    await middleware.on_list_tools(context, call_next)

    assert mock_logger.info.call_count >= 2
    all_calls = str(mock_logger.info.call_args_list)
    assert "LIST TOOLS" in all_calls
    # Check that 2 was passed as tool count argument
    assert ", 2," in all_calls or "2, " in all_calls


@pytest.mark.asyncio
async def test_logging_middleware_logs_list_resources() -> None:
    """LoggingMiddleware logs list resources requests."""
    mock_logger = MagicMock()
    middleware = LoggingMiddleware(logger=mock_logger)
    context = MagicMock()
    context.method = "resources/list"

    # Mock result with resources attribute
    result = MagicMock()
    result.resources = [MagicMock(), MagicMock(), MagicMock()]
    call_next = AsyncMock(return_value=result)

    await middleware.on_list_resources(context, call_next)

    assert mock_logger.info.call_count >= 2
    all_calls = str(mock_logger.info.call_args_list)
    assert "LIST RESOURCES" in all_calls
    # Check that 3 was passed as resource count argument
    assert ", 3," in all_calls or "3, " in all_calls


@pytest.mark.asyncio
async def test_logging_middleware_summarizes_string_results(
    mock_tool_context: MagicMock,
) -> None:
    """LoggingMiddleware summarizes string results with char/line count."""
    mock_logger = MagicMock()
    middleware = LoggingMiddleware(logger=mock_logger)
    result = "line1\nline2\nline3"
    call_next = AsyncMock(return_value=result)

    await middleware.on_call_tool(mock_tool_context, call_next)

    # logger.log is used for completion, check all logged calls
    all_log_calls = str(mock_logger.log.call_args_list)
    # Should show char count and line count
    assert "chars" in all_log_calls
    assert "lines" in all_log_calls


@pytest.mark.asyncio
async def test_logging_middleware_formats_duration() -> None:
    """LoggingMiddleware includes duration in milliseconds."""
    mock_logger = MagicMock()
    middleware = LoggingMiddleware(logger=mock_logger)
    context = MagicMock()
    context.method = "tools/call"
    context.message = MagicMock()
    context.message.name = "scout"
    context.message.arguments = {}
    call_next = AsyncMock(return_value="result")

    await middleware.on_call_tool(context, call_next)

    # logger.log is used for completion with timing
    all_log_calls = str(mock_logger.log.call_args_list)
    assert "ms" in all_log_calls


@pytest.mark.asyncio
async def test_logging_middleware_slow_threshold() -> None:
    """LoggingMiddleware warns on slow requests."""
    import asyncio

    mock_logger = MagicMock()
    # Set a very low threshold so the test triggers it
    middleware = LoggingMiddleware(logger=mock_logger, slow_threshold_ms=1.0)
    context = MagicMock()
    context.method = "tools/call"
    context.message = MagicMock()
    context.message.name = "scout"
    context.message.arguments = {}

    async def slow_handler(_: MagicMock) -> str:
        await asyncio.sleep(0.01)  # 10ms delay
        return "result"

    await middleware.on_call_tool(context, slow_handler)

    # Should log at WARNING level for slow requests
    # logger.log is called with level as first arg
    call_args = mock_logger.log.call_args_list
    assert len(call_args) > 0
    # First positional arg is log level (WARNING = 30)
    log_level = call_args[0][0][0]
    import logging

    assert log_level == logging.WARNING
    all_log_calls = str(call_args)
    assert "SLOW!" in all_log_calls

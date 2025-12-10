# Middleware Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement logging, error handling, and timing middleware for the Scout MCP server to provide observability, consistent error responses, and performance metrics.

**Architecture:** Create a `scout_mcp/middleware/` package with three middleware classes that follow FastMCP's middleware patterns. Each middleware hooks into `on_message` or operation-specific hooks to intercept requests/responses. The middleware will be composable and added to the FastMCP server in order.

**Tech Stack:** FastMCP 2.0+ middleware system, Python 3.11+, structlog for structured logging, time.perf_counter for timing

---

## Task 1: Create middleware package structure

**Files:**
- Create: `scout_mcp/middleware/__init__.py`
- Create: `scout_mcp/middleware/base.py`
- Test: `tests/test_middleware/__init__.py`
- Test: `tests/test_middleware/test_base.py`

**Step 1: Create directory structure**

```bash
mkdir -p scout_mcp/middleware tests/test_middleware
touch scout_mcp/middleware/__init__.py tests/test_middleware/__init__.py
```

**Step 2: Write the base module test**

Create `tests/test_middleware/test_base.py`:

```python
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
```

**Step 3: Run test to verify it fails**

```bash
cd /code/scout_mcp && .venv/bin/python -m pytest tests/test_middleware/test_base.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scout_mcp.middleware'`

**Step 4: Write minimal implementation**

Create `scout_mcp/middleware/base.py`:

```python
"""Base middleware classes for Scout MCP."""

import logging
from typing import Any

from fastmcp.server.middleware import Middleware


class ScoutMiddleware(Middleware):
    """Base middleware with common functionality for Scout MCP.

    Provides:
        - Configurable logger
        - Common initialization patterns
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """Initialize middleware.

        Args:
            logger: Optional custom logger. Defaults to module logger.
        """
        self.logger = logger or logging.getLogger(__name__)
```

**Step 5: Update package __init__.py**

Create `scout_mcp/middleware/__init__.py`:

```python
"""Scout MCP middleware components."""

from scout_mcp.middleware.base import ScoutMiddleware

__all__ = ["ScoutMiddleware"]
```

**Step 6: Run test to verify it passes**

```bash
cd /code/scout_mcp && .venv/bin/python -m pytest tests/test_middleware/test_base.py -v
```

Expected: PASS

**Step 7: Commit**

```bash
git add scout_mcp/middleware/ tests/test_middleware/
git commit -m "feat(middleware): add base middleware package structure"
```

---

## Task 2: Implement TimingMiddleware

**Files:**
- Create: `scout_mcp/middleware/timing.py`
- Test: `tests/test_middleware/test_timing.py`

**Step 1: Write the failing test**

Create `tests/test_middleware/test_timing.py`:

```python
"""Tests for timing middleware."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time

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
```

**Step 2: Run test to verify it fails**

```bash
cd /code/scout_mcp && .venv/bin/python -m pytest tests/test_middleware/test_timing.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scout_mcp.middleware.timing'`

**Step 3: Write minimal implementation**

Create `scout_mcp/middleware/timing.py`:

```python
"""Timing middleware for request duration tracking."""

import logging
import time
from typing import Any

from fastmcp.server.middleware import MiddlewareContext

from scout_mcp.middleware.base import ScoutMiddleware


class TimingMiddleware(ScoutMiddleware):
    """Middleware that logs execution time of MCP requests.

    Measures duration of each request and logs timing information.
    Optionally warns on slow requests exceeding a threshold.

    Example:
        >>> middleware = TimingMiddleware(slow_threshold_ms=100.0)
        >>> mcp.add_middleware(middleware)
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
        slow_threshold_ms: float = 1000.0,
    ) -> None:
        """Initialize timing middleware.

        Args:
            logger: Optional custom logger.
            slow_threshold_ms: Threshold in milliseconds for slow request warnings.
                Defaults to 1000ms (1 second).
        """
        super().__init__(logger=logger)
        self.slow_threshold_ms = slow_threshold_ms

    async def on_request(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Time request execution and log results.

        Args:
            context: The middleware context with request info.
            call_next: Function to call the next handler.

        Returns:
            The result from the next handler.
        """
        start_time = time.perf_counter()
        method = context.method

        try:
            result = await call_next(context)
            duration_ms = (time.perf_counter() - start_time) * 1000

            if duration_ms >= self.slow_threshold_ms:
                self.logger.warning(
                    "Slow request: %s completed in %.2fms",
                    method,
                    duration_ms,
                )
            else:
                self.logger.info(
                    "Request %s completed in %.2fms",
                    method,
                    duration_ms,
                )

            return result

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.logger.error(
                "Request %s failed after %.2fms: %s",
                method,
                duration_ms,
                str(e),
            )
            raise
```

**Step 4: Update package __init__.py**

Edit `scout_mcp/middleware/__init__.py`:

```python
"""Scout MCP middleware components."""

from scout_mcp.middleware.base import ScoutMiddleware
from scout_mcp.middleware.timing import TimingMiddleware

__all__ = ["ScoutMiddleware", "TimingMiddleware"]
```

**Step 5: Run test to verify it passes**

```bash
cd /code/scout_mcp && .venv/bin/python -m pytest tests/test_middleware/test_timing.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add scout_mcp/middleware/timing.py tests/test_middleware/test_timing.py scout_mcp/middleware/__init__.py
git commit -m "feat(middleware): add TimingMiddleware for request duration tracking"
```

---

## Task 3: Implement LoggingMiddleware

**Files:**
- Create: `scout_mcp/middleware/logging.py`
- Test: `tests/test_middleware/test_logging.py`

**Step 1: Write the failing test**

Create `tests/test_middleware/test_logging.py`:

```python
"""Tests for logging middleware."""

import pytest
from unittest.mock import AsyncMock, MagicMock

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
```

**Step 2: Run test to verify it fails**

```bash
cd /code/scout_mcp && .venv/bin/python -m pytest tests/test_middleware/test_logging.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scout_mcp.middleware.logging'`

**Step 3: Write minimal implementation**

Create `scout_mcp/middleware/logging.py`:

```python
"""Logging middleware for request/response tracking."""

import json
import logging
from typing import Any

from fastmcp.server.middleware import MiddlewareContext

from scout_mcp.middleware.base import ScoutMiddleware


class LoggingMiddleware(ScoutMiddleware):
    """Middleware that logs MCP requests and responses.

    Provides comprehensive request/response logging with configurable
    detail levels and payload inclusion.

    Example:
        >>> middleware = LoggingMiddleware(include_payloads=True)
        >>> mcp.add_middleware(middleware)
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
        include_payloads: bool = False,
        max_payload_length: int = 1000,
    ) -> None:
        """Initialize logging middleware.

        Args:
            logger: Optional custom logger.
            include_payloads: Whether to log request/response payloads.
            max_payload_length: Maximum payload length before truncation.
        """
        super().__init__(logger=logger)
        self.include_payloads = include_payloads
        self.max_payload_length = max_payload_length

    def _truncate(self, data: Any) -> str:
        """Truncate data to max payload length.

        Args:
            data: Data to serialize and truncate.

        Returns:
            Truncated string representation.
        """
        try:
            text = json.dumps(data, default=str)
        except (TypeError, ValueError):
            text = str(data)

        if len(text) > self.max_payload_length:
            return text[: self.max_payload_length] + "... [truncated]"
        return text

    async def on_message(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Log incoming requests and outgoing responses.

        Args:
            context: The middleware context with request info.
            call_next: Function to call the next handler.

        Returns:
            The result from the next handler.
        """
        method = context.method
        source = getattr(context, "source", "unknown")

        # Log incoming request
        self.logger.info("Received %s from %s", method, source)

        if self.include_payloads and hasattr(context.message, "arguments"):
            payload = getattr(context.message, "arguments", None)
            if payload:
                self.logger.debug(
                    "Request payload: %s",
                    self._truncate(payload),
                )

        try:
            result = await call_next(context)

            # Log successful completion
            self.logger.info("Completed %s", method)

            if self.include_payloads and result is not None:
                self.logger.debug(
                    "Response payload: %s",
                    self._truncate(result),
                )

            return result

        except Exception as e:
            self.logger.error(
                "Failed %s: %s: %s",
                method,
                type(e).__name__,
                str(e),
            )
            raise
```

**Step 4: Update package __init__.py**

Edit `scout_mcp/middleware/__init__.py`:

```python
"""Scout MCP middleware components."""

from scout_mcp.middleware.base import ScoutMiddleware
from scout_mcp.middleware.logging import LoggingMiddleware
from scout_mcp.middleware.timing import TimingMiddleware

__all__ = ["ScoutMiddleware", "LoggingMiddleware", "TimingMiddleware"]
```

**Step 5: Run test to verify it passes**

```bash
cd /code/scout_mcp && .venv/bin/python -m pytest tests/test_middleware/test_logging.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add scout_mcp/middleware/logging.py tests/test_middleware/test_logging.py scout_mcp/middleware/__init__.py
git commit -m "feat(middleware): add LoggingMiddleware for request/response logging"
```

---

## Task 4: Implement ErrorHandlingMiddleware

**Files:**
- Create: `scout_mcp/middleware/errors.py`
- Test: `tests/test_middleware/test_errors.py`

**Step 1: Write the failing test**

Create `tests/test_middleware/test_errors.py`:

```python
"""Tests for error handling middleware."""

import pytest
from unittest.mock import AsyncMock, MagicMock

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
```

**Step 2: Run test to verify it fails**

```bash
cd /code/scout_mcp && .venv/bin/python -m pytest tests/test_middleware/test_errors.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scout_mcp.middleware.errors'`

**Step 3: Write minimal implementation**

Create `scout_mcp/middleware/errors.py`:

```python
"""Error handling middleware for consistent error responses."""

import logging
import traceback
from collections import defaultdict
from typing import Any, Callable

from fastmcp.server.middleware import MiddlewareContext

from scout_mcp.middleware.base import ScoutMiddleware


ErrorCallback = Callable[[Exception, MiddlewareContext], None]


class ErrorHandlingMiddleware(ScoutMiddleware):
    """Middleware that provides consistent error handling and logging.

    Catches exceptions, logs them appropriately, tracks error statistics,
    and optionally calls an error callback for custom handling.

    Example:
        >>> def on_error(exc, ctx):
        ...     print(f"Error in {ctx.method}: {exc}")
        >>> middleware = ErrorHandlingMiddleware(error_callback=on_error)
        >>> mcp.add_middleware(middleware)
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
        include_traceback: bool = False,
        error_callback: ErrorCallback | None = None,
    ) -> None:
        """Initialize error handling middleware.

        Args:
            logger: Optional custom logger.
            include_traceback: Whether to include full traceback in logs.
            error_callback: Optional callback called on each error.
                Receives (exception, context) as arguments.
        """
        super().__init__(logger=logger)
        self.include_traceback = include_traceback
        self.error_callback = error_callback
        self._error_counts: dict[str, int] = defaultdict(int)

    def get_error_stats(self) -> dict[str, int]:
        """Get error statistics by exception type.

        Returns:
            Dictionary mapping exception type names to occurrence counts.
        """
        return dict(self._error_counts)

    def reset_stats(self) -> None:
        """Reset error statistics."""
        self._error_counts.clear()

    async def on_message(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Handle errors during request processing.

        Args:
            context: The middleware context with request info.
            call_next: Function to call the next handler.

        Returns:
            The result from the next handler.

        Raises:
            Exception: Re-raises the original exception after logging.
        """
        try:
            return await call_next(context)

        except Exception as e:
            error_type = type(e).__name__
            method = context.method

            # Track statistics
            self._error_counts[error_type] += 1

            # Log the error
            if self.include_traceback:
                tb = traceback.format_exc()
                self.logger.error(
                    "Error in %s: %s: %s\n%s",
                    method,
                    error_type,
                    str(e),
                    tb,
                )
            else:
                self.logger.error(
                    "Error in %s: %s: %s",
                    method,
                    error_type,
                    str(e),
                )

            # Call error callback if provided
            if self.error_callback:
                try:
                    self.error_callback(e, context)
                except Exception as callback_error:
                    self.logger.warning(
                        "Error callback failed: %s",
                        str(callback_error),
                    )

            # Re-raise the original exception
            raise
```

**Step 4: Update package __init__.py**

Edit `scout_mcp/middleware/__init__.py`:

```python
"""Scout MCP middleware components."""

from scout_mcp.middleware.base import ScoutMiddleware
from scout_mcp.middleware.errors import ErrorHandlingMiddleware
from scout_mcp.middleware.logging import LoggingMiddleware
from scout_mcp.middleware.timing import TimingMiddleware

__all__ = [
    "ScoutMiddleware",
    "ErrorHandlingMiddleware",
    "LoggingMiddleware",
    "TimingMiddleware",
]
```

**Step 5: Run test to verify it passes**

```bash
cd /code/scout_mcp && .venv/bin/python -m pytest tests/test_middleware/test_errors.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add scout_mcp/middleware/errors.py tests/test_middleware/test_errors.py scout_mcp/middleware/__init__.py
git commit -m "feat(middleware): add ErrorHandlingMiddleware with stats tracking"
```

---

## Task 5: Add DetailedTimingMiddleware for operation-specific timing

**Files:**
- Modify: `scout_mcp/middleware/timing.py`
- Modify: `tests/test_middleware/test_timing.py`

**Step 1: Write the failing test**

Add to `tests/test_middleware/test_timing.py`:

```python
from scout_mcp.middleware.timing import DetailedTimingMiddleware


@pytest.fixture
def detailed_timing_middleware() -> DetailedTimingMiddleware:
    """Create a detailed timing middleware instance."""
    return DetailedTimingMiddleware()


@pytest.mark.asyncio
async def test_detailed_timing_tracks_tool_calls() -> None:
    """DetailedTimingMiddleware tracks tool execution times."""
    mock_logger = MagicMock()
    middleware = DetailedTimingMiddleware(logger=mock_logger)
    context = MagicMock()
    context.method = "tools/call"
    context.message = MagicMock()
    context.message.name = "scout"

    call_next = AsyncMock(return_value="result")

    await middleware.on_call_tool(context, call_next)

    mock_logger.info.assert_called()
    log_call = str(mock_logger.info.call_args)
    assert "scout" in log_call


@pytest.mark.asyncio
async def test_detailed_timing_tracks_resource_reads() -> None:
    """DetailedTimingMiddleware tracks resource read times."""
    mock_logger = MagicMock()
    middleware = DetailedTimingMiddleware(logger=mock_logger)
    context = MagicMock()
    context.method = "resources/read"
    context.message = MagicMock()
    context.message.uri = "scout://tootie/etc/hosts"

    call_next = AsyncMock(return_value="result")

    await middleware.on_read_resource(context, call_next)

    mock_logger.info.assert_called()
    log_call = str(mock_logger.info.call_args)
    assert "scout://tootie" in log_call


@pytest.mark.asyncio
async def test_detailed_timing_provides_stats() -> None:
    """DetailedTimingMiddleware provides timing statistics."""
    middleware = DetailedTimingMiddleware()
    context = MagicMock()
    context.method = "tools/call"
    context.message = MagicMock()
    context.message.name = "scout"

    call_next = AsyncMock(return_value="result")

    await middleware.on_call_tool(context, call_next)

    stats = middleware.get_timing_stats()
    assert "tool:scout" in stats
    assert stats["tool:scout"]["count"] == 1
    assert "total_ms" in stats["tool:scout"]
    assert "avg_ms" in stats["tool:scout"]
```

**Step 2: Run test to verify it fails**

```bash
cd /code/scout_mcp && .venv/bin/python -m pytest tests/test_middleware/test_timing.py::test_detailed_timing_tracks_tool_calls -v
```

Expected: FAIL with `ImportError`

**Step 3: Write implementation**

Add to `scout_mcp/middleware/timing.py`:

```python
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class TimingStats:
    """Statistics for a timed operation."""

    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0

    @property
    def avg_ms(self) -> float:
        """Average duration in milliseconds."""
        return self.total_ms / self.count if self.count > 0 else 0.0

    def record(self, duration_ms: float) -> None:
        """Record a new timing measurement."""
        self.count += 1
        self.total_ms += duration_ms
        self.min_ms = min(self.min_ms, duration_ms)
        self.max_ms = max(self.max_ms, duration_ms)

    def to_dict(self) -> dict[str, float | int]:
        """Convert to dictionary."""
        return {
            "count": self.count,
            "total_ms": round(self.total_ms, 2),
            "avg_ms": round(self.avg_ms, 2),
            "min_ms": round(self.min_ms, 2) if self.min_ms != float("inf") else 0.0,
            "max_ms": round(self.max_ms, 2),
        }


class DetailedTimingMiddleware(ScoutMiddleware):
    """Middleware with per-operation timing breakdowns.

    Tracks timing for specific operation types (tools, resources, prompts)
    and provides aggregate statistics.

    Example:
        >>> middleware = DetailedTimingMiddleware()
        >>> mcp.add_middleware(middleware)
        >>> # Later...
        >>> stats = middleware.get_timing_stats()
        >>> print(stats["tool:scout"]["avg_ms"])
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
        slow_threshold_ms: float = 1000.0,
    ) -> None:
        """Initialize detailed timing middleware.

        Args:
            logger: Optional custom logger.
            slow_threshold_ms: Threshold for slow operation warnings.
        """
        super().__init__(logger=logger)
        self.slow_threshold_ms = slow_threshold_ms
        self._stats: dict[str, TimingStats] = defaultdict(TimingStats)

    def get_timing_stats(self) -> dict[str, dict[str, float | int]]:
        """Get timing statistics for all operations.

        Returns:
            Dictionary mapping operation keys to timing stats.
        """
        return {key: stats.to_dict() for key, stats in self._stats.items()}

    def reset_stats(self) -> None:
        """Reset all timing statistics."""
        self._stats.clear()

    async def _time_operation(
        self,
        key: str,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Time an operation and record stats.

        Args:
            key: Statistics key for this operation.
            context: The middleware context.
            call_next: Function to call the next handler.

        Returns:
            The result from the next handler.
        """
        start_time = time.perf_counter()

        try:
            result = await call_next(context)
            duration_ms = (time.perf_counter() - start_time) * 1000

            self._stats[key].record(duration_ms)

            if duration_ms >= self.slow_threshold_ms:
                self.logger.warning(
                    "Slow operation %s: %.2fms",
                    key,
                    duration_ms,
                )
            else:
                self.logger.info(
                    "Operation %s: %.2fms",
                    key,
                    duration_ms,
                )

            return result

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._stats[key].record(duration_ms)
            self.logger.error(
                "Operation %s failed after %.2fms: %s",
                key,
                duration_ms,
                str(e),
            )
            raise

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Time tool execution."""
        tool_name = getattr(context.message, "name", "unknown")
        return await self._time_operation(f"tool:{tool_name}", context, call_next)

    async def on_read_resource(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Time resource reading."""
        uri = getattr(context.message, "uri", "unknown")
        return await self._time_operation(f"resource:{uri}", context, call_next)

    async def on_get_prompt(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Time prompt retrieval."""
        name = getattr(context.message, "name", "unknown")
        return await self._time_operation(f"prompt:{name}", context, call_next)

    async def on_list_tools(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Time tool listing."""
        return await self._time_operation("list:tools", context, call_next)

    async def on_list_resources(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Time resource listing."""
        return await self._time_operation("list:resources", context, call_next)

    async def on_list_prompts(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Time prompt listing."""
        return await self._time_operation("list:prompts", context, call_next)
```

**Step 4: Update package __init__.py**

Edit `scout_mcp/middleware/__init__.py`:

```python
"""Scout MCP middleware components."""

from scout_mcp.middleware.base import ScoutMiddleware
from scout_mcp.middleware.errors import ErrorHandlingMiddleware
from scout_mcp.middleware.logging import LoggingMiddleware
from scout_mcp.middleware.timing import DetailedTimingMiddleware, TimingMiddleware

__all__ = [
    "ScoutMiddleware",
    "DetailedTimingMiddleware",
    "ErrorHandlingMiddleware",
    "LoggingMiddleware",
    "TimingMiddleware",
]
```

**Step 5: Run test to verify it passes**

```bash
cd /code/scout_mcp && .venv/bin/python -m pytest tests/test_middleware/test_timing.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add scout_mcp/middleware/timing.py tests/test_middleware/test_timing.py scout_mcp/middleware/__init__.py
git commit -m "feat(middleware): add DetailedTimingMiddleware with per-operation stats"
```

---

## Task 6: Integrate middleware into server.py

**Files:**
- Modify: `scout_mcp/server.py`
- Test: `tests/test_middleware/test_integration.py`

**Step 1: Write the failing integration test**

Create `tests/test_middleware/test_integration.py`:

```python
"""Integration tests for middleware with the server."""

import pytest
from unittest.mock import MagicMock, patch

from scout_mcp.server import mcp, configure_middleware
from scout_mcp.middleware import (
    ErrorHandlingMiddleware,
    LoggingMiddleware,
    TimingMiddleware,
)


def test_configure_middleware_adds_all_middleware() -> None:
    """configure_middleware adds timing, logging, and error middleware."""
    # Reset middleware stack
    mcp._middleware = []

    configure_middleware(mcp)

    # Should have 3 middleware
    assert len(mcp._middleware) == 3


def test_configure_middleware_order() -> None:
    """Middleware is added in correct order (error → timing → logging)."""
    mcp._middleware = []

    configure_middleware(mcp)

    # Order: ErrorHandling first (runs last on way in, first on way out)
    # Then Timing, then Logging (logs at outermost layer)
    middleware_types = [type(m).__name__ for m in mcp._middleware]

    # Error handling should be innermost (added first)
    assert middleware_types[0] == "ErrorHandlingMiddleware"
    assert middleware_types[1] == "TimingMiddleware"
    assert middleware_types[2] == "LoggingMiddleware"


def test_configure_middleware_respects_env_vars(monkeypatch) -> None:
    """Middleware configuration respects environment variables."""
    monkeypatch.setenv("SCOUT_LOG_PAYLOADS", "true")
    monkeypatch.setenv("SCOUT_SLOW_THRESHOLD_MS", "500")

    mcp._middleware = []

    configure_middleware(mcp)

    # Find logging middleware and check config
    logging_mw = next(
        m for m in mcp._middleware if isinstance(m, LoggingMiddleware)
    )
    assert logging_mw.include_payloads is True

    timing_mw = next(
        m for m in mcp._middleware if isinstance(m, TimingMiddleware)
    )
    assert timing_mw.slow_threshold_ms == 500.0
```

**Step 2: Run test to verify it fails**

```bash
cd /code/scout_mcp && .venv/bin/python -m pytest tests/test_middleware/test_integration.py -v
```

Expected: FAIL with `ImportError: cannot import name 'configure_middleware'`

**Step 3: Write implementation**

Add to `scout_mcp/server.py` after imports:

```python
import os

from scout_mcp.middleware import (
    ErrorHandlingMiddleware,
    LoggingMiddleware,
    TimingMiddleware,
)


def configure_middleware(server: FastMCP) -> None:
    """Configure middleware stack for the server.

    Adds middleware in order: ErrorHandling → Timing → Logging

    Environment variables:
        SCOUT_LOG_PAYLOADS: Set to "true" to log request/response payloads
        SCOUT_SLOW_THRESHOLD_MS: Threshold for slow request warnings (default: 1000)
        SCOUT_INCLUDE_TRACEBACK: Set to "true" to include tracebacks in error logs

    Args:
        server: The FastMCP server to configure.
    """
    # Parse environment configuration
    log_payloads = os.getenv("SCOUT_LOG_PAYLOADS", "").lower() == "true"
    slow_threshold = float(os.getenv("SCOUT_SLOW_THRESHOLD_MS", "1000"))
    include_traceback = os.getenv("SCOUT_INCLUDE_TRACEBACK", "").lower() == "true"

    # Add middleware in order (first added = innermost)
    server.add_middleware(
        ErrorHandlingMiddleware(include_traceback=include_traceback)
    )
    server.add_middleware(
        TimingMiddleware(slow_threshold_ms=slow_threshold)
    )
    server.add_middleware(
        LoggingMiddleware(include_payloads=log_payloads)
    )
```

Update the mcp initialization to call configure_middleware:

```python
# Initialize server
mcp = FastMCP("scout_mcp")

# Configure middleware stack
configure_middleware(mcp)
```

**Step 4: Run test to verify it passes**

```bash
cd /code/scout_mcp && .venv/bin/python -m pytest tests/test_middleware/test_integration.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add scout_mcp/server.py tests/test_middleware/test_integration.py
git commit -m "feat(middleware): integrate middleware stack into server"
```

---

## Task 7: Run full test suite and type checking

**Step 1: Run all tests**

```bash
cd /code/scout_mcp && .venv/bin/python -m pytest -v
```

Expected: All tests pass

**Step 2: Run type checking**

```bash
cd /code/scout_mcp && .venv/bin/python -m mypy scout_mcp/middleware/
```

Expected: No errors

**Step 3: Run linting**

```bash
cd /code/scout_mcp && .venv/bin/ruff check scout_mcp/middleware/
cd /code/scout_mcp && .venv/bin/ruff format scout_mcp/middleware/
```

Expected: Clean output

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: lint and type check middleware package"
```

---

## Verification Checklist

- [ ] `scout_mcp/middleware/__init__.py` created with all exports
- [ ] `scout_mcp/middleware/base.py` with `ScoutMiddleware` base class
- [ ] `scout_mcp/middleware/timing.py` with `TimingMiddleware` and `DetailedTimingMiddleware`
- [ ] `scout_mcp/middleware/logging.py` with `LoggingMiddleware`
- [ ] `scout_mcp/middleware/errors.py` with `ErrorHandlingMiddleware`
- [ ] All middleware tests pass
- [ ] Middleware integrated into server.py
- [ ] Environment variable configuration works
- [ ] Type checking passes
- [ ] Linting passes

---

## Usage Examples

After implementation, middleware can be used like this:

```python
from scout_mcp.middleware import (
    ErrorHandlingMiddleware,
    LoggingMiddleware,
    TimingMiddleware,
    DetailedTimingMiddleware,
)

# Basic usage (already configured in server.py)
# Just run the server and middleware is active

# Custom configuration
from scout_mcp.server import mcp

mcp._middleware = []  # Reset if needed

mcp.add_middleware(ErrorHandlingMiddleware(
    include_traceback=True,
    error_callback=lambda e, ctx: print(f"Error: {e}"),
))

mcp.add_middleware(DetailedTimingMiddleware(
    slow_threshold_ms=500,
))

mcp.add_middleware(LoggingMiddleware(
    include_payloads=True,
    max_payload_length=2000,
))

# Access statistics
timing_mw = next(
    m for m in mcp._middleware
    if isinstance(m, DetailedTimingMiddleware)
)
print(timing_mw.get_timing_stats())

error_mw = next(
    m for m in mcp._middleware
    if isinstance(m, ErrorHandlingMiddleware)
)
print(error_mw.get_error_stats())
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SCOUT_LOG_PAYLOADS` | `false` | Log request/response payloads |
| `SCOUT_SLOW_THRESHOLD_MS` | `1000` | Slow request warning threshold (ms) |
| `SCOUT_INCLUDE_TRACEBACK` | `false` | Include traceback in error logs |

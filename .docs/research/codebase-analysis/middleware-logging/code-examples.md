# Scout MCP Middleware - Code Examples and Patterns

## Creating Custom Middleware

### Basic Middleware Template

```python
"""Custom middleware for Scout MCP."""

import logging
from typing import Any
from fastmcp.server.middleware import MiddlewareContext
from scout_mcp.middleware.base import ScoutMiddleware


class CustomMiddleware(ScoutMiddleware):
    """Custom middleware with specific functionality."""

    def __init__(
        self,
        logger: logging.Logger | None = None,
        custom_param: str = "default",
    ) -> None:
        """Initialize middleware.

        Args:
            logger: Optional custom logger.
            custom_param: Custom configuration parameter.
        """
        super().__init__(logger=logger)
        self.custom_param = custom_param

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Process tool calls."""
        tool_name = getattr(context.message, "name", "unknown")

        # Pre-processing
        self.logger.debug(f"Tool {tool_name} starting")

        try:
            # Execute handler
            result = await call_next(context)

            # Post-processing on success
            self.logger.debug(f"Tool {tool_name} completed")
            return result

        except Exception as e:
            # Post-processing on error
            self.logger.error(f"Tool {tool_name} failed: {e}")
            raise
```

### Registering Custom Middleware

```python
# In scout_mcp/server.py:configure_middleware()

def configure_middleware(server: FastMCP) -> None:
    """Configure middleware stack for the server."""

    # Add middleware in order (first = innermost)
    server.add_middleware(ErrorHandlingMiddleware(include_traceback=False))
    server.add_middleware(CustomMiddleware(custom_param="value"))  # Add here
    server.add_middleware(LoggingMiddleware(include_payloads=False))
```

## Logging Patterns

### Structured Logging with Context

```python
# In a tool or resource handler
import logging
logger = logging.getLogger(__name__)

async def my_resource(host: str, path: str) -> str:
    """Resource handler with structured logging."""

    # Log with structured data
    logger.info(
        "Reading resource: host=%s, path=%s",
        host,
        path,
    )

    try:
        result = await perform_operation(host, path)
        logger.info(
            "Resource read successful: host=%s, bytes=%d",
            host,
            len(result),
        )
        return result

    except Exception as e:
        logger.error(
            "Resource read failed: host=%s, path=%s, error=%s",
            host,
            path,
            str(e),
        )
        raise
```

### Using Logger Extras for Rich Context

```python
import logging
from logging import LoggerAdapter

class HostLoggerAdapter(LoggerAdapter):
    """Logger adapter that includes host context."""

    def process(self, msg, kwargs):
        """Add host to all log messages."""
        return f"[{self.extra['host']}] {msg}", kwargs


# Usage in a service
base_logger = logging.getLogger(__name__)
logger = HostLoggerAdapter(base_logger, {"host": "tootie"})

logger.info("Connection established")
# Output: [tootie] Connection established
```

### Conditional Payload Logging

```python
import logging
import os

logger = logging.getLogger(__name__)
LOG_PAYLOADS = os.getenv("SCOUT_LOG_PAYLOADS", "").lower() == "true"

async def execute_command(host: str, command: str) -> str:
    """Execute command with optional payload logging."""

    logger.info(f"Executing command on {host}")

    if LOG_PAYLOADS:
        logger.debug(f"Command payload: {command[:100]}...")

    result = await ssh_run(host, command)

    if LOG_PAYLOADS:
        logger.debug(f"Result (first 500 chars): {result[:500]}")

    return result
```

## Performance Tracking

### Using DetailedTimingMiddleware

```python
from scout_mcp.middleware import DetailedTimingMiddleware

# Create middleware with statistics
timing_mw = DetailedTimingMiddleware(slow_threshold_ms=500.0)

# Add to server
server.add_middleware(timing_mw)

# Later, retrieve statistics
stats = timing_mw.get_timing_stats()

# Example output:
# {
#     "tool:scout": {
#         "count": 100,
#         "total_ms": 45234.5,
#         "avg_ms": 452.3,
#         "min_ms": 12.1,
#         "max_ms": 2345.6
#     },
#     "resource:tootie://etc": {...}
# }

# Print performance report
for operation, stats_dict in stats.items():
    print(f"{operation}:")
    print(f"  Calls: {stats_dict['count']}")
    print(f"  Avg: {stats_dict['avg_ms']:.2f}ms")
    print(f"  Min: {stats_dict['min_ms']:.2f}ms")
    print(f"  Max: {stats_dict['max_ms']:.2f}ms")
```

### Manual Timing in Handlers

```python
import time
import logging

logger = logging.getLogger(__name__)

async def expensive_operation(data: str) -> str:
    """Operation with manual timing."""
    start = time.perf_counter()

    try:
        # Expensive work
        result = await process_data(data)

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(f"Operation completed in {duration_ms:.2f}ms")

        return result

    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.error(f"Operation failed after {duration_ms:.2f}ms: {e}")
        raise
```

## Error Handling Patterns

### Error Callback for Alerts

```python
from scout_mcp.middleware import ErrorHandlingMiddleware
import asyncio

# Define error callback
async def send_error_alert(exc: Exception, context) -> None:
    """Send alert on critical errors."""
    if isinstance(exc, CriticalException):
        await send_notification(
            f"Critical error in {context.method}: {exc}"
        )

# Create middleware with callback
error_mw = ErrorHandlingMiddleware(
    error_callback=send_error_alert,
    include_traceback=True
)
```

### Tracking Error Patterns

```python
from scout_mcp.middleware import ErrorHandlingMiddleware
from collections import Counter

# Create middleware
error_mw = ErrorHandlingMiddleware()

# After running for a while, analyze errors
stats = error_mw.get_error_stats()

# Find most common errors
most_common = Counter(stats).most_common(5)
for error_type, count in most_common:
    print(f"{error_type}: {count} occurrences")

# Reset for next period
error_mw.reset_stats()
```

### Custom Exception Logging

```python
import traceback
import logging

logger = logging.getLogger(__name__)

async def risky_operation() -> str:
    """Operation with detailed exception logging."""
    try:
        return await perform_ssh_operation()

    except ConnectionError as e:
        logger.error(
            "SSH connection failed: %s\n%s",
            str(e),
            traceback.format_exc()
        )
        raise

    except TimeoutError as e:
        logger.warning("Operation timed out: %s", str(e))
        raise

    except Exception as e:
        logger.critical(
            "Unexpected error: %s\n%s",
            str(e),
            traceback.format_exc()
        )
        raise
```

## Custom Formatters

### JSON Formatter for Log Aggregation

```python
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=ZoneInfo("America/New_York")
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)

# Usage
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
```

### Minimal Formatter for Production

```python
import logging

class MinimalFormatter(logging.Formatter):
    """Minimal formatter for production logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format with timestamp, level, and message only."""
        return f"{self.formatTime(record)} [{record.levelname}] {record.getMessage()}"

# Configure for production
if os.getenv("ENV") == "production":
    handler = logging.StreamHandler()
    handler.setFormatter(MinimalFormatter())
else:
    # Use colorful formatter for dev
    from scout_mcp.utils.console import ColorfulFormatter
    handler = logging.StreamHandler()
    handler.setFormatter(ColorfulFormatter())
```

## Testing Middleware

### Test Fixture Setup

```python
import pytest
from unittest.mock import MagicMock, AsyncMock
from scout_mcp.middleware import LoggingMiddleware

@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    return MagicMock()

@pytest.fixture
def mock_context():
    """Create a mock middleware context."""
    context = MagicMock()
    context.method = "tools/call"
    context.message = MagicMock()
    context.message.name = "scout"
    context.message.arguments = {"target": "tootie:/etc"}
    return context

@pytest.fixture
def logging_middleware(mock_logger):
    """Create logging middleware with mock logger."""
    return LoggingMiddleware(logger=mock_logger)
```

### Testing Logging Behavior

```python
@pytest.mark.asyncio
async def test_middleware_logs_requests(logging_middleware, mock_context, mock_logger):
    """Test that middleware logs requests."""
    call_next = AsyncMock(return_value="result")

    await logging_middleware.on_call_tool(mock_context, call_next)

    # Verify logging calls
    assert mock_logger.info.call_count >= 1

    # Check log content
    all_calls = str(mock_logger.info.call_args_list)
    assert ">>> TOOL" in all_calls
    assert "scout" in all_calls
```

### Testing Error Handling

```python
@pytest.mark.asyncio
async def test_middleware_handles_errors(error_middleware, mock_context):
    """Test error handling and statistics."""
    call_next = AsyncMock(side_effect=ValueError("test error"))

    # Should re-raise exception
    with pytest.raises(ValueError, match="test error"):
        await error_middleware.on_message(mock_context, call_next)

    # Should track error
    stats = error_middleware.get_error_stats()
    assert stats["ValueError"] == 1
```

### Testing Timing Accuracy

```python
import asyncio
import pytest

@pytest.mark.asyncio
async def test_timing_middleware_accuracy(timing_middleware, mock_context):
    """Test that timing measurements are accurate."""

    async def slow_handler(ctx):
        await asyncio.sleep(0.1)  # 100ms
        return "result"

    await timing_middleware.on_request(mock_context, slow_handler)

    # Timing should be around 100ms (with some tolerance)
    # Check via logger mock or timing stats
```

## Environment Configuration Examples

### Development Configuration

```bash
# .env.development
SCOUT_LOG_LEVEL=DEBUG
SCOUT_LOG_COLORS=true
SCOUT_LOG_PAYLOADS=true
SCOUT_SLOW_THRESHOLD_MS=500
SCOUT_INCLUDE_TRACEBACK=true
SCOUT_TRANSPORT=http
SCOUT_HTTP_HOST=127.0.0.1
SCOUT_HTTP_PORT=8000
```

### Production Configuration

```bash
# .env.production
SCOUT_LOG_LEVEL=INFO
SCOUT_LOG_COLORS=false
SCOUT_LOG_PAYLOADS=false
SCOUT_SLOW_THRESHOLD_MS=2000
SCOUT_INCLUDE_TRACEBACK=false
SCOUT_TRANSPORT=http
SCOUT_HTTP_HOST=0.0.0.0
SCOUT_HTTP_PORT=8000
```

### Testing Configuration

```bash
# .env.test
SCOUT_LOG_LEVEL=WARNING
SCOUT_LOG_COLORS=false
SCOUT_LOG_PAYLOADS=false
SCOUT_SLOW_THRESHOLD_MS=10000  # High threshold for tests
SCOUT_INCLUDE_TRACEBACK=true
```

## Integration Patterns

### Adding Middleware to Existing Server

```python
from scout_mcp.server import mcp
from scout_mcp.middleware import DetailedTimingMiddleware

# Add middleware after server creation
detailed_timing = DetailedTimingMiddleware(slow_threshold_ms=250.0)
mcp.add_middleware(detailed_timing)

# Now all requests will be tracked with detailed statistics
```

### Conditional Middleware Loading

```python
import os
from scout_mcp.server import FastMCP
from scout_mcp.middleware import (
    ErrorHandlingMiddleware,
    LoggingMiddleware,
    DetailedTimingMiddleware,
)

def configure_middleware(server: FastMCP) -> None:
    """Configure middleware based on environment."""

    # Always add error handling
    server.add_middleware(ErrorHandlingMiddleware(
        include_traceback=os.getenv("ENV") != "production"
    ))

    # Add detailed timing in development
    if os.getenv("ENV") == "development":
        server.add_middleware(DetailedTimingMiddleware())

    # Always add logging
    server.add_middleware(LoggingMiddleware(
        include_payloads=os.getenv("SCOUT_LOG_PAYLOADS") == "true",
        slow_threshold_ms=float(os.getenv("SCOUT_SLOW_THRESHOLD_MS", "1000")),
    ))
```

### Accessing Middleware at Runtime

```python
from scout_mcp.server import mcp
from scout_mcp.middleware import DetailedTimingMiddleware

# Find specific middleware instance
timing_mw = next(
    (m for m in mcp.middleware if isinstance(m, DetailedTimingMiddleware)),
    None
)

if timing_mw:
    stats = timing_mw.get_timing_stats()
    print(f"Performance stats: {stats}")
```

## Advanced Patterns

### Request ID Tracking

```python
import uuid
from contextvars import ContextVar
from scout_mcp.middleware.base import ScoutMiddleware

request_id_var: ContextVar[str] = ContextVar("request_id")

class RequestIDMiddleware(ScoutMiddleware):
    """Middleware that adds request IDs to all logs."""

    async def on_message(self, context, call_next):
        """Add request ID to context."""
        req_id = str(uuid.uuid4())[:8]
        request_id_var.set(req_id)

        self.logger.info(f"[{req_id}] Request started")

        try:
            result = await call_next(context)
            self.logger.info(f"[{req_id}] Request completed")
            return result
        finally:
            request_id_var.set("")
```

### Rate Limiting

```python
import time
from collections import defaultdict
from scout_mcp.middleware.base import ScoutMiddleware

class RateLimitMiddleware(ScoutMiddleware):
    """Middleware that enforces rate limits."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        super().__init__()
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: defaultdict[str, list[float]] = defaultdict(list)

    async def on_message(self, context, call_next):
        """Check rate limit before processing."""
        client_id = context.source  # Or extract from context
        now = time.time()

        # Clean old requests
        self._requests[client_id] = [
            ts for ts in self._requests[client_id]
            if now - ts < self.window_seconds
        ]

        # Check limit
        if len(self._requests[client_id]) >= self.max_requests:
            self.logger.warning(f"Rate limit exceeded for {client_id}")
            raise Exception("Rate limit exceeded")

        # Record request
        self._requests[client_id].append(now)

        return await call_next(context)
```

### Caching Middleware

```python
import hashlib
import json
from scout_mcp.middleware.base import ScoutMiddleware

class CacheMiddleware(ScoutMiddleware):
    """Middleware that caches tool results."""

    def __init__(self, ttl_seconds: int = 300):
        super().__init__()
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[float, Any]] = {}

    def _cache_key(self, tool_name: str, args: dict) -> str:
        """Generate cache key from tool name and arguments."""
        data = json.dumps({"tool": tool_name, "args": args}, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    async def on_call_tool(self, context, call_next):
        """Check cache before executing tool."""
        import time

        tool_name = getattr(context.message, "name", "")
        args = getattr(context.message, "arguments", {})

        cache_key = self._cache_key(tool_name, args)

        # Check cache
        if cache_key in self._cache:
            timestamp, result = self._cache[cache_key]
            if time.time() - timestamp < self.ttl_seconds:
                self.logger.debug(f"Cache hit for {tool_name}")
                return result

        # Execute and cache
        result = await call_next(context)
        self._cache[cache_key] = (time.time(), result)

        return result
```

# Scout MCP Middleware and Logging Implementation - Research Analysis

## Summary

Scout MCP implements a sophisticated middleware stack with unified logging, timing, and error handling. The system uses a custom colorful console formatter with EST timestamps and provides comprehensive request/response tracking. Middleware is built on FastMCP's base `Middleware` class with specialized hooks for different MCP operation types (tools, resources, prompts). The architecture separates concerns cleanly: ErrorHandling catches exceptions, LoggingMiddleware provides integrated timing and request tracking, and a custom ColorfulFormatter delivers rich console output with ANSI colors and intelligent message highlighting.

## Key Components

### Middleware Stack
- `/mnt/cache/code/scout_mcp/scout_mcp/middleware/base.py` - Base `ScoutMiddleware` class extending FastMCP's `Middleware`
- `/mnt/cache/code/scout_mcp/scout_mcp/middleware/errors.py` - `ErrorHandlingMiddleware` for exception handling and statistics
- `/mnt/cache/code/scout_mcp/scout_mcp/middleware/timing.py` - Two timing implementations: basic and detailed with statistics
- `/mnt/cache/code/scout_mcp/scout_mcp/middleware/logging.py` - Unified `LoggingMiddleware` with integrated timing
- `/mnt/cache/code/scout_mcp/scout_mcp/middleware/__init__.py` - Public exports

### Logging Infrastructure
- `/mnt/cache/code/scout_mcp/scout_mcp/utils/console.py` - Custom `ColorfulFormatter` and `MCPRequestFormatter` for rich console output
- `/mnt/cache/code/scout_mcp/scout_mcp/server.py` - Logging configuration in `_configure_logging()` at module load time
- `/mnt/cache/code/scout_mcp/scout_mcp/__main__.py` - Additional logging setup for direct execution

### Integration Points
- `/mnt/cache/code/scout_mcp/scout_mcp/server.py:387-413` - `configure_middleware()` function wires middleware to FastMCP
- `/mnt/cache/code/scout_mcp/scout_mcp/server.py:41-90` - `_configure_logging()` initializes logging at import time
- `/mnt/cache/code/scout_mcp/scout_mcp/config.py:34-86` - Environment variable parsing for logging/transport config

## Implementation Patterns

### Middleware Composition Pattern
**How it works**: Middleware is added in specific order using `server.add_middleware()`, creating an onion-like execution model where first-added middleware runs innermost (closest to handler).

```python
# From server.py:405-413
server.add_middleware(ErrorHandlingMiddleware(include_traceback=include_traceback))
server.add_middleware(LoggingMiddleware(include_payloads=log_payloads, slow_threshold_ms=slow_threshold))
```

**Execution flow**:
```
Request  → LoggingMiddleware → ErrorHandlingMiddleware → Handler
Response ← LoggingMiddleware ← ErrorHandlingMiddleware ← Handler
```

This ensures errors are caught before logging completes, and timing measurements include error handling.

### Hook-Based Architecture
**How it works**: Middleware overrides specific hooks for different MCP operations (`on_call_tool`, `on_read_resource`, `on_list_tools`, etc.) plus a generic `on_message` fallback.

**Example from logging.py:78-131**:
```python
async def on_call_tool(self, context: MiddlewareContext, call_next: Any) -> Any:
    """Log tool calls with name, arguments, and timing."""
    start = time.perf_counter()
    tool_name = getattr(context.message, "name", "unknown")
    args = getattr(context.message, "arguments", None)

    self.logger.info(">>> TOOL: %s%s", tool_name, self._format_args(args))

    try:
        result = await call_next(context)
        duration_ms = (time.perf_counter() - start) * 1000
        # Log completion with timing
        return result
    except Exception as e:
        # Log error with timing
        raise
```

**Available hooks** (from FastMCP):
- `on_call_tool` - Tool execution
- `on_read_resource` - Resource reads
- `on_get_prompt` - Prompt retrieval
- `on_list_tools` / `on_list_resources` / `on_list_prompts` - List operations
- `on_message` - Catch-all for other operations
- `on_request` - Generic request handler (used by TimingMiddleware)

### Unified Logging + Timing Pattern
**How it works**: LoggingMiddleware combines timing and logging into single middleware, eliminating duplicate timing measurements and providing cleaner output.

**Key insight from middleware/logging.py:22-23**:
```python
# This middleware combines logging AND timing for cleaner output.
# Use this INSTEAD of TimingMiddleware for a unified log format.
```

**Benefits**:
- Single timing measurement per operation (not doubled)
- Consistent log format with duration in every message
- Slow request warnings integrated with logging level
- Reduced middleware stack overhead

### Colorful Console Formatter Pattern
**How it works**: Custom `logging.Formatter` subclass applies ANSI color codes based on log level, component name, and message content.

**From utils/console.py:60-132**:
- EST timezone for all timestamps (`ZoneInfo("America/New_York")`)
- Fixed-width columns for timestamp, level, component
- Component-specific colors (server=cyan, pool=magenta, tools=blue)
- Message pattern highlighting (URIs, durations, SSH connections)
- `MCPRequestFormatter` extends with visual indicators (`>>>`, `<<<`, `!!`, etc.)

**Color mappings**:
```python
LEVEL_COLORS = {
    "DEBUG": bright_black,
    "INFO": bright_green,
    "WARNING": bright_yellow,
    "ERROR": bright_red,
    "CRITICAL": bg_red + white + bold
}

COMPONENT_COLORS = {
    "scout_mcp.server": bright_cyan,
    "scout_mcp.services.pool": bright_magenta,
    "scout_mcp.tools.scout": bright_blue,
    # ...
}
```

### Module-Time Logging Configuration
**How it works**: Logging is configured at module import time (not runtime) to ensure it's ready before any loggers are used.

**From server.py:89-90**:
```python
# Configure logging at module load time
_configure_logging()
```

This happens when `scout_mcp.server` is imported, ensuring:
1. Logging works regardless of entry point
2. Third-party loggers (uvicorn, asyncssh) are quieted
3. Custom formatter is applied before any log messages
4. No duplicate handlers from multiple imports

### Error Statistics Tracking
**How it works**: ErrorHandlingMiddleware maintains a counter dict of exception types for debugging.

**From middleware/errors.py:46-58**:
```python
self._error_counts: dict[str, int] = defaultdict(int)

async def on_message(self, context, call_next):
    try:
        return await call_next(context)
    except Exception as e:
        error_type = type(e).__name__
        self._error_counts[error_type] += 1
        # Log and re-raise
```

**API**:
- `get_error_stats()` → `{"ValueError": 3, "SSHException": 1}`
- `reset_stats()` - Clear counters

### Environment-Driven Configuration
**How it works**: All middleware behavior is configurable via environment variables, parsed in `server.py:configure_middleware()`.

**Environment variables** (from server.py:392-403):
```bash
SCOUT_LOG_LEVEL=DEBUG           # Overall log level
SCOUT_LOG_COLORS=true           # Enable/disable ANSI colors
SCOUT_LOG_PAYLOADS=true         # Log request/response payloads
SCOUT_SLOW_THRESHOLD_MS=1000    # Slow request warning threshold
SCOUT_INCLUDE_TRACEBACK=true    # Include full tracebacks in errors
```

**Backward compatibility**: Legacy `MCP_CAT_*` prefixes still supported (config.py:44-53).

## Considerations

### Middleware Order is Critical
The order middleware is added determines execution order. **ErrorHandlingMiddleware MUST be added first** (runs innermost) to catch exceptions before they escape the middleware stack. LoggingMiddleware is added second to wrap everything with timing.

**From tests/test_middleware/test_integration.py:18-30**:
```python
# Order: ErrorHandling first (runs last on way in, first on way out)
# Then Logging (logs at outermost layer, includes timing)
assert middleware_types[0] == "ErrorHandlingMiddleware"
assert middleware_types[1] == "LoggingMiddleware"
```

Reversing this order would cause errors to escape before being logged.

### LoggingMiddleware Replaces TimingMiddleware
The codebase includes **two timing implementations**:
1. **TimingMiddleware** - Basic timing with `on_request` hook
2. **DetailedTimingMiddleware** - Per-operation statistics
3. **LoggingMiddleware** - Unified logging + timing

**Current usage**: Only LoggingMiddleware is active (server.py:406-413). TimingMiddleware exists for reference but is not used to avoid duplicate measurements.

**If you need statistics**: Use DetailedTimingMiddleware's `get_timing_stats()` API for performance analysis.

### Logger Propagation Must Be Disabled
To prevent duplicate log messages and maintain custom formatting:

**From server.py:64, 81**:
```python
scout_logger.propagate = False  # Don't propagate to root
lg.propagate = False            # Third-party loggers
```

This ensures:
- Scout logs only use custom formatter
- Third-party libraries (uvicorn, asyncssh) don't spam output
- No duplicate messages from parent/child logger relationships

### TTY Detection for Color Auto-Disable
Colors are automatically disabled if stderr is not a TTY:

**From server.py:51-53**:
```python
if not sys.stderr.isatty():
    use_colors = False
```

This prevents ANSI codes in log files or when output is piped. Override with `SCOUT_LOG_COLORS=false`.

### Message Highlighting Edge Cases
The ColorfulFormatter applies regex patterns to highlight URIs, durations, SSH connections. **Be careful with complex log messages** that might match multiple patterns - the regex order matters.

**From utils/console.py:133-193**:
- URI highlighting: `\w+://[^\s]+`
- Duration highlighting: `\d+\.?\d*ms`
- SSH patterns: `\w+@[\w\.\-]+:\d+`

These run on **every log message**, so complex patterns could impact performance on high-volume logging.

### Middleware Context Access Patterns
Middleware receives `MiddlewareContext` with different attributes depending on the operation:

**Tool calls** (logging.py:85-86):
```python
tool_name = getattr(context.message, "name", "unknown")
args = getattr(context.message, "arguments", None)
```

**Resource reads** (logging.py:140):
```python
uri = getattr(context.message, "uri", "unknown")
```

**Always use `getattr` with defaults** to handle missing attributes gracefully.

### Error Re-Raising is Required
ErrorHandlingMiddleware logs exceptions but **always re-raises** them (errors.py:115-116):

```python
# Re-raise the original exception
raise
```

This allows:
1. Statistics tracking without swallowing errors
2. Error callbacks for custom handling
3. Proper error propagation to MCP clients

**Never return error messages from middleware** - let FastMCP handle error serialization.

### Payload Logging Privacy Concerns
When `SCOUT_LOG_PAYLOADS=true`, request arguments and responses are logged at DEBUG level. This could expose:
- File contents from resource reads
- SSH paths and commands
- Sensitive configuration data

**Use carefully in production**. The `max_payload_length` parameter (default 1000) truncates output but doesn't prevent logging sensitive data.

## Next Steps

### For Feature Implementation
1. **New middleware**: Extend `ScoutMiddleware` base class for common logger setup
2. **Operation-specific logic**: Override appropriate hook (`on_call_tool`, `on_read_resource`, etc.)
3. **Registration**: Add to `configure_middleware()` in proper order
4. **Testing**: Follow pattern in `tests/test_middleware/` with mock contexts

### For Logging Customization
1. **New formatters**: Extend `ColorfulFormatter` or create new `logging.Formatter`
2. **Component colors**: Add to `COMPONENT_COLORS` dict in `utils/console.py`
3. **Message patterns**: Add regex highlighting in `_highlight_message()`
4. **Log levels**: Use environment variables, no code changes needed

### For Performance Analysis
1. **Use DetailedTimingMiddleware**: Swap in for LoggingMiddleware temporarily
2. **Collect stats**: Call `middleware.get_timing_stats()` after load test
3. **Analyze by operation**: Stats keyed as `"tool:scout"`, `"resource:scout://host/path"`
4. **Reset between runs**: Call `middleware.reset_stats()`

### For Debugging
1. **Enable full tracebacks**: `SCOUT_INCLUDE_TRACEBACK=true`
2. **Enable payload logging**: `SCOUT_LOG_PAYLOADS=true` (DEBUG level)
3. **Lower slow threshold**: `SCOUT_SLOW_THRESHOLD_MS=100` to catch more slow ops
4. **Check error stats**: Access `ErrorHandlingMiddleware.get_error_stats()` at runtime

### Integration with New Transports
The middleware stack is transport-agnostic (works with HTTP and STDIO). When adding new transports:
1. No middleware changes needed
2. Logging configuration in `_configure_logging()` applies to all transports
3. Test with `SCOUT_TRANSPORT=<new_transport>`
4. Ensure `sys.stderr.isatty()` behavior is correct for new transport context

### Observability Improvements
Current limitations and opportunities:
1. **No structured logging**: All logs are text-based, could add JSON formatter
2. **No metrics export**: Timing stats only available via code, could expose via endpoint
3. **No distributed tracing**: Each request is isolated, could add trace IDs
4. **No log aggregation**: Logs to stderr only, could add remote logging sink
5. **Error callbacks**: Underutilized feature, could integrate error tracking service

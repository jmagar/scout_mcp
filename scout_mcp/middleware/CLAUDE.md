# middleware/

Request/response processing for logging, timing, and error handling.

## Classes

### ScoutMiddleware (`base.py`)
Base class for all middleware. Extends `fastmcp.server.middleware.Middleware`.

### TimingMiddleware (`timing.py`)
```python
class TimingMiddleware(ScoutMiddleware):
    def __init__(self, slow_threshold_ms: float = 1000.0)
```
- Logs all requests with duration
- Warns on slow requests (> threshold)
- Logs failed requests

### DetailedTimingMiddleware (`timing.py`)
```python
class DetailedTimingMiddleware(ScoutMiddleware):
    def get_timing_stats() -> dict[str, TimingStats]
    def reset_stats() -> None
```
- Per-operation statistics: count, total, min, max, avg
- Operation keys: `"tool:scout"`, `"resource:scout://host/path"`

### ErrorHandlingMiddleware (`errors.py`)
```python
class ErrorHandlingMiddleware(ScoutMiddleware):
    def __init__(self, include_traceback: bool = False, error_callback=None)
    def get_error_stats() -> dict[str, int]
    def reset_stats() -> None
```
- Catches and logs exceptions
- Tracks error counts by type
- Optional traceback inclusion
- Always re-raises after logging

### LoggingMiddleware (`logging.py`)
```python
class LoggingMiddleware(ScoutMiddleware):
    def __init__(self, log_payloads: bool = False, max_payload_length: int = 1000)
```
- Request/response logging
- Optional payload logging (DEBUG level)
- Truncates large payloads

## Middleware Stack

**Order in server.py:**
```
Request  → Logging → Timing → ErrorHandling → Handler
Response ← Logging ← Timing ← ErrorHandling ← Handler
```

ErrorHandling is outermost (catches all exceptions).

## Configuration

Environment variables:
```bash
SCOUT_LOG_PAYLOADS=true        # Enable payload logging
SCOUT_SLOW_THRESHOLD_MS=1000   # Slow request threshold
SCOUT_INCLUDE_TRACEBACK=true   # Include tracebacks
```

## Import

```python
from scout_mcp.middleware import (
    ScoutMiddleware,
    TimingMiddleware,
    DetailedTimingMiddleware,
    ErrorHandlingMiddleware,
    LoggingMiddleware,
)
```

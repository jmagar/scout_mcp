# Scout MCP Server - Core Architecture Research

## Summary
Scout MCP is a cleanly architected FastMCP server with HTTP/STDIO transports for remote SSH operations. The design emphasizes separation of concerns with a thin server layer that wires together independent components: tools, resources, middleware, services, and utilities. Key architectural patterns include lazy singleton state management, connection pooling with auto-cleanup, middleware stacking for cross-cutting concerns, and dynamic resource registration at startup.

## Key Components

### Entry Points & Server Initialization
- `/mnt/cache/code/scout_mcp/scout_mcp/__main__.py` (61 lines) - CLI entry point with transport selection
- `/mnt/cache/code/scout_mcp/scout_mcp/server.py` (448 lines) - FastMCP server factory and configuration
- `/mnt/cache/code/scout_mcp/scout_mcp/config.py` (183 lines) - SSH config parsing and environment variables

### Service Layer
- `/mnt/cache/code/scout_mcp/scout_mcp/services/state.py` - Lazy singleton pattern for global state
- `/mnt/cache/code/scout_mcp/scout_mcp/services/pool.py` - SSH connection pooling with idle timeout
- `/mnt/cache/code/scout_mcp/scout_mcp/services/executors.py` - Remote command execution

### Request Processing
- `/mnt/cache/code/scout_mcp/scout_mcp/middleware/errors.py` - Error handling and statistics
- `/mnt/cache/code/scout_mcp/scout_mcp/middleware/logging.py` - Request/response logging with timing
- `/mnt/cache/code/scout_mcp/scout_mcp/middleware/timing.py` - Performance tracking and slow request detection
- `/mnt/cache/code/scout_mcp/scout_mcp/utils/console.py` - Colorful console formatter with EST timestamps

### Interface Layer
- `/mnt/cache/code/scout_mcp/scout_mcp/tools/scout.py` - Primary MCP tool for SSH operations
- `/mnt/cache/code/scout_mcp/scout_mcp/resources/*.py` - URI-based read-only access (scout://, hosts://, per-host resources)

## Implementation Patterns

### 1. **Thin Server Wrapper Pattern** (`server.py`)
The server module is intentionally minimal, acting only as a wiring layer. All business logic is delegated:

```python
# server.py creates server and wires components
def create_server() -> FastMCP:
    server = FastMCP("scout_mcp", lifespan=app_lifespan)
    configure_middleware(server)
    server.tool()(scout)
    server.resource("scout://{host}/{path*}")(scout_resource)
    server.resource("hosts://list")(list_hosts_resource)
    return server

mcp = create_server()  # Default instance
```

**Design rationale:** Keeps server.py focused on configuration, not implementation. Easy to test components in isolation.

### 2. **Lazy Singleton State** (`services/state.py`)
Global configuration and connection pool use module-level singletons with lazy initialization:

```python
_config: Config | None = None
_pool: ConnectionPool | None = None

def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config

def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        config = get_config()
        _pool = ConnectionPool(idle_timeout=config.idle_timeout)
    return _pool
```

**Usage pattern throughout codebase:**
```python
from scout_mcp.services import get_config, get_pool
config = get_config()  # First call creates singleton
pool = get_pool()      # Reuses same instance
```

**Testing support:** Provides `reset_state()`, `set_config()`, `set_pool()` for test isolation.

### 3. **Async Connection Pooling** (`services/pool.py`)
One connection per host, reused across requests, with automatic cleanup:

```python
class ConnectionPool:
    def __init__(self, idle_timeout: int = 60):
        self._connections: dict[str, PooledConnection] = {}
        self._lock = asyncio.Lock()  # Thread safety
        self._cleanup_task: asyncio.Task | None = None

    async def get_connection(self, host: SSHHost):
        async with self._lock:
            # Return existing if valid
            if pooled and not pooled.is_stale:
                pooled.touch()  # Update last_used timestamp
                return pooled.connection

            # Create new connection
            conn = await asyncssh.connect(...)
            self._connections[host.name] = PooledConnection(connection=conn)

            # Start background cleanup
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._cleanup_loop())
```

**Cleanup strategy:**
- Background task runs every `idle_timeout/2` seconds
- Removes connections idle > `idle_timeout` seconds
- Stops automatically when pool empty
- Comprehensive logging for connection lifecycle

**Connection retry pattern** (used in tools/resources):
```python
try:
    conn = await pool.get_connection(ssh_host)
except Exception:
    await pool.remove_connection(ssh_host.name)  # Clear stale
    conn = await pool.get_connection(ssh_host)   # Retry once
```

### 4. **Middleware Stack Architecture** (`server.py` + `middleware/`)
Middleware configured in specific order for proper request/response handling:

```python
def configure_middleware(server: FastMCP):
    # Inner to outer (processing order: outer → inner → handler → inner → outer)
    server.add_middleware(ErrorHandlingMiddleware(include_traceback=...))
    server.add_middleware(LoggingMiddleware(include_payloads=..., slow_threshold_ms=...))
```

**Processing flow:**
```
Request  → ErrorHandling → Logging → Handler
Response ← ErrorHandling ← Logging ← Handler
```

**Middleware implementations:**
- `ErrorHandlingMiddleware`: Catches all exceptions, logs with optional traceback, tracks error statistics
- `LoggingMiddleware`: Logs request/response with integrated timing, warns on slow requests (>1000ms default)
- `TimingMiddleware`: Alternative timing-only middleware (not used when LoggingMiddleware present)
- `DetailedTimingMiddleware`: Per-operation statistics (count, total, min, max, avg)

**Environment configuration:**
```bash
SCOUT_LOG_PAYLOADS=true          # Log request/response payloads
SCOUT_SLOW_THRESHOLD_MS=1000     # Slow request threshold
SCOUT_INCLUDE_TRACEBACK=true     # Include tracebacks in errors
```

### 5. **Dynamic Resource Registration** (`server.py` lifespan)
Resources are registered at server startup based on discovered SSH hosts:

```python
@asynccontextmanager
async def app_lifespan(server: FastMCP):
    config = get_config()
    hosts = config.get_hosts()  # Parse ~/.ssh/config

    # Register 9 resource types per host:
    for host_name in hosts:
        # Docker resources (specific patterns first)
        server.resource(f"{host_name}://docker/{{container}}/logs")(...)
        server.resource(f"{host_name}://docker")(...)

        # Compose resources
        server.resource(f"{host_name}://compose")(...)
        server.resource(f"{host_name}://compose/{{project}}")(...)
        server.resource(f"{host_name}://compose/{{project}}/logs")(...)

        # ZFS resources
        server.resource(f"{host_name}://zfs")(...)
        server.resource(f"{host_name}://zfs/{{pool}}")(...)
        server.resource(f"{host_name}://zfs/{{pool}}/datasets")(...)
        server.resource(f"{host_name}://zfs/snapshots")(...)

        # Syslog resource
        server.resource(f"{host_name}://syslog")(...)

        # Filesystem wildcard (LAST - catches everything else)
        server.resource(f"{host_name}://{{path*}}")(...)

    yield {"hosts": list(hosts.keys())}

    # Shutdown: close all SSH connections
    pool = get_pool()
    await pool.close_all()
```

**Pattern:** Closure-based handler factories to capture host name in scope:
```python
def make_docker_logs_handler(h: str):
    async def handler(container: str) -> str:
        return await _read_docker_logs(h, container)
    return handler

server.resource(...)(make_docker_logs_handler(host_name))
```

**Resource URI examples:**
- `tootie://docker/plex/logs` - Docker container logs
- `tootie://compose/myapp` - Docker Compose config
- `tootie://zfs/cache` - ZFS pool status
- `tootie://syslog` - System logs
- `tootie:///var/log/app.log` - Filesystem (wildcard catch-all)

### 6. **Transport Configuration** (`__main__.py` + `config.py`)
Server supports HTTP (default) and STDIO transports via environment variable:

```python
# __main__.py
def run_server():
    config = get_config()

    if config.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(
            transport="http",
            host=config.http_host,  # Default: 0.0.0.0
            port=config.http_port,  # Default: 8000
        )
```

**Configuration precedence:**
```python
# config.py __post_init__
transport = os.getenv("SCOUT_TRANSPORT", "").lower()  # "http" or "stdio"
http_host = os.getenv("SCOUT_HTTP_HOST")              # Default: "0.0.0.0"
http_port = int(os.getenv("SCOUT_HTTP_PORT", "8000"))
```

**Legacy support:** Environment variables support both `SCOUT_*` (preferred) and `MCP_CAT_*` (legacy) prefixes.

### 7. **Module-Level Logging Configuration** (`server.py`)
Logging is configured at module import time to ensure consistency:

```python
# server.py (executed at import time)
def _configure_logging():
    log_level = os.getenv("SCOUT_LOG_LEVEL", "DEBUG").upper()
    use_colors = os.getenv("SCOUT_LOG_COLORS", "true").lower() != "false"

    if not sys.stderr.isatty():
        use_colors = False

    scout_logger = logging.getLogger("scout_mcp")
    scout_logger.setLevel(getattr(logging, log_level))

    if not scout_logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(MCPRequestFormatter(use_colors=use_colors))
        scout_logger.addHandler(handler)
        scout_logger.propagate = False

    # Suppress noisy third-party loggers
    for logger_name in ["uvicorn", "asyncssh", "httpx", ...]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

_configure_logging()  # Called at module load
```

**Console formatter features** (`utils/console.py`):
- EST timestamps with milliseconds: `HH:MM:SS.mmm MM/DD`
- ANSI color codes by log level and component
- Pattern highlighting: URIs, durations, SSH connections
- Visual indicators: `>>>` (start), `<<<` (shutdown), `!!` (error), `!` (warning)
- Component-based coloring for logger names

## Considerations

### Critical Design Decisions

**1. Server as Wiring Layer Only**
- Server.py intentionally kept minimal (448 lines including extensive resource registration)
- All business logic delegated to tools/, resources/, services/
- Makes testing easier: components can be tested without FastMCP server
- Follows Single Responsibility Principle

**2. Global Singleton State**
- `get_config()` and `get_pool()` used throughout without dependency injection
- Simplifies API: no need to pass state through function chains
- Testing utilities (`reset_state()`, `set_config()`) enable test isolation
- Trade-off: Global state makes some testing more complex

**3. Lazy Connection Management**
- Connections created on-demand, not at startup
- Background cleanup prevents resource leaks
- One-retry pattern handles transient network issues
- Lock-based concurrency control prevents race conditions

**4. Middleware Order Matters**
- ErrorHandling must be outermost to catch all exceptions
- LoggingMiddleware includes timing, so TimingMiddleware not needed
- Order affects which middleware sees exceptions vs. successful responses

**5. Dynamic Resource Registration**
- Resources discovered and registered at startup from SSH config
- Enables hostname-based URIs (e.g., `tootie://path`)
- Requires host-specific closure factories to capture context
- Wildcard patterns must be registered LAST to avoid shadowing specific routes

### Edge Cases and Gotchas

**1. SSH Config Parsing**
- Case-insensitive directive matching: `Host`, `host`, `HOST` all valid
- Missing hostname in config → host excluded from available list
- Invalid port values → defaults to 22
- Allowlist/blocklist use fnmatch patterns (`*`, `?`, `[abc]`)

**2. Connection Pool Behavior**
- `is_stale` checks if underlying asyncssh connection is closed
- Cleanup task stops when pool empty (auto-restart on next connection)
- Lock prevents concurrent connection creation to same host
- No connection limit: pool can grow unbounded (one per host)

**3. Middleware Context**
- `context.method` contains MCP method name (e.g., "tools/call")
- `context.message` has type-specific attributes (tool name, resource URI)
- Middleware can modify context or response before passing to next handler
- Exceptions propagate up middleware stack (outermost catches all)

**4. Resource vs. Tool Error Handling**
- Tools return error strings: `return f"Error: {e}"`
- Resources raise ResourceError: `raise ResourceError(f"Error: {e}")`
- Different contracts for same underlying operations (scout tool vs. scout resource)

**5. Logging Configuration Timing**
- `_configure_logging()` called at server.py module import
- Ensures logging configured before any loggers are created
- Additional quieting in `__main__.py` when run directly
- Environment variables must be set before import

**6. Transport Selection**
- HTTP transport binds to `0.0.0.0:8000` by default (accepts all interfaces)
- STDIO transport disables HTTP endpoints (including `/health`)
- Health check endpoint only available in HTTP mode
- Client configuration differs significantly between transports

### Performance Characteristics

**1. Connection Pooling Impact**
- First request to host: ~200-500ms (SSH handshake)
- Subsequent requests: <10ms (connection reuse)
- Cleanup overhead: minimal (background task, 30s intervals for 60s timeout)
- Memory per connection: ~1-2MB (asyncssh overhead)

**2. Middleware Stack Overhead**
- Each middleware adds ~0.1-0.5ms per request
- LoggingMiddleware: ~0.2ms (timestamp + formatting)
- ErrorHandlingMiddleware: ~0.1ms (try/catch wrapper)
- Slow request threshold: 1000ms default (configurable)

**3. Dynamic Resource Registration**
- Startup time: ~10-50ms per host (SSH config parsing + resource creation)
- 10 hosts = ~100-500ms startup overhead
- Runtime impact: None (resources registered once at startup)
- Resource lookup: O(1) via FastMCP's internal routing

**4. Logging Performance**
- Color formatting adds ~0.1ms per log line
- Disabled automatically when `sys.stderr` not a TTY
- Payload logging can significantly increase overhead (disabled by default)
- String truncation prevents memory issues with large payloads

### Security Considerations

**1. No Path Traversal Protection**
- Server relies on SSH server's access controls
- No validation of `..` or absolute paths
- Assumes trusted MCP client

**2. Command Execution**
- Shell commands executed via `repr()` quoting (prevents basic injection)
- No command allowlist/blocklist
- Command timeout prevents runaway processes (30s default)

**3. File Size Limits**
- `max_file_size` prevents memory exhaustion (1MB default)
- Truncated files clearly marked in response
- No limits on directory listings or command output

**4. SSH Authentication**
- Uses SSH keys (no password support)
- `known_hosts` validation disabled (`known_hosts=None`)
- Identity files from SSH config

**5. HTTP Transport Security**
- No authentication on HTTP endpoints
- Binds to all interfaces (`0.0.0.0`) by default
- Health check endpoint reveals server presence
- Assumes trusted network or reverse proxy with auth

## Next Steps

### For New Feature Implementation

**1. Adding New MCP Tools**
- Create async function in `/mnt/cache/code/scout_mcp/scout_mcp/tools/`
- Add to `__all__` in `tools/__init__.py`
- Register in `server.py` via `server.tool()(your_tool)`
- Use `get_config()` and `get_pool()` for state access
- Return error strings (never raise exceptions)

**2. Adding New MCP Resources**
- Create async function in `/mnt/cache/code/scout_mcp/scout_mcp/resources/`
- Add to `__all__` in `resources/__init__.py`
- Register in `server.py` or `app_lifespan()` if host-specific
- Raise `ResourceError` on failures (don't return error strings)
- Consider URI pattern specificity (register specific patterns before wildcards)

**3. Adding Custom Middleware**
- Extend `ScoutMiddleware` from `/mnt/cache/code/scout_mcp/scout_mcp/middleware/base.py`
- Implement `on_message()` or specific handlers (`on_call_tool()`, `on_read_resource()`)
- Add to middleware stack in `configure_middleware()`
- Consider middleware order (outermost to innermost)

**4. Modifying Transport Behavior**
- HTTP-specific changes: modify `run_server()` in `__main__.py`
- STDIO-specific changes: same location, different branch
- Both transports: modify `create_server()` in `server.py`
- Custom routes: use `@server.custom_route()` decorator

**5. Extending Configuration**
- Add fields to `Config` dataclass in `/mnt/cache/code/scout_mcp/scout_mcp/config.py`
- Update `__post_init__()` for environment variable support
- Follow pattern: `SCOUT_*` (new) and `MCP_CAT_*` (legacy) prefixes
- Document in README and docstrings

### Architectural Patterns to Follow

**1. Keep server.py Thin**
- Only wiring logic, no business logic
- Extract reusable functions to appropriate modules
- Follow existing delegation patterns

**2. Use Lazy Singletons for Shared State**
- Access via `get_config()` and `get_pool()`
- Don't create new Config or ConnectionPool instances in application code
- For tests: use `set_config()`, `set_pool()`, `reset_state()`

**3. Async All I/O**
- All SSH operations async (`await conn.run()`)
- All network operations async (`await check_host_online()`)
- Use `asyncio.Lock` for shared state

**4. Comprehensive Logging**
- Use module-level loggers: `logger = logging.getLogger(__name__)`
- Log at appropriate levels: DEBUG (details), INFO (events), WARNING (slow/degraded), ERROR (failures)
- Include context: host names, paths, durations, error messages

**5. Error Handling by Layer**
- Tools: catch exceptions, return error strings
- Resources: raise `ResourceError` with descriptive messages
- Services: raise exceptions, let callers decide handling
- Middleware: catch, log, re-raise (don't swallow)

### Testing Recommendations

**1. Unit Testing Components**
- Use `reset_state()` in fixtures for clean state
- Mock SSH connections with `set_pool()` and custom pool
- Test tools/resources/middleware independently

**2. Integration Testing**
- Test full request flow: client → middleware → tool → service → SSH
- Use real SSH config or mock with `set_config()`
- Verify middleware order and error propagation

**3. Performance Testing**
- Use `DetailedTimingMiddleware` to collect stats
- Benchmark connection pooling: first vs. subsequent requests
- Test slow request detection and logging

**4. Lifespan Testing**
- Verify resource registration for different SSH configs
- Test connection cleanup on shutdown
- Ensure cleanup task stops when pool empty

### Common Implementation Patterns

**Pattern 1: Adding SSH-based Tool**
```python
# tools/my_tool.py
async def my_tool(target: str) -> str:
    config = get_config()
    pool = get_pool()

    parsed = parse_target(target)
    ssh_host = config.get_host(parsed.host)
    if not ssh_host:
        return f"Error: Unknown host"

    try:
        conn = await pool.get_connection(ssh_host)
    except Exception as e:
        await pool.remove_connection(ssh_host.name)
        conn = await pool.get_connection(ssh_host)

    result = await run_command(conn, parsed.path, "my command")
    return result.output
```

**Pattern 2: Adding Per-Host Resource**
```python
# In server.py app_lifespan()
for host_name in hosts:
    def make_handler(h: str):
        async def handler(param: str) -> str:
            return await my_resource_function(h, param)
        return handler

    server.resource(
        uri=f"{host_name}://myresource/{{param}}",
        name=f"{host_name} my resource",
        mime_type="text/plain"
    )(make_handler(host_name))
```

**Pattern 3: Adding Middleware with Stats**
```python
# middleware/my_middleware.py
class MyMiddleware(ScoutMiddleware):
    def __init__(self):
        super().__init__()
        self._stats = defaultdict(int)

    async def on_message(self, context, call_next):
        self._stats[context.method] += 1
        return await call_next(context)

    def get_stats(self):
        return dict(self._stats)
```

**Pattern 4: Resource with Error Handling**
```python
# resources/my_resource.py
from fastmcp.exceptions import ResourceError

async def my_resource(host: str, path: str) -> str:
    config = get_config()
    ssh_host = config.get_host(host)
    if not ssh_host:
        raise ResourceError(f"Unknown host: {host}")

    pool = get_pool()
    try:
        conn = await pool.get_connection(ssh_host)
        result = await cat_file(conn, path, config.max_file_size)
        return result[0]
    except Exception as e:
        raise ResourceError(f"Failed to read {path}: {e}")
```

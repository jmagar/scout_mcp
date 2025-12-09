# Security Fixes and Refactoring - Current Implementation Research

## Summary
This research document analyzes the scout_mcp codebase to understand current implementation patterns for 11 security and refactoring issues. The codebase uses `repr()` for command quoting, disables SSH host key verification, has duplicated connection retry logic across 8 files, and lacks API authentication and rate limiting.

## Key Components

### Critical Security Files
- `/mnt/cache/code/scout_mcp/scout_mcp/services/executors.py` - SSH command execution (643 lines)
- `/mnt/cache/code/scout_mcp/scout_mcp/services/pool.py` - Connection pooling (171 lines)
- `/mnt/cache/code/scout_mcp/scout_mcp/server.py` - FastMCP server setup (448 lines)
- `/mnt/cache/code/scout_mcp/scout_mcp/tools/scout.py` - Main tool interface (146 lines)
- `/mnt/cache/code/scout_mcp/scout_mcp/utils/parser.py` - URI parsing (41 lines)
- `/mnt/cache/code/scout_mcp/pyproject.toml` - Dependencies and config

### Resource Files with Retry Pattern
- `/mnt/cache/code/scout_mcp/scout_mcp/resources/scout.py` (92 lines)
- `/mnt/cache/code/scout_mcp/scout_mcp/resources/docker.py` (116 lines)
- `/mnt/cache/code/scout_mcp/scout_mcp/resources/compose.py` (~150 lines estimated)
- `/mnt/cache/code/scout_mcp/scout_mcp/resources/zfs.py`
- `/mnt/cache/code/scout_mcp/scout_mcp/resources/syslog.py`

## Implementation Patterns

### 1. Command Injection (scout_mcp-zge)
**Location:** `/mnt/cache/code/scout_mcp/scout_mcp/services/executors.py:161`

**Current Implementation:**
```python
async def run_command(
    conn: "asyncssh.SSHClientConnection",
    working_dir: str,
    command: str,
    timeout: int,
) -> CommandResult:
    """Execute arbitrary command in working directory."""
    full_command = f"cd {working_dir!r} && timeout {timeout} {command}"
    result = await conn.run(full_command, check=False)
```

**Pattern Used:** `repr()` for quoting (the `!r` format spec)
- Used consistently across all executors: `stat_path` (line 17), `cat_file` (line 53), `ls_dir` (line 87), `tree_dir` (lines 124, 137), `run_command` (line 161)
- Also used in Docker/Compose/ZFS executors throughout the file

**Risk:** `repr()` is NOT safe for shell escaping. Example:
```python
working_dir = "/tmp'; rm -rf / #"
# repr() produces: "'/tmp'; rm -rf / #'"
# Shell sees: cd '/tmp'; rm -rf / #' && command
# This DOES NOT prevent injection!
```

**No shlex usage found:** Search confirmed no `shlex.quote()` imports anywhere in codebase.

### 2. SSH Host Key Verification (scout_mcp-7di)
**Location:** `/mnt/cache/code/scout_mcp/scout_mcp/services/pool.py:67`

**Current Implementation:**
```python
async def get_connection(self, host: "SSHHost") -> asyncssh.SSHClientConnection:
    """Get or create a connection to the host."""
    # ... pool check logic ...

    # Create new connection
    client_keys = [host.identity_file] if host.identity_file else None
    conn = await asyncssh.connect(
        host.hostname,
        port=host.port,
        username=host.user,
        known_hosts=None,  # ⚠️ SECURITY ISSUE
        client_keys=client_keys,
    )
```

**Impact:**
- Disables ALL host key verification
- Vulnerable to MITM attacks
- No certificate pinning or validation

**Test Dependency:** `/mnt/cache/code/scout_mcp/tests/test_pool.py:40` also uses `known_hosts=None`

### 3. asyncssh Version (scout_mcp-vn7)
**Location:** `/mnt/cache/code/scout_mcp/pyproject.toml:9`

**Current Constraint:**
```toml
dependencies = [
    "fastmcp>=2.0.0",
    "asyncssh>=2.14.0",  # Minimum version only
]
```

**Risk:** No upper bound allows any future version (could include breaking changes or CVEs)

**Latest Version Check Required:** Need to verify current latest stable version and any known vulnerabilities.

### 4. API Authentication (scout_mcp-0wx)
**Location:** `/mnt/cache/code/scout_mcp/scout_mcp/server.py`

**Current Implementation:**
```python
def create_server() -> FastMCP:
    """Create and configure the MCP server with all middleware and resources."""
    server = FastMCP(
        "scout_mcp",
        lifespan=app_lifespan,
    )

    configure_middleware(server)  # Only logging/timing/error handling
    server.tool()(scout)
    server.resource("scout://{host}/{path*}")(scout_resource)
    # ... more resources ...
    return server
```

**Middleware Stack (server.py:387-413):**
```python
def configure_middleware(server: FastMCP) -> None:
    """Configure middleware stack for the server.

    Adds middleware in order: ErrorHandling -> Logging (with integrated timing)
    """
    server.add_middleware(ErrorHandlingMiddleware(include_traceback=include_traceback))
    server.add_middleware(LoggingMiddleware(
        include_payloads=log_payloads,
        slow_threshold_ms=slow_threshold,
    ))
```

**Available Middleware:**
- `ErrorHandlingMiddleware` - Exception catching and logging
- `LoggingMiddleware` - Request/response logging
- `TimingMiddleware` - Request timing
- NO authentication middleware

**FastMCP Capabilities:** Need to research if FastMCP supports custom auth middleware or has built-in options.

### 5. Rate Limiting (scout_mcp-drx)
**Location:** Same as #4 - no rate limiting middleware exists

**Current State:** Zero rate limiting implementation
- No request throttling
- No per-client limits
- No connection limits (see #10)

### 6. Path Traversal (scout_mcp-pya)
**Location:** `/mnt/cache/code/scout_mcp/scout_mcp/utils/parser.py`

**Current Implementation:**
```python
def parse_target(target: str) -> ScoutTarget:
    """Parse a scout target URI."""
    target = target.strip()

    # Special case: hosts command
    if target.lower() == "hosts":
        return ScoutTarget(host=None, is_hosts_command=True)

    # Parse host:/path format
    if ":" not in target:
        raise ValueError(f"Invalid target '{target}'. Expected 'host:/path' or 'hosts'")

    parts = target.split(":", 1)
    host = parts[0].strip()
    path = parts[1].strip() if len(parts) > 1 else ""

    if not host:
        raise ValueError("Host cannot be empty")

    if not path:
        raise ValueError("Path cannot be empty")

    return ScoutTarget(host=host, path=path)
```

**Path Validation:** NONE
- No check for `..` sequences
- No check for absolute vs relative paths
- No check for symlink traversal
- Relies entirely on SSH server permissions

**Note from CLAUDE.md:** "No path traversal protection (relies on SSH server access controls)"

### 7. Connection Retry Pattern Duplication (scout_mcp-2rf)
**Locations:** Found in 8+ files with identical pattern

**Pattern (from scout.py:76-95):**
```python
# Get connection (with one retry on failure)
try:
    conn = await pool.get_connection(ssh_host)
except Exception as first_error:
    # Connection failed - clear stale connection and retry once
    logger.warning(
        "Connection to %s failed: %s, retrying after cleanup",
        ssh_host.name,
        first_error,
    )
    try:
        await pool.remove_connection(ssh_host.name)
        conn = await pool.get_connection(ssh_host)
        logger.info("Retry connection to %s succeeded", ssh_host.name)
    except Exception as retry_error:
        logger.error(
            "Retry connection to %s failed: %s",
            ssh_host.name,
            retry_error,
        )
        return f"Error: Cannot connect to {ssh_host.name}: {retry_error}"
```

**Duplicated In:**
1. `/mnt/cache/code/scout_mcp/scout_mcp/tools/scout.py:76-95` (20 lines)
2. `/mnt/cache/code/scout_mcp/scout_mcp/resources/scout.py:44-65` (22 lines)
3. `/mnt/cache/code/scout_mcp/scout_mcp/resources/docker.py:32-41` (10 lines, simplified)
4. `/mnt/cache/code/scout_mcp/scout_mcp/resources/docker.py:82-90` (9 lines, duplicate in same file)
5. `/mnt/cache/code/scout_mcp/scout_mcp/resources/compose.py:29-37` (estimated 3 occurrences)
6. `/mnt/cache/code/scout_mcp/scout_mcp/resources/zfs.py` (estimated 4 occurrences)
7. `/mnt/cache/code/scout_mcp/scout_mcp/resources/syslog.py:33-37` (estimated 1 occurrence)

**Total:** ~100-120 lines of duplicated retry logic across codebase

**Variance:** Some use detailed logging, some simplified, but all follow same try-except-remove-retry pattern.

### 8. scout() Function Size (scout_mcp-ydy)
**Location:** `/mnt/cache/code/scout_mcp/scout_mcp/tools/scout.py`

**Current Size:** 146 lines total, 128 lines in `scout()` function (lines 19-146)

**Responsibilities:**
1. Parse and validate target URI (5 lines)
2. Handle "hosts" command (19 lines, including async ping checks)
3. Validate host exists (4 lines)
4. Get connection with retry (20 lines)
5. Execute command if query provided (21 lines)
6. Stat path (7 lines)
7. Read file or list directory (18 lines)
8. Error handling throughout

**Complexity:** High - single function handles 4 distinct operations with different return formats

### 9. Global Lock Contention (scout_mcp-kvk)
**Location:** `/mnt/cache/code/scout_mcp/scout_mcp/services/pool.py:25`

**Current Implementation:**
```python
class ConnectionPool:
    """SSH connection pool with idle timeout."""

    def __init__(self, idle_timeout: int = 60) -> None:
        """Initialize pool with idle timeout in seconds."""
        self.idle_timeout = idle_timeout
        self._connections: dict[str, PooledConnection] = {}
        self._lock = asyncio.Lock()  # ⚠️ SINGLE GLOBAL LOCK
        self._cleanup_task: asyncio.Task[Any] | None = None
```

**Lock Usage:**
- `get_connection()` - Acquires lock for entire operation (lines 34-83)
- `_cleanup_idle()` - Acquires lock to scan all connections (lines 99-123)
- `close_all()` - Acquires lock to close all (lines 127-138)
- `remove_connection()` - Acquires lock to remove one (lines 146-160)

**Contention Points:**
1. **get_connection()** holds lock while calling `asyncssh.connect()` (network I/O)
2. Concurrent requests to different hosts block each other
3. Cleanup task blocks new connections
4. No per-host locking

**Scale Impact:** Becomes bottleneck with >10 concurrent requests to different hosts

### 10. Pool Size Limits (scout_mcp-82l)
**Location:** `/mnt/cache/code/scout_mcp/scout_mcp/services/pool.py`

**Current State:** ZERO limits
```python
class ConnectionPool:
    def __init__(self, idle_timeout: int = 60) -> None:
        self.idle_timeout = idle_timeout
        self._connections: dict[str, PooledConnection] = {}  # No max size
```

**No Constraints:**
- No max connection count
- No max connections per host
- No memory limits
- No resource tracking

**Risk:** Can create unlimited connections until system resources exhausted

**Properties Available:**
```python
@property
def pool_size(self) -> int:
    """Return the current number of connections in the pool."""
    return len(self._connections)

@property
def active_hosts(self) -> list[str]:
    """Return list of hosts with active connections."""
    return list(self._connections.keys())
```

### 11. Test Coverage and pytest-asyncio (scout_mcp-y6f)
**Location:** `/mnt/cache/code/scout_mcp/pyproject.toml:47-50`

**Current Configuration:**
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"  # ⚠️ Deprecated mode
testpaths = ["tests"]
cache_dir = ".cache/.pytest_cache"
```

**Test Files Found:** 30+ test files
```
tests/
├── test_config.py
├── test_executors.py
├── test_integration.py
├── test_pool.py
├── test_scout.py
├── test_ping.py
├── test_middleware/
│   ├── test_errors.py
│   ├── test_logging.py
│   └── test_timing.py
├── test_resources/
│   ├── test_compose.py
│   ├── test_docker.py
│   ├── test_hosts.py
│   ├── test_syslog.py
│   └── test_zfs.py
└── test_services/
    ├── test_compose_executors.py
    ├── test_docker_executors.py
    ├── test_syslog_executors.py
    └── test_zfs_executors.py
```

**Dependencies:**
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]
```

**Issue:** `asyncio_mode = "auto"` is deprecated in pytest-asyncio 0.23+. Should use `asyncio_default_fixture_loop_scope = "function"` instead.

## Considerations

### Security-Critical Issues
1. **Command Injection** - HIGH SEVERITY - `repr()` does NOT prevent shell injection
2. **Host Key Bypass** - HIGH SEVERITY - Disables MITM protection
3. **No Authentication** - MEDIUM SEVERITY - Anyone can access HTTP endpoint
4. **Path Traversal** - LOW SEVERITY - Relies on SSH ACLs only

### Code Quality Issues
5. **Duplicated Retry Logic** - ~120 lines across 8+ files
6. **Large Function** - 128-line scout() does 4 different things
7. **Global Lock** - Blocks concurrent requests to different hosts
8. **No Pool Limits** - Can exhaust system resources

### Configuration Issues
9. **Loose Dependency** - asyncssh version unbounded
10. **Deprecated Config** - pytest-asyncio auto mode
11. **No Rate Limiting** - Can be DoS'd

### FastMCP Integration Questions
- Does FastMCP support custom auth middleware?
- Does FastMCP have built-in rate limiting?
- Can middleware access request context (IP, headers)?
- Does FastMCP support connection limits?

### Testing Impact
- Many tests may break with security fixes (known_hosts, command escaping)
- Test mocks need updating for retry helper function
- New tests needed for auth/rate limiting
- Integration tests may need Docker for known_hosts file

## Next Steps

### Research Phase
1. Check latest asyncssh version and CVE database
2. Review FastMCP documentation for auth/rate limiting capabilities
3. Analyze performance impact of per-host locks
4. Determine if pytest-asyncio upgrade has breaking changes

### Implementation Priorities
**Phase 1 - Critical Security (Week 1)**
1. Replace `repr()` with `shlex.quote()` in all executors
2. Enable host key verification with fallback config
3. Add asyncssh version upper bound

**Phase 2 - Code Quality (Week 2)**
4. Extract connection retry helper function
5. Refactor scout() into separate handler functions
6. Implement per-host connection locks

**Phase 3 - Features (Week 3)**
7. Add FastMCP auth middleware (if supported) or HTTP Basic
8. Implement rate limiting middleware
9. Add pool size limits with configuration
10. Update pytest-asyncio configuration

**Phase 4 - Polish (Week 4)**
11. Add path traversal validation
12. Update all tests for new patterns
13. Add security documentation

### Testing Strategy
- Unit tests for each fix in isolation
- Integration tests with real SSH (Docker container)
- Security tests for injection/traversal attempts
- Performance tests for lock contention
- Backward compatibility tests where possible

### Documentation Needs
- Security hardening guide
- Migration guide for breaking changes
- Configuration reference for new options
- Threat model and security assumptions

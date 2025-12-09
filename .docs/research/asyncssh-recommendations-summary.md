# AsyncSSH Recommendations Summary for Scout MCP

**Date:** 2025-12-03
**For:** Quick reference and implementation planning

## Top 10 Immediate Actions

### 1. Add Connection Timeouts (CRITICAL)
```python
conn = await asyncssh.connect(
    host.hostname,
    port=host.port,
    username=host.user,
    client_keys=client_keys,
    connect_timeout=30,      # ✅ ADD - Prevents hanging on unreachable hosts
    login_timeout=30,        # ✅ ADD - Timeout for authentication
    keepalive_interval=60,   # ✅ ADD - Prevent firewall timeouts
    keepalive_count_max=3,   # ✅ ADD - Auto-disconnect on keepalive failure
    known_hosts=None,
)
```

**Impact:** Prevents indefinite hangs on unreachable hosts (currently ~2 min default).

### 2. Enable Host Key Verification (SECURITY)
```python
# Current: known_hosts=None  # ⚠️ VULNERABLE TO MITM
# Recommended: Omit parameter (uses ~/.ssh/known_hosts by default)

# Add config option
verify_host_keys: bool = True  # Default: enabled

# Update connection
known_hosts_arg = {} if config.verify_host_keys else {"known_hosts": None}
conn = await asyncssh.connect(..., **known_hosts_arg)
```

**Impact:** Protects against man-in-the-middle attacks.

### 3. Implement Connection Validation
```python
async def _validate_connection(conn: asyncssh.SSHClientConnection) -> bool:
    """Test if connection is still alive."""
    try:
        result = await asyncio.wait_for(conn.run('true', check=False), timeout=2)
        return result.returncode == 0
    except (asyncssh.Error, asyncio.TimeoutError):
        return False

# Use before returning pooled connections
if pooled and not pooled.is_stale:
    if await self._validate_connection(pooled.connection):
        return pooled.connection
```

**Impact:** Reliably detects stale connections (current `_transport is None` check is unreliable).

### 4. Enhance Graceful Shutdown
```python
async def close_all(self) -> None:
    """Close all connections gracefully."""
    async with self._lock:
        # Close connections
        close_tasks = []
        for pooled in self._connections.values():
            pooled.connection.close()
            close_tasks.append(pooled.connection.wait_closed())  # ✅ ADD

        # Wait for cleanup (with timeout)
        try:
            await asyncio.wait_for(
                asyncio.gather(*close_tasks, return_exceptions=True),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            logger.warning("Connection cleanup timed out")
```

**Impact:** Proper cleanup, prevents resource leaks.

### 5. Add AsyncSSH Debug Logging
```python
# In config.py
asyncssh_debug = int(os.getenv("SCOUT_ASYNCSSH_DEBUG", "0"))
if asyncssh_debug > 0:
    import asyncssh
    asyncssh_logger = logging.getLogger('asyncssh')
    asyncssh_logger.setLevel(logging.DEBUG)
    asyncssh.set_debug_level(asyncssh_debug)  # 1-3 (2 recommended)
    logger.warning("AsyncSSH debug level %d enabled", asyncssh_debug)
```

**Usage:**
```bash
SCOUT_ASYNCSSH_DEBUG=2 uv run python -m scout_mcp
```

**Impact:** Enables deep debugging of SSH issues.

### 6. Implement Session Semaphore
```python
class ConnectionPool:
    def __init__(self, idle_timeout: int = 60):
        self._session_semaphores: dict[str, asyncio.Semaphore] = {}
        self._max_sessions_per_host = 8  # Conservative (OpenSSH default: 10)

    async def execute_on_host(self, host, operation, *args, **kwargs):
        """Execute with session limit enforcement."""
        if host.name not in self._session_semaphores:
            self._session_semaphores[host.name] = asyncio.Semaphore(
                self._max_sessions_per_host
            )

        async with self._session_semaphores[host.name]:
            conn = await self.get_connection(host)
            return await operation(conn, *args, **kwargs)
```

**Impact:** Prevents hitting SSH server's `MaxSessions` limit (default: 10).

### 7. Add Retry with Exponential Backoff
```python
async def get_connection_with_retry(pool, host, max_retries=2):
    """Get connection with exponential backoff."""
    for attempt in range(max_retries + 1):
        try:
            return await pool.get_connection(host)
        except Exception as e:
            if attempt < max_retries:
                await pool.remove_connection(host.name)
                delay = 1.0 * (2 ** attempt)  # 1s, 2s, 4s...
                await asyncio.sleep(delay)
            else:
                raise
```

**Impact:** More resilient to transient network issues.

### 8. Use SFTP for Large Files (>1MB)
```python
async def stream_large_file(conn, remote_path, max_size, chunk_size=65536):
    """Stream large file via SFTP instead of cat."""
    async with conn.start_sftp_client() as sftp:
        async with sftp.open(remote_path, 'rb') as f:
            chunks = []
            bytes_read = 0
            while bytes_read < max_size:
                chunk = await f.read(min(chunk_size, max_size - bytes_read))
                if not chunk:
                    break
                chunks.append(chunk)
                bytes_read += len(chunk)
            return b''.join(chunks).decode('utf-8', errors='replace')
```

**Impact:** Better memory usage, faster transfers for large files.

### 9. Add Connection Pool Metrics
```python
@dataclass
class ConnectionMetrics:
    created_at: datetime
    last_used: datetime
    use_count: int = 0
    error_count: int = 0

class ConnectionPool:
    def __init__(self, ...):
        self._metrics: dict[str, ConnectionMetrics] = {}
        self.total_connections_created = 0
        self.total_connection_errors = 0

    def get_pool_stats(self) -> dict:
        """Return pool statistics."""
        return {
            "active_connections": len(self._connections),
            "total_created": self.total_connections_created,
            "total_errors": self.total_connection_errors,
            "error_rate": ...,
        }
```

**Impact:** Enables monitoring and debugging.

### 10. Expose Pool Stats via MCP Resource
```python
@mcp.resource("scout://pool/stats")
async def pool_stats_resource() -> str:
    """Connection pool statistics."""
    pool = get_pool()
    stats = pool.get_pool_stats()
    return json.dumps(stats, indent=2)
```

**Impact:** Visibility into connection pool health.

---

## Implementation Priority

### Phase 1: Critical Security & Reliability (Week 1)
1. ✅ Add connection timeouts
2. ✅ Enhance graceful shutdown
3. ✅ Add connection validation
4. ✅ Enable host key verification (with config flag)

### Phase 2: Observability & Debugging (Week 2)
5. ✅ Add AsyncSSH debug logging
6. ✅ Add connection pool metrics
7. ✅ Expose pool stats resource

### Phase 3: Performance & Resilience (Week 3)
8. ✅ Implement session semaphore
9. ✅ Add retry with exponential backoff
10. ✅ Use SFTP for large files

---

## Key Configuration Variables

Add these to `.env` / environment:

```bash
# Connection behavior
SCOUT_CONNECT_TIMEOUT=30          # TCP + SSH handshake timeout (seconds)
SCOUT_LOGIN_TIMEOUT=30            # Authentication timeout (seconds)
SCOUT_KEEPALIVE_INTERVAL=60       # Keepalive frequency (seconds)
SCOUT_KEEPALIVE_COUNT_MAX=3       # Failed keepalives before disconnect

# Security
SCOUT_VERIFY_HOST_KEYS=true       # Enable host key verification

# Session limits
SCOUT_MAX_SESSIONS_PER_HOST=8     # Max concurrent sessions per connection

# Debugging
SCOUT_ASYNCSSH_DEBUG=0            # AsyncSSH debug level (0=off, 1-3)
SCOUT_LOG_LEVEL=INFO              # General log level

# Retry behavior
SCOUT_MAX_RETRIES=2               # Connection retry attempts
SCOUT_RETRY_BASE_DELAY=1.0        # Base delay for exponential backoff
```

---

## Common AsyncSSH Issues & Solutions

### Issue: Connection hangs on unreachable hosts
**Solution:** Add `connect_timeout=30`

### Issue: Connections drop after idle period
**Solution:** Add `keepalive_interval=60`

### Issue: "Connection lost" errors
**Solution:** Validate connections before use, implement retry logic

### Issue: "ChannelOpenError: SSH connection closed"
**Solution:** Session limit exceeded - add semaphore

### Issue: Can't detect stale connections
**Solution:** Use `_validate_connection()` before reuse

### Issue: Resource leaks on shutdown
**Solution:** Call `wait_closed()` on all connections

---

## Testing Recommendations

### Unit Tests with Mocks
```python
@pytest.fixture
def mock_ssh_connection():
    conn = AsyncMock(spec=asyncssh.SSHClientConnection)
    conn.run = AsyncMock(return_value=MagicMock(returncode=0, stdout="output"))
    return conn
```

### Integration Tests with Real SSH Server
```python
@pytest.fixture
async def ssh_server():
    """Start local AsyncSSH server for testing."""
    server = await asyncssh.create_server(
        lambda: asyncssh.SSHServer(),
        '', 0,  # Random port
        server_host_keys=[...],
    )
    yield server
    server.close()
    await server.wait_closed()
```

---

## Performance Benchmarks

**From Research:**
- AsyncSSH is ~15x faster than other libraries for multi-host operations
- Single-host performance roughly equivalent across libraries
- SFTP with 256KB blocks ~3x faster than 48KB blocks
- 128 parallel SFTP requests optimal for throughput

---

## Security Warnings

### ⚠️ NEVER in Production:
```python
known_hosts=None  # Disables host key verification - MITM vulnerable
asyncssh.set_debug_level(3)  # Exposes passwords in logs!
```

### ✅ Always in Production:
```python
# Host key verification enabled (default)
connect_timeout=30  # Prevent indefinite hangs
keepalive_interval=60  # Detect dead connections
```

---

## Quick Links

- **Full Report:** `/mnt/cache/code/scout_mcp/.docs/asyncssh-best-practices-2025-12-03.md`
- **AsyncSSH Docs:** https://asyncssh.readthedocs.io/
- **GitHub Issues:** https://github.com/ronf/asyncssh/issues

---

## Code Templates

### Enhanced Connection with All Settings
```python
conn = await asyncssh.connect(
    host.hostname,
    port=host.port,
    username=host.user,
    client_keys=[host.identity_file] if host.identity_file else None,
    # Timeouts
    connect_timeout=30,
    login_timeout=30,
    # Keepalive
    keepalive_interval=60,
    keepalive_count_max=3,
    # Security (choose one):
    # known_hosts=None,  # Disable (dev only)
    # known_hosts omitted = use ~/.ssh/known_hosts (recommended)
)
```

### Graceful Shutdown Handler
```python
import signal

async def shutdown_handler(pool):
    logger.info("Shutting down...")
    await pool.close_all()

    tasks = [t for t in asyncio.all_tasks() if not t.done()]
    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)

# Register
loop = asyncio.get_event_loop()
for sig in (signal.SIGTERM, signal.SIGINT):
    loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown_handler(pool)))
```

### Connection Retry with Backoff
```python
for attempt in range(max_retries + 1):
    try:
        conn = await pool.get_connection(host)
        return conn
    except Exception as e:
        if attempt < max_retries:
            await pool.remove_connection(host.name)
            await asyncio.sleep(1.0 * (2 ** attempt))
        else:
            raise
```

---

**Last Updated:** 2025-12-03
**Maintainer:** Research Specialist (Claude)

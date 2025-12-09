# SSH Connection Management Research

## Summary
Scout MCP implements a sophisticated SSH connection pooling system with lazy disconnect, automatic stale detection, and one-retry error recovery. The architecture uses asyncio primitives for thread safety, global singletons for state management, and comprehensive logging for observability. Connection reuse is optimized for single-host scenarios with sub-millisecond warm retrieval, while idle connections are automatically cleaned up via background tasks.

## Key Components

### Connection Pool
- `/mnt/cache/code/scout_mcp/scout_mcp/services/pool.py`: Core pooling logic with idle timeout and cleanup
- `/mnt/cache/code/scout_mcp/scout_mcp/services/state.py`: Global singleton management for pool and config
- `/mnt/cache/code/scout_mcp/scout_mcp/models/ssh.py`: Data models for SSH hosts and pooled connections

### Configuration & Discovery
- `/mnt/cache/code/scout_mcp/scout_mcp/config.py`: SSH config parser with allowlist/blocklist filtering
- `/mnt/cache/code/scout_mcp/scout_mcp/utils/ping.py`: TCP-based host connectivity checking

### Executors
- `/mnt/cache/code/scout_mcp/scout_mcp/services/executors.py`: SSH command execution wrappers (cat, ls, tree, run_command)

### Retry Integration
- `/mnt/cache/code/scout_mcp/scout_mcp/tools/scout.py`: Tool interface with one-retry pattern
- `/mnt/cache/code/scout_mcp/scout_mcp/resources/scout.py`: Resource interface with one-retry pattern

## Implementation Patterns

### Connection Pooling Architecture

**Pattern: Single Connection Per Host**
```python
# pool.py line 24
self._connections: dict[str, PooledConnection] = {}
```
- Dictionary keyed by host name (not hostname+port tuple)
- Each host gets exactly one reusable connection
- Connections tracked with last-used timestamp and stale detection

**Pattern: Lock-Based Thread Safety** (`pool.py` lines 25, 34)
```python
self._lock = asyncio.Lock()

async def get_connection(self, host: SSHHost):
    async with self._lock:  # Serialize all pool operations
        ...
```
- Single asyncio.Lock protects all pool mutations
- Lock held during: lookup, creation, stale detection, removal
- No per-connection locks (not needed for single connection/host)
- Benchmark: <1ms overhead for warm retrieval, handles 100 concurrent requests to same host

**Pattern: Lazy Connection Creation** (`pool.py` lines 35-45)
```python
pooled = self._connections.get(host.name)
if pooled and not pooled.is_stale:
    pooled.touch()  # Update last_used timestamp
    return pooled.connection
# Otherwise create new connection
```

**Pattern: Stale Detection** (`models/ssh.py` lines 34-37)
```python
@property
def is_stale(self) -> bool:
    """Check if connection was closed."""
    is_closed: bool = self.connection.is_closed
    return is_closed
```
- Uses asyncssh's built-in `is_closed` property
- Detected on every `get_connection()` call
- Automatically triggers reconnection without error propagation

### Idle Timeout & Cleanup

**Pattern: Background Cleanup Task** (`pool.py` lines 78-95)
```python
if self._cleanup_task is None or self._cleanup_task.done():
    self._cleanup_task = asyncio.create_task(self._cleanup_loop())

async def _cleanup_loop(self) -> None:
    while True:
        await asyncio.sleep(self.idle_timeout // 2)  # Check at half-interval
        await self._cleanup_idle()
        if not self._connections:
            break  # Auto-stop when empty
```
- Started lazily on first connection
- Runs at `idle_timeout / 2` intervals (default 30s for 60s timeout)
- Self-terminates when pool is empty
- Automatically restarts on next connection

**Pattern: Idle Cutoff Calculation** (`pool.py` lines 100-116)
```python
cutoff = datetime.now() - timedelta(seconds=self.idle_timeout)
for name, pooled in self._connections.items():
    if pooled.last_used < cutoff or pooled.is_stale:
        pooled.connection.close()
        to_remove.append(name)
```
- Compares `last_used` timestamp against cutoff
- Closes both idle AND stale connections
- Batch removal after iteration completes

### Error Handling & Retry Logic

**Pattern: One-Retry with Stale Removal** (`tools/scout.py` lines 76-95, `resources/scout.py` lines 44-65)
```python
try:
    conn = await pool.get_connection(ssh_host)
except Exception as first_error:
    logger.warning("Connection failed: %s, retrying after cleanup", first_error)
    try:
        await pool.remove_connection(ssh_host.name)  # Clear stale
        conn = await pool.get_connection(ssh_host)   # Retry once
        logger.info("Retry succeeded")
    except Exception as retry_error:
        logger.error("Retry failed: %s", retry_error)
        return f"Error: Cannot connect to {ssh_host.name}: {retry_error}"
```
- First failure: Log warning, remove connection, retry
- Second failure: Log error, return error string (tools) or raise ResourceError (resources)
- Retry always creates fresh connection (stale removed)
- Used consistently in both tool and resource interfaces

**Difference: Tools vs Resources**
- **Tools** (`scout.py`): Return error strings, never raise
- **Resources** (`scout_resource.py`): Raise `ResourceError` (MCP standard)

### Global State Management

**Pattern: Lazy Singleton** (`services/state.py` lines 6-25)
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
- Module-level singletons initialized on first access
- Pool depends on config for idle_timeout
- No dependency injection (direct function calls throughout codebase)
- Testing support: `reset_state()`, `set_config()`, `set_pool()`

### SSH Configuration Parsing

**Pattern: Lazy Config Parsing** (`config.py` lines 88-157)
```python
def _parse_ssh_config(self) -> None:
    if self._parsed:
        return  # Parse only once

    # Parse ~/.ssh/config line by line
    for line in content.splitlines():
        host_match = re.match(r"^Host\s+(\S+)", line, re.IGNORECASE)
        if host_match:
            # Save previous host, start new one
```
- Parse on first `get_hosts()` or `get_host()` call
- Reads `~/.ssh/config` with standard SSH directives
- Extracts: Host alias, HostName, User, Port, IdentityFile
- Defaults: user="root", port=22
- Missing config file treated as empty (no error)

**Pattern: Allowlist/Blocklist Filtering** (`config.py` lines 159-178)
```python
def _is_host_allowed(self, name: str) -> bool:
    # Allowlist takes precedence
    if self.allowlist:
        return any(fnmatch(name, pattern) for pattern in self.allowlist)
    # Check blocklist
    if self.blocklist:
        return not any(fnmatch(name, pattern) for pattern in self.blocklist)
    return True
```
- Supports fnmatch patterns (e.g., `"prod-*"`, `"*.internal"`)
- Allowlist overrides blocklist
- Empty lists = allow all

### Host Connectivity Checking

**Pattern: Concurrent TCP Probe** (`utils/ping.py` lines 29-52)
```python
async def check_hosts_online(
    hosts: dict[str, tuple[str, int]],
    timeout: float = 2.0,
) -> dict[str, bool]:
    coros = [
        check_host_online(hostname, port, timeout)
        for hostname, port in hosts.values()
    ]
    results = await asyncio.gather(*coros)
    return dict(zip(names, results, strict=True))
```
- TCP connection only (no SSH authentication)
- Default 2-second timeout per host
- All hosts checked in parallel via `asyncio.gather()`
- Returns False on timeout or OSError

**Usage:** Used by `scout("hosts")` command and `list_hosts_resource()` to show online/offline status

### SSH Command Execution

**Pattern: Shell Command Wrapping** (`services/executors.py`)
```python
# stat_path - line 17
result = await conn.run(f'stat -c "%F" {path!r} 2>/dev/null', check=False)

# cat_file - line 53
result = await conn.run(f"head -c {max_size} {path!r}", check=False)

# ls_dir - line 87
result = await conn.run(f"ls -la {path!r}", check=False)

# run_command - line 161
full_command = f"cd {working_dir!r} && timeout {timeout} {command}"
result = await conn.run(full_command, check=False)
```
- All use `check=False` to capture return codes
- Path quoting via `repr()` for shell safety
- `2>/dev/null` for silent error suppression
- Decode bytes as UTF-8 with `errors="replace"`

**Pattern: Fallback Commands** (`executors.py` lines 122-147)
```python
# Try tree command first
result = await conn.run(f"tree -L {max_depth} --noreport {path!r} 2>/dev/null")
if result.returncode == 0:
    return stdout

# Fall back to find
find_cmd = f"find {path!r} -maxdepth {max_depth} -type f -o -type d 2>/dev/null | head -100"
```
- Attempt preferred command, check return code
- Fallback to more universal command if first fails

## Considerations

### Thread Safety
- **Single Lock Strategy**: All pool operations serialized via one `asyncio.Lock`
- **No Deadlocks**: Lock never held across await points (except controlled pool operations)
- **Race Condition Free**: Dictionary mutations always inside lock
- **Async-Safe Only**: Not thread-safe (uses asyncio.Lock, not threading.Lock)

### Resource Cleanup
- **Automatic Idle Cleanup**: Background task removes idle connections every `idle_timeout/2` seconds
- **Manual Cleanup**: `pool.close_all()` closes all connections (used in server shutdown)
- **Stale Connection Handling**: Detected on every access, triggers immediate replacement
- **No Connection Leaks**: Connections always closed before removal from pool

### Memory Management
- **Bounded by Host Count**: Max connections = number of configured SSH hosts
- **Typical Footprint**: ~10KB for 100 pooled connections (benchmark data)
- **No Unbounded Growth**: One connection per host, idle cleanup prevents accumulation
- **Test Reset**: `reset_state()` clears singletons for test isolation

### Performance Characteristics
- **Cold Start**: ~10-50ms (SSH handshake + key exchange)
- **Warm Retrieval**: <1ms (dict lookup + timestamp update)
- **Lock Contention**: Handles 100 concurrent requests to same host without degradation
- **Cleanup Overhead**: <5ms max latency impact during cleanup cycles
- **Parallel Creation**: Multiple new hosts connected concurrently (not serialized)

### Error Edge Cases
- **SSH Config Missing**: Treated as empty, no hosts available
- **SSH Config Unreadable**: Logged as warning, treated as empty
- **Invalid Port**: Defaults to 22, logged if parse fails
- **Missing IdentityFile**: Passed as `None`, asyncssh uses default keys
- **Connection Timeout**: asyncssh default timeouts apply (not configurable in Scout)
- **Network Partition**: TCP probe returns offline, SSH connection fails with retry
- **Stale Detection False Negative**: Impossible (uses asyncssh.is_closed property)

### Non-Obvious Behaviors
- **Host Name vs Hostname**: Pool keyed by SSH config alias (name), not actual hostname
- **Port Not in Key**: Same hostname on different ports = separate hosts in SSH config
- **Cleanup Task Lifecycle**: Auto-starts on first connection, auto-stops when empty
- **Retry Creates New Connection**: `remove_connection()` forces fresh connection on retry
- **Last-Used Updated Even on Reuse**: Every `get_connection()` updates timestamp
- **Blocklist Ignored if Allowlist Present**: Allowlist takes absolute precedence

### Configuration Gotchas
- **Default User**: Hardcoded to "root" (not current user)
- **Identity File Path**: Not expanded (~/ passed directly to asyncssh)
- **known_hosts**: Always `None` (host key verification disabled for convenience)
- **Environment Variables**: `SCOUT_*` preferred, `MCP_CAT_*` legacy fallback
- **Transport Config**: `SCOUT_TRANSPORT` controls HTTP vs STDIO mode

### Logging Coverage
- **Connection Lifecycle**: Creation, reuse, stale detection, removal logged at INFO
- **Retry Logic**: First failure WARNING, retry success INFO, retry failure ERROR
- **Pool State**: Pool size logged on connection changes
- **Cleanup Events**: Idle/stale closure logged at INFO, batch summary at DEBUG
- **Config Parsing**: Host count logged at DEBUG after parsing

## Next Steps

### For Feature Implementation
1. **Connection Reuse**: Use `get_pool()` singleton, never create ConnectionPool directly
2. **Error Handling**: Implement one-retry pattern for robustness (see tools/scout.py example)
3. **Host Lookup**: Use `get_config().get_host(name)` for validation before connection
4. **Logging**: Use existing logger patterns for consistency (`logging.getLogger(__name__)`)

### For Refactoring Connection Pool
**Risk Areas:**
- Changing lock strategy requires careful analysis of concurrent access patterns
- Removing background cleanup task would need alternative idle timeout mechanism
- Per-connection locks would add complexity without performance benefit (benchmarked)
- Connection key changes (e.g., including port) would break existing behavior

**Safe Changes:**
- Configurable connection limits per host (currently hardcoded to 1)
- Connection health checks (ping before returning stale connection)
- Metrics collection (connection counts, error rates, latency histograms)
- Alternative cleanup strategies (LRU eviction, connection age limits)

### For Testing
- Use `reset_state()` in fixtures to clear singletons between tests
- Mock `asyncssh.connect` for unit tests (see `tests/test_pool.py`)
- Use `set_pool()` and `set_config()` to inject test doubles
- Benchmark tests available in `tests/benchmarks/test_connection_pool.py`

### For Monitoring
- Enable `SCOUT_LOG_LEVEL=DEBUG` for detailed pool events
- Monitor pool size via `pool.pool_size` property
- Track active hosts via `pool.active_hosts` property
- Watch for repeated "retry failed" errors indicating persistent connectivity issues

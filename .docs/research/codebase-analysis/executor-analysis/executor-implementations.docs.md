# Scout MCP Executor Implementations Research

## Summary

The Scout MCP server implements SSH command executors in `/mnt/cache/code/scout_mcp/scout_mcp/services/executors.py`. These executors provide atomic operations for remote file and command operations, abstracting SSH interactions with consistent error handling and output normalization. All executors use `asyncssh.SSHClientConnection.run()` with `check=False` to capture return codes, and handle both bytes and string outputs with UTF-8 decoding and error replacement.

## Key Components

### Core Executors
- `/mnt/cache/code/scout_mcp/scout_mcp/services/executors.py` - All executor implementations (643 lines)
- `/mnt/cache/code/scout_mcp/scout_mcp/services/pool.py` - Connection pooling and SSH lifecycle (171 lines)
- `/mnt/cache/code/scout_mcp/scout_mcp/models/command.py` - CommandResult dataclass
- `/mnt/cache/code/scout_mcp/scout_mcp/models/ssh.py` - PooledConnection, SSHHost dataclasses
- `/mnt/cache/code/scout_mcp/scout_mcp/config.py` - Configuration with timeout/size limits (184 lines)

### Usage Sites
- `/mnt/cache/code/scout_mcp/scout_mcp/tools/scout.py` - Primary tool using executors (147 lines)
- `/mnt/cache/code/scout_mcp/scout_mcp/resources/scout.py` - Resource using cat_file, ls_dir, stat_path (92 lines)
- `/mnt/cache/code/scout_mcp/tests/test_executors.py` - Unit tests for core executors (180 lines)

## Implementation Patterns

### 1. File Operations Pattern

**stat_path** (lines 11-37):
```python
async def stat_path(conn, path: str) -> str | None
```
- Uses `stat -c "%F"` with stderr redirected to `/dev/null`
- Returns: `'file'`, `'directory'`, or `None`
- Treats unknown types (symlinks, devices) as `'file'`
- Error suppression: Non-zero return code → `None`

**cat_file** (lines 40-75):
```python
async def cat_file(conn, path: str, max_size: int) -> tuple[str, bool]
```
- Uses `head -c {max_size}` for size limiting (server-side truncation)
- Returns: `(content, was_truncated)`
- Truncation detection: `len(content.encode("utf-8")) >= max_size`
- Raises `RuntimeError` on read failure (non-zero return code)
- Size enforcement: Configured via `SCOUT_MAX_FILE_SIZE` (default: 1MB)

### 2. Directory Operations Pattern

**ls_dir** (lines 78-102):
```python
async def ls_dir(conn, path: str) -> str
```
- Uses `ls -la` for detailed listings
- Returns raw output string
- Raises `RuntimeError` on failure with stderr message

**tree_dir** (lines 105-147):
```python
async def tree_dir(conn, path: str, max_depth: int = 3) -> str
```
- Tries `tree -L {max_depth} --noreport` first
- Falls back to `find {path} -maxdepth {max_depth} -type f -o -type d | head -100`
- No error on failure - returns empty string or fallback output
- Graceful degradation for systems without `tree` command

### 3. Command Execution Pattern

**run_command** (lines 150-190):
```python
async def run_command(conn, working_dir: str, command: str, timeout: int) -> CommandResult
```
- Combines: `cd {working_dir} && timeout {timeout} {command}`
- Uses shell `timeout` command (not asyncio timeout)
- Always returns `CommandResult` - never raises
- Handles None outputs by converting to empty strings
- Default timeout: 30 seconds (configurable via `SCOUT_COMMAND_TIMEOUT`)

### 4. Output Normalization Pattern

**All executors follow this pattern:**
```python
# 1. Execute command with check=False
result = await conn.run(command, check=False)

# 2. Check return code
if result.returncode != 0:
    # Handle error (return None, raise, or include in result)

# 3. Normalize output (bytes or str → str)
stdout = result.stdout
if stdout is None:
    output = ""
elif isinstance(stdout, bytes):
    output = stdout.decode("utf-8", errors="replace")
else:
    output = stdout
```

### 5. Connection Retry Pattern (in callers)

**Used in tools/scout.py and resources/scout.py:**
```python
try:
    conn = await pool.get_connection(ssh_host)
except Exception as first_error:
    # Log and retry once
    await pool.remove_connection(ssh_host.name)
    conn = await pool.get_connection(ssh_host)  # May raise
```

## Error Handling Strategies

### Strategy 1: Return None (stat_path)
- **When**: Path might not exist (expected failure)
- **Pattern**: Non-zero return code → `None`
- **Example**: `stat_path("/nonexistent")` returns `None`

### Strategy 2: Raise RuntimeError (cat_file, ls_dir)
- **When**: Unexpected failure (permission denied, I/O error)
- **Pattern**: Non-zero return code → `raise RuntimeError(stderr_msg)`
- **Example**: `cat_file("/root/secret")` raises with permission error

### Strategy 3: Always Return Result (run_command)
- **When**: Command execution itself is the operation
- **Pattern**: Return `CommandResult` with stdout/stderr/returncode
- **Example**: `run_command("/tmp", "grep NOTFOUND file")` returns exit code 1

### Strategy 4: Graceful Degradation (tree_dir)
- **When**: Optional features or fallback commands
- **Pattern**: Try preferred → fallback → empty string
- **Example**: `tree` command missing → uses `find` instead

### Strategy 5: Silent Failure (docker_*/zfs_*/compose_* helpers)
- **When**: Checking availability of optional services
- **Pattern**: Return empty list/False on any error
- **Example**: `docker_ps()` returns `[]` if Docker not installed

## Timeout Handling

### Configuration
- **Environment Variable**: `SCOUT_COMMAND_TIMEOUT` (legacy: `MCP_CAT_COMMAND_TIMEOUT`)
- **Default**: 30 seconds
- **Applied in**: `run_command` executor only

### Implementation Details
```python
# Uses Linux 'timeout' command (NOT asyncio timeout)
full_command = f"cd {working_dir!r} && timeout {timeout} {command}"
result = await conn.run(full_command, check=False)
```

### Timeout Exit Codes
- **124**: Command timed out (killed by `timeout` utility)
- **137**: Command killed by signal (SIGKILL)
- Callers must check `result.returncode` to detect timeouts

### NO Timeout on Other Executors
- `stat_path`: Fast operation (stat syscall)
- `cat_file`: Limited by `max_size` (head command terminates)
- `ls_dir`: Directory listings typically fast
- `tree_dir`: Uses `head -100` to limit output

### Connection-Level Timeout
- **NOT** at executor level
- Handled by `asyncssh.connect()` in ConnectionPool
- No explicit timeout parameter (uses asyncssh defaults)

## Size Limit Enforcement

### File Reading (cat_file)
```python
# Server-side enforcement using 'head' command
result = await conn.run(f"head -c {max_size} {path!r}", check=False)

# Client-side detection
was_truncated = len(content.encode("utf-8")) >= max_size
```

**Configuration:**
- Environment: `SCOUT_MAX_FILE_SIZE` (legacy: `MCP_CAT_MAX_FILE_SIZE`)
- Default: 1,048,576 bytes (1 MB)
- Prevents memory exhaustion from large files

### Directory Listings
- `tree_dir`: Hardcoded `head -100` on find fallback
- `ls_dir`: No limit (assumes reasonable directory sizes)

### Command Output
- `run_command`: No explicit limit
- Relies on timeout to prevent infinite output
- Memory risk: Long-running commands with continuous output

## Additional Executors (Beyond Core Five)

### Docker Support (lines 193-285)
- `docker_logs(container, tail, timestamps)` → tuple[str, bool]
- `docker_ps()` → list[dict[name, status, image]]
- `docker_inspect(container)` → bool
- Pattern: Return empty/False if Docker unavailable

### Docker Compose Support (lines 287-420)
- `compose_ls()` → list[dict[name, status, config_file]]
- `compose_config(project)` → tuple[str, str|None]
- `compose_logs(project, tail, timestamps)` → tuple[str, bool]
- Pattern: Parse JSON output, return empty on error

### ZFS Support (lines 423-597)
- `zfs_check()` → bool (availability check)
- `zfs_pools()` → list[dict] (pool info)
- `zfs_pool_status(pool)` → tuple[str, bool]
- `zfs_datasets(pool)` → list[dict]
- `zfs_snapshots(dataset, limit)` → list[dict]
- Pattern: Parse tab-delimited output, return empty lists on failure

### System Logs (lines 600-642)
- `syslog_read(lines)` → tuple[str, str]
- Tries `journalctl` first (systemd)
- Falls back to `/var/log/syslog`
- Returns source type: 'journalctl', 'syslog', or 'none'

## Considerations

### Critical Edge Cases

1. **Encoding Errors**: All executors use `errors="replace"` for UTF-8 decoding
   - Binary files become garbage characters
   - No detection of binary vs text files
   - Consider: Add MIME type detection before cat_file

2. **Path Injection**: Commands use `repr()` for shell quoting
   - Example: `f"head -c {max_size} {path!r}"`
   - `repr("/etc/passwd")` → `'/etc/passwd'`
   - Safe from basic injection, but not validated for traversal

3. **Truncation Detection Edge Case**:
   - `was_truncated = len(content.encode("utf-8")) >= max_size`
   - False positive: File exactly max_size bytes shows as truncated
   - Should be `>` not `>=` for accuracy

4. **Empty Stdout**: Multiple checks for `None` throughout
   - `asyncssh` may return `None`, `b""`, or `""`
   - Inconsistent handling could cause issues

5. **Connection Staleness**:
   - Detected via `connection.is_closed` property
   - Not checked before command execution
   - Failure triggers retry pattern in callers

### Dependencies and Constraints

1. **Linux Shell Dependencies**:
   - `stat`: Must support `-c "%F"` flag (GNU stat, not BSD)
   - `head`: Must support `-c` for byte counting
   - `ls`: Assumes GNU ls output format
   - `tree`: Optional (graceful fallback)
   - `timeout`: Command-line utility (GNU coreutils)

2. **SSH Server Requirements**:
   - Must allow shell command execution
   - No sftp/scp-only restrictions
   - Assumes bash-compatible shell

3. **Connection Pool Contract**:
   - One connection per host (shared across all executors)
   - Executors must not close connections
   - Thread-safe via asyncio.Lock in pool
   - Idle cleanup runs every idle_timeout/2 seconds

4. **asyncssh Version**:
   - Requires asyncssh >= 2.14.0
   - Uses `.run()` method (not execute or create_process)
   - Output may be bytes or str depending on version

### Security Considerations

1. **No Path Traversal Protection**:
   - Executors blindly execute paths provided
   - Security relies on SSH server access controls
   - Consider: Add path validation or chroot-style restrictions

2. **Command Injection via run_command**:
   - `working_dir` is quoted with `repr()`
   - `command` is NOT quoted (intentional - allows pipes/redirects)
   - Caller responsible for sanitizing command strings

3. **File Size DoS**:
   - Protected by `max_size` parameter
   - Default 1MB prevents memory exhaustion
   - Large values still risky on memory-constrained systems

4. **Timeout DoS**:
   - Only run_command has timeout
   - Other operations could hang on unresponsive SSH
   - Consider: Add timeout to all executors

5. **Connection Exhaustion**:
   - One connection per host (not per request)
   - Limited by SSH server's MaxSessions setting
   - No explicit connection limit in pool

### Type Safety

1. **Union Types**: `stdout: str | bytes | None`
   - All executors handle all three cases
   - Pattern: Check None → check bytes → assume str

2. **Optional Returns**: Several executors return `T | None`
   - `stat_path` → `str | None`
   - Callers must check before using

3. **Tuple Returns**: Multiple return values common
   - `cat_file` → `tuple[str, bool]`
   - `docker_logs` → `tuple[str, bool]`
   - Clear semantics but no named tuples

4. **Type Checking**: Uses TYPE_CHECKING guard
   - Avoids circular imports
   - `asyncssh` imported only for type hints

## Next Steps

### For New Features Using Executors

1. **Follow Return Patterns**:
   - Optional operations → Return None or empty
   - Required operations → Raise on failure
   - User commands → Always return result object

2. **Add Timeout if Long-Running**:
   - Use `timeout` command like run_command
   - Document timeout behavior
   - Return timeout exit code (124) in result

3. **Handle Binary Content**:
   - Check file type before cat_file
   - Add MIME detection utility
   - Return error for binary files or base64 encode

4. **Test Edge Cases**:
   - Empty output (None vs "" vs b"")
   - Non-zero exit codes
   - Connection failures
   - Encoding errors (UTF-8 invalid sequences)

### For Enhancing Executors

1. **Add MIME Detection**:
   - Create `detect_mime_type(conn, path)` executor
   - Use `file --mime-type` command
   - Call before cat_file to prevent binary reads

2. **Improve Truncation Detection**:
   - Change `>=` to `>` in cat_file line 73
   - Or use actual file size from stat

3. **Add Universal Timeout**:
   - Wrap all executor calls with asyncio.timeout
   - Configurable per-executor type
   - Log timeout events

4. **Structured Output Types**:
   - Convert docker_*/zfs_* to use dataclasses
   - Replace dict returns with typed objects
   - Better IDE support and validation

5. **Connection Health Checks**:
   - Add `conn.is_closed` check before execution
   - Auto-retry in executors instead of callers
   - Reduce boilerplate in tools/resources

## Testing Patterns

From `/mnt/cache/code/scout_mcp/tests/test_executors.py`:

```python
# Mock SSH connection
@pytest.fixture
def mock_connection() -> AsyncMock:
    conn = AsyncMock()
    return conn

# Test success path
mock_connection.run.return_value = MagicMock(
    stdout="expected output",
    returncode=0
)

# Test failure path
mock_connection.run.return_value = MagicMock(
    stdout="",
    stderr="error message",
    returncode=1
)

# Test bytes vs string handling
mock_connection.run.return_value = MagicMock(
    stdout=b"bytes output",
    returncode=0
)
```

**Coverage:** 120+ tests, ~81% coverage overall
- Core executors: Well tested
- Docker/ZFS/Compose executors: Limited coverage
- Error paths: Good coverage
- Edge cases: Some gaps (encoding, truncation boundary)

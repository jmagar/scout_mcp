# Docker Logs Resource Implementation Research

## Summary
Scout MCP uses a lifespan pattern to dynamically register host-specific URI resources (e.g., `tootie://path`). Docker logs can follow this pattern by registering `docker://{host}/{container}` resources during server startup. The existing executor pattern uses SSH commands with proper error handling and output decoding, which maps cleanly to `docker logs` commands.

## Key Components

### Dynamic Resource Registration
- `/code/scout_mcp/scout_mcp/server.py:37-69` - `app_lifespan()` function registers host-specific resources
- `/code/scout_mcp/scout_mcp/server.py:54-67` - Closure pattern with `make_handler()` to capture host context
- `/code/scout_mcp/scout_mcp/server.py:62-67` - Resource decorator registers URI templates

### Existing Resource Implementations
- `/code/scout_mcp/scout_mcp/resources/scout.py:9-77` - `scout_resource()` main pattern
- `/code/scout_mcp/scout_mcp/resources/hosts.py:7-51` - `list_hosts_resource()` for listing
- `/code/scout_mcp/scout_mcp/resources/__init__.py:1-6` - Module exports

### SSH Command Execution
- `/code/scout_mcp/scout_mcp/services/executors.py:11-38` - `stat_path()` pattern for checking existence
- `/code/scout_mcp/scout_mcp/services/executors.py:40-76` - `cat_file()` pattern with size limits and truncation
- `/code/scout_mcp/scout_mcp/services/executors.py:78-103` - `ls_dir()` pattern for listing
- `/code/scout_mcp/scout_mcp/services/executors.py:150-191` - `run_command()` with working dir and timeout

### Connection Management
- `/code/scout_mcp/scout_mcp/services/pool.py:15-98` - `ConnectionPool` class with retry pattern
- `/code/scout_mcp/scout_mcp/resources/scout.py:39-50` - One-retry connection pattern with cleanup

### Tools Pattern (Alternative to Resources)
- `/code/scout_mcp/scout_mcp/tools/scout.py:14-120` - Tool returns error strings (no exceptions)
- `/code/scout_mcp/scout_mcp/tools/scout.py:70-91` - Query parameter for running commands

## Implementation Patterns

### Pattern 1: Dynamic Resource Registration (Lifespan)
**Location:** `/code/scout_mcp/scout_mcp/server.py:37-69`

```python
@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    config = get_config()
    hosts = config.get_hosts()

    for host_name in hosts:
        def make_handler(h: str) -> Any:
            async def handler(path: str) -> str:
                return await _read_host_path(h, path)
            return handler

        server.resource(
            uri=f"{host_name}://{{path*}}",
            name=f"{host_name} filesystem",
            description=f"Read files and directories on {host_name}",
            mime_type="text/plain",
        )(make_handler(host_name))

    yield {"hosts": list(hosts.keys())}
```

**Key Points:**
- Closure pattern (`make_handler`) captures host in scope
- `{path*}` allows arbitrary path segments
- Registered on server startup via lifespan context manager
- Resources are callable async functions that return strings

### Pattern 2: Resource Error Handling
**Location:** `/code/scout_mcp/scout_mcp/resources/scout.py:27-76`

```python
async def scout_resource(host: str, path: str) -> str:
    config = get_config()
    pool = get_pool()

    # Validate host
    ssh_host = config.get_host(host)
    if ssh_host is None:
        available = ", ".join(sorted(config.get_hosts().keys()))
        raise ResourceError(f"Unknown host '{host}'. Available: {available}")

    # Get connection with retry
    try:
        conn = await pool.get_connection(ssh_host)
    except Exception:
        try:
            await pool.remove_connection(ssh_host.name)
            conn = await pool.get_connection(ssh_host)
        except Exception as retry_error:
            raise ResourceError(
                f"Cannot connect to {host}: {retry_error}"
            ) from retry_error
```

**Key Points:**
- Resources raise `ResourceError` (MCP standard) not return error strings
- One-retry pattern: clear stale connection and retry
- Use `from retry_error` to preserve stack trace
- Validate inputs before attempting connections

### Pattern 3: SSH Command Execution
**Location:** `/code/scout_mcp/scout_mcp/services/executors.py:11-38`

```python
async def stat_path(conn: "asyncssh.SSHClientConnection", path: str) -> str | None:
    result = await conn.run(f'stat -c "%F" {path!r} 2>/dev/null', check=False)

    if result.returncode != 0:
        return None

    stdout = result.stdout
    if stdout is None:
        return None

    # Handle bytes or str
    if isinstance(stdout, bytes):
        file_type = stdout.decode("utf-8", errors="replace").strip().lower()
    else:
        file_type = stdout.strip().lower()

    return file_type
```

**Key Points:**
- Always use `check=False` to capture return codes manually
- Handle both bytes and str output (asyncssh inconsistency)
- Use `path!r` for shell quoting (repr for safety)
- Use `2>/dev/null` to suppress stderr when checking existence
- Use `errors="replace"` for robust UTF-8 decoding

### Pattern 4: Output Formatting with Truncation
**Location:** `/code/scout_mcp/scout_mcp/services/executors.py:40-76`

```python
async def cat_file(
    conn: "asyncssh.SSHClientConnection",
    path: str,
    max_size: int,
) -> tuple[str, bool]:
    result = await conn.run(f"head -c {max_size} {path!r}", check=False)

    if result.returncode != 0:
        stderr = result.stderr
        if isinstance(stderr, bytes):
            error_msg = stderr.decode("utf-8", errors="replace")
        else:
            error_msg = stderr or ""
        raise RuntimeError(f"Failed to read {path}: {error_msg}")

    stdout = result.stdout
    if stdout is None:
        return ("", False)

    if isinstance(stdout, bytes):
        content = stdout.decode("utf-8", errors="replace")
    else:
        content = stdout

    # Check if file was truncated
    was_truncated = len(content.encode("utf-8")) >= max_size

    return (content, was_truncated)
```

**Key Points:**
- Return tuple `(content, was_truncated)` for size-limited reads
- Use `head -c {max_size}` to limit output at source
- Check truncation by comparing byte length to max_size
- Always decode stderr for error messages

## Docker-Specific SSH Commands

### List Containers
```bash
docker ps --format '{{.Names}}\t{{.Status}}\t{{.Image}}'
```

### Check Container Exists
```bash
docker inspect --format '{{.Name}}' container_name 2>/dev/null
```
- Returns empty with exit code 1 if container doesn't exist
- Returns container name if exists

### Get Logs
```bash
docker logs --tail 100 container_name 2>&1
```
- `--tail N` limits to last N lines
- `--since 5m` for time-based filtering (5 minutes, 2h, etc)
- `--timestamps` adds RFC3339 timestamps
- `2>&1` merges stderr into stdout (Docker logs split stdout/stderr)

### Get Logs with Timestamps and Time Filter
```bash
docker logs --timestamps --since 5m container_name 2>&1
```

### Follow Logs (NOT for resources - would block)
```bash
docker logs --follow container_name 2>&1
```
- DO NOT use for resources (infinite stream)
- Could be useful for a future streaming tool

## Considerations

### Error Cases to Handle
1. **Docker not installed on host** - `docker` command not found
2. **Docker daemon not running** - Permission denied or socket errors
3. **Container doesn't exist** - Use `docker inspect` to check first
4. **Container stopped** - Can still read logs from stopped containers
5. **No logs available** - Empty output is valid, don't raise error
6. **Large log files** - Truncate with `--tail` parameter

### Resource URI Design Options

**Option A: Separate docker:// scheme per host**
```
docker://dookie/scout_mcp
docker://tootie/nginx
```
- Pros: Clean, matches existing host:// pattern
- Cons: Requires dynamic registration in lifespan

**Option B: Generic docker:// with host parameter**
```
docker://{host}/{container}
```
- Pros: Single resource registration
- Cons: Less discoverable, need to parse host from path

**Recommendation: Option A** - Matches existing pattern, more discoverable

### Query Parameters for Filtering
Consider adding optional parameters:
- `tail` - Number of lines (default: 100)
- `since` - Time filter (e.g., "5m", "2h", "2025-01-01")
- `timestamps` - Include timestamps (default: true)

MCP resources don't support query parameters directly, but could encode in path:
```
docker://dookie/scout_mcp?tail=50&since=5m
```

**Better approach:** Create separate resources or use tool instead:
```python
# Resource: default behavior (tail 100, timestamps)
docker://dookie/scout_mcp

# Tool: full control over parameters
scout("dookie:docker", "logs --tail 50 --since 5m scout_mcp")
```

### Stdout vs Stderr Merging
Docker logs splits stdout/stderr by default. Always use `2>&1` to merge:
```bash
docker logs scout_mcp 2>&1  # Merges stderr into stdout
```

Without merge, stderr goes to SSH stderr channel and may be lost.

### Security Considerations
- Docker socket requires root or docker group membership
- Validate container names to prevent command injection
- Use `{container!r}` for shell quoting
- No path traversal risk (containers are flat namespace)

### Performance Considerations
- Large containers may have GB of logs
- Always use `--tail` to limit output
- Consider adding max_size limit like cat_file pattern
- Connection pooling already handles reuse

## Next Steps

### Implementation Approach

1. **Create new executor function** (`services/executors.py`)
   ```python
   async def docker_logs(
       conn: "asyncssh.SSHClientConnection",
       container: str,
       tail: int = 100,
       since: str | None = None,
       timestamps: bool = True,
   ) -> tuple[str, bool]:
       """Fetch Docker logs from container."""
   ```

2. **Create docker_inspect executor** (`services/executors.py`)
   ```python
   async def docker_inspect(
       conn: "asyncssh.SSHClientConnection",
       container: str
   ) -> bool:
       """Check if Docker container exists."""
   ```

3. **Create docker_ps executor** (`services/executors.py`)
   ```python
   async def docker_ps(
       conn: "asyncssh.SSHClientConnection",
       all_containers: bool = True,
   ) -> str:
       """List Docker containers."""
   ```

4. **Create docker resource** (`resources/docker.py`)
   ```python
   async def docker_resource(host: str, container: str) -> str:
       """Read Docker logs for container on host."""
   ```

5. **Create list_docker_containers resource** (`resources/docker.py`)
   ```python
   async def list_docker_containers_resource(host: str) -> str:
       """List Docker containers on host."""
   ```

6. **Register resources in lifespan** (`server.py`)
   - Loop through hosts and register `docker://{host}/{{container}}` templates
   - Similar to existing host filesystem registration

7. **Add tests** (`tests/test_resources/test_docker.py`)
   - Mock SSH connection with docker command responses
   - Test container exists/doesn't exist
   - Test log truncation
   - Test error handling

8. **Update documentation**
   - Add docker:// URI examples to CLAUDE.md
   - Document available parameters
   - Add usage examples

### Example Resource Registration
```python
# In app_lifespan(), after host filesystem registration:
for host_name in hosts:
    def make_docker_handler(h: str) -> Any:
        async def handler(container: str) -> str:
            return await docker_resource(h, container)
        return handler

    server.resource(
        uri=f"docker://{host_name}/{{container}}",
        name=f"{host_name} docker logs",
        description=f"Read Docker container logs on {host_name}",
        mime_type="text/plain",
    )(make_docker_handler(host_name))
```

### Testing Strategy
1. Unit tests for docker executors (mock asyncssh.SSHClientConnection)
2. Integration tests for docker resource (mock connection pool)
3. End-to-end tests for dynamic registration (mock config)
4. Manual testing with real Docker containers on remote hosts

### Alternative: Tool-Based Approach
Instead of resources, could extend scout tool:
```python
scout("dookie:docker", "logs --tail 50 scout_mcp")
scout("dookie:docker", "ps -a")
```

**Pros:**
- No lifespan changes needed
- Full command flexibility
- Easier to implement

**Cons:**
- Less discoverable than dedicated docker:// URIs
- Doesn't show up in resource templates
- Mixing filesystem and docker operations in one tool

**Recommendation:** Start with dedicated docker resources for discoverability, but keep tool-based approach as fallback for advanced queries.

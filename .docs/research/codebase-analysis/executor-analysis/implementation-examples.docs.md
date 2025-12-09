# Executor Implementation Examples

## Code Patterns and Usage Examples

### Pattern 1: Basic File Read with Truncation

**Scenario**: Read a log file, handling truncation gracefully

```python
from scout_mcp.services import get_config, get_pool
from scout_mcp.services.executors import stat_path, cat_file

async def read_log_file(hostname: str, log_path: str) -> str:
    """Read a log file from remote host."""
    config = get_config()
    pool = get_pool()

    # Get SSH host config
    ssh_host = config.get_host(hostname)
    if not ssh_host:
        return f"Error: Unknown host {hostname}"

    # Get connection (reused if exists)
    try:
        conn = await pool.get_connection(ssh_host)
    except Exception as e:
        return f"Error: Cannot connect to {hostname}: {e}"

    # Check if path exists and is a file
    path_type = await stat_path(conn, log_path)
    if path_type is None:
        return f"Error: Path not found: {log_path}"
    if path_type != "file":
        return f"Error: {log_path} is a {path_type}, not a file"

    # Read file with size limit
    try:
        content, was_truncated = await cat_file(
            conn, log_path, config.max_file_size
        )

        if was_truncated:
            content += f"\n\n[Note: File truncated at {config.max_file_size} bytes]"

        return content

    except RuntimeError as e:
        return f"Error: Cannot read file: {e}"

# Usage
content = await read_log_file("dookie", "/var/log/app.log")
```

**Key Points:**
- Connection retry not shown (add try/except with remove_connection)
- `stat_path` validates existence before reading
- `cat_file` raises on error (catch RuntimeError)
- Always check `was_truncated` flag

---

### Pattern 2: Directory Listing with Tree Option

**Scenario**: List directory contents with optional tree view

```python
from scout_mcp.services.executors import stat_path, ls_dir, tree_dir

async def list_directory(
    conn,  # Already obtained from pool
    path: str,
    use_tree: bool = False,
    max_depth: int = 3
) -> str:
    """List directory contents, optionally as tree."""

    # Verify it's a directory
    path_type = await stat_path(conn, path)

    if path_type is None:
        raise ValueError(f"Path not found: {path}")

    if path_type != "directory":
        raise ValueError(f"{path} is not a directory")

    # Choose listing method
    if use_tree:
        listing = await tree_dir(conn, path, max_depth=max_depth)
    else:
        listing = await ls_dir(conn, path)

    return listing

# Usage
listing = await list_directory(conn, "/etc/nginx", use_tree=True)
```

**Key Points:**
- `tree_dir` gracefully falls back to `find` if tree unavailable
- No size limit on directory listings (assumes reasonable size)
- Both `ls_dir` and `tree_dir` raise RuntimeError on failure
- `max_depth` prevents infinite recursion

---

### Pattern 3: Command Execution with Timeout

**Scenario**: Search for pattern in files with timeout

```python
from scout_mcp.services.executors import run_command

async def search_pattern(
    conn,
    directory: str,
    pattern: str,
    file_pattern: str = "*.log",
    timeout: int = 30
) -> dict:
    """Search for pattern in files, return structured result."""

    # Build grep command
    command = f"grep -r '{pattern}' --include='{file_pattern}'"

    # Execute with timeout
    result = await run_command(conn, directory, command, timeout)

    # Structure the result
    return {
        "matches": result.output.strip() if result.output else None,
        "errors": result.error.strip() if result.error else None,
        "exit_code": result.returncode,
        "timed_out": result.returncode == 124,  # timeout command exit code
        "not_found": result.returncode == 1,     # grep no matches
        "success": result.returncode == 0
    }

# Usage
result = await search_pattern(conn, "/var/log", "ERROR", "*.log", timeout=60)

if result["timed_out"]:
    print("Search timed out after 60 seconds")
elif result["not_found"]:
    print("No matches found")
elif result["success"]:
    print(f"Found matches:\n{result['matches']}")
else:
    print(f"Search failed: {result['errors']}")
```

**Key Points:**
- `run_command` NEVER raises (always returns CommandResult)
- Timeout enforced by shell `timeout` command (not asyncio)
- Exit code 124 = timeout, 1 = grep no match, 0 = success
- Must handle stderr even on success (warnings)

---

### Pattern 4: Connection Retry with Cleanup

**Scenario**: Robust connection handling with automatic retry

```python
import logging
from scout_mcp.services import get_pool

logger = logging.getLogger(__name__)

async def get_connection_with_retry(ssh_host):
    """Get connection with one automatic retry."""
    pool = get_pool()

    try:
        conn = await pool.get_connection(ssh_host)
        return conn

    except Exception as first_error:
        # Log and retry once
        logger.warning(
            "Connection to %s failed: %s, retrying after cleanup",
            ssh_host.name,
            first_error
        )

        try:
            # Remove stale connection
            await pool.remove_connection(ssh_host.name)

            # Try again
            conn = await pool.get_connection(ssh_host)
            logger.info("Retry connection to %s succeeded", ssh_host.name)
            return conn

        except Exception as retry_error:
            logger.error(
                "Retry connection to %s failed: %s",
                ssh_host.name,
                retry_error
            )
            raise  # Give up after one retry

# Usage in tool/resource
try:
    conn = await get_connection_with_retry(ssh_host)
    result = await stat_path(conn, "/etc/passwd")
except Exception as e:
    return f"Error: Connection failed: {e}"
```

**Key Points:**
- One retry is the standard pattern (used in scout.py, scout_resource.py)
- Always remove connection before retry (clears stale state)
- Log at different levels: warning for first failure, error for final
- Don't retry forever (network issues won't self-resolve)

---

### Pattern 5: Binary vs Text Detection

**Scenario**: Detect binary files before attempting to read

```python
async def is_binary_file(conn, path: str) -> bool:
    """Check if file is binary using 'file' command."""
    result = await conn.run(f"file --mime-type -b {path!r}", check=False)

    if result.returncode != 0:
        return False  # Assume text if detection fails

    mime_type = result.stdout
    if isinstance(mime_type, bytes):
        mime_type = mime_type.decode("utf-8", errors="replace")

    mime_type = mime_type.strip()

    # Binary types: images, executables, archives, etc.
    binary_prefixes = [
        "application/octet-stream",
        "application/x-executable",
        "application/x-sharedlib",
        "application/zip",
        "application/gzip",
        "image/",
        "video/",
        "audio/",
    ]

    return any(mime_type.startswith(prefix) for prefix in binary_prefixes)

async def safe_cat_file(conn, path: str, max_size: int) -> str:
    """Read file only if it's text, error for binary."""

    # Check file type first
    if await is_binary_file(conn, path):
        raise ValueError(f"Cannot read binary file: {path}")

    # Read as text
    content, was_truncated = await cat_file(conn, path, max_size)

    if was_truncated:
        content += f"\n\n[Truncated at {max_size} bytes]"

    return content

# Usage
try:
    content = await safe_cat_file(conn, "/bin/bash", 1024)
except ValueError as e:
    print(f"Error: {e}")  # "Cannot read binary file: /bin/bash"
```

**Key Points:**
- Use `file --mime-type` to detect binary files
- Prevents garbage output from binary files
- Consider adding this to cat_file executor itself
- UTF-8 decode errors still possible (use errors="replace")

---

### Pattern 6: Docker Container Logs with Streaming

**Scenario**: Tail Docker container logs with timestamp filtering

```python
from scout_mcp.services.executors import docker_logs, docker_ps

async def get_container_logs(
    conn,
    container: str,
    tail: int = 100,
    since: str | None = None
) -> dict:
    """Get Docker container logs with metadata."""

    # Check if container exists
    logs, exists = await docker_logs(conn, container, tail=tail, timestamps=True)

    if not exists:
        # Get list of available containers
        containers = await docker_ps(conn)
        available = [c["name"] for c in containers]
        return {
            "error": f"Container '{container}' not found",
            "available": available
        }

    # Parse log lines
    log_lines = []
    for line in logs.strip().split("\n"):
        if not line:
            continue

        # Format: "2025-12-03T14:32:15.123456789Z log message"
        parts = line.split(" ", 1)
        if len(parts) == 2:
            timestamp, message = parts
            log_lines.append({
                "timestamp": timestamp,
                "message": message
            })
        else:
            log_lines.append({
                "timestamp": None,
                "message": line
            })

    # Filter by timestamp if provided
    if since:
        log_lines = [l for l in log_lines if l["timestamp"] and l["timestamp"] > since]

    return {
        "container": container,
        "lines": log_lines,
        "count": len(log_lines)
    }

# Usage
result = await get_container_logs(conn, "nginx", tail=50)
if "error" in result:
    print(f"Error: {result['error']}")
    print(f"Available containers: {result['available']}")
else:
    print(f"Found {result['count']} log lines")
    for log in result['lines']:
        print(f"[{log['timestamp']}] {log['message']}")
```

**Key Points:**
- `docker_logs` returns tuple: (logs, container_exists)
- Always check `exists` flag before parsing
- Docker logs format is timestamp + message
- Use `docker_ps()` to show available containers on error

---

### Pattern 7: ZFS Dataset Information

**Scenario**: Get ZFS pool and dataset information

```python
from scout_mcp.services.executors import (
    zfs_check,
    zfs_pools,
    zfs_datasets,
    zfs_snapshots
)

async def get_zfs_info(conn) -> dict:
    """Get comprehensive ZFS information."""

    # Check if ZFS is available
    if not await zfs_check(conn):
        return {"available": False, "error": "ZFS not installed or not accessible"}

    # Get all pools
    pools = await zfs_pools(conn)

    # Get datasets for each pool
    pool_data = []
    for pool in pools:
        pool_name = pool["name"]

        # Get datasets in this pool
        datasets = await zfs_datasets(conn, pool=pool_name)

        # Get recent snapshots
        snapshots = await zfs_snapshots(conn, dataset=pool_name, limit=10)

        pool_data.append({
            "name": pool_name,
            "size": pool["size"],
            "alloc": pool["alloc"],
            "free": pool["free"],
            "capacity": pool["cap"],
            "health": pool["health"],
            "dataset_count": len(datasets),
            "datasets": datasets,
            "recent_snapshots": snapshots
        })

    return {
        "available": True,
        "pool_count": len(pools),
        "pools": pool_data
    }

# Usage
zfs_info = await get_zfs_info(conn)

if not zfs_info["available"]:
    print(f"ZFS not available: {zfs_info['error']}")
else:
    print(f"Found {zfs_info['pool_count']} ZFS pools")

    for pool in zfs_info["pools"]:
        print(f"\nPool: {pool['name']}")
        print(f"  Health: {pool['health']}")
        print(f"  Capacity: {pool['capacity']}")
        print(f"  Datasets: {pool['dataset_count']}")
        print(f"  Recent snapshots: {len(pool['recent_snapshots'])}")
```

**Key Points:**
- Always call `zfs_check()` first (returns False if unavailable)
- All ZFS executors return empty lists on error (silent failure)
- Tab-delimited parsing built into executors
- Combine multiple executors for comprehensive view

---

### Pattern 8: System Log Reading with Fallback

**Scenario**: Read system logs from journalctl or syslog

```python
from scout_mcp.services.executors import syslog_read

async def get_system_errors(conn, lines: int = 100) -> dict:
    """Get system error logs from journalctl or syslog."""

    # Read logs with automatic fallback
    logs, source = await syslog_read(conn, lines=lines)

    if source == "none":
        return {
            "error": "No system logs available",
            "source": None,
            "logs": []
        }

    # Parse and filter for errors
    error_lines = []
    for line in logs.split("\n"):
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in ["error", "fail", "critical"]):
            error_lines.append(line)

    return {
        "source": source,  # "journalctl" or "syslog"
        "total_lines": len(logs.split("\n")),
        "error_count": len(error_lines),
        "errors": error_lines
    }

# Usage
result = await get_system_errors(conn, lines=200)

if "error" in result:
    print(f"Error: {result['error']}")
else:
    print(f"Log source: {result['source']}")
    print(f"Found {result['error_count']} errors in {result['total_lines']} lines")

    for error in result['errors'][:10]:  # Show first 10
        print(f"  {error}")
```

**Key Points:**
- `syslog_read` automatically tries journalctl → syslog → none
- Returns source type so caller knows what worked
- Journalctl preferred (systemd systems)
- Syslog fallback for older systems

---

### Pattern 9: Handling Encoding Errors

**Scenario**: Read files with potentially non-UTF-8 content

```python
async def safe_read_with_encoding_detection(conn, path: str, max_size: int) -> dict:
    """Read file with encoding detection and error handling."""

    # Try UTF-8 first (default)
    try:
        content, was_truncated = await cat_file(conn, path, max_size)

        # Check for replacement characters (encoding issues)
        replacement_count = content.count('\ufffd')

        if replacement_count > 0:
            # Many replacement chars = likely binary or wrong encoding
            return {
                "success": False,
                "error": "File contains non-UTF-8 data",
                "encoding_errors": replacement_count,
                "content": None
            }

        return {
            "success": True,
            "content": content,
            "was_truncated": was_truncated,
            "encoding": "utf-8"
        }

    except RuntimeError as e:
        return {
            "success": False,
            "error": str(e),
            "content": None
        }

# Usage
result = await safe_read_with_encoding_detection(conn, "/var/log/app.log", 1024)

if result["success"]:
    print(f"Read {len(result['content'])} chars ({result['encoding']})")
    if result["was_truncated"]:
        print("Note: Content was truncated")
else:
    print(f"Error: {result['error']}")
    if result.get("encoding_errors"):
        print(f"Found {result['encoding_errors']} encoding errors")
```

**Key Points:**
- All executors use `errors="replace"` for UTF-8 decoding
- Replacement character (U+FFFD) indicates encoding issues
- High count of replacements suggests binary file
- Consider checking MIME type before reading

---

### Pattern 10: Parallel Executor Calls

**Scenario**: Read multiple files concurrently from same host

```python
import asyncio
from scout_mcp.services.executors import cat_file, stat_path

async def read_multiple_files(
    conn,
    file_paths: list[str],
    max_size: int = 1048576
) -> dict[str, dict]:
    """Read multiple files concurrently using same connection."""

    async def read_single_file(path: str) -> dict:
        """Read one file with error handling."""
        try:
            # Check if exists and is file
            path_type = await stat_path(conn, path)

            if path_type is None:
                return {"error": "File not found", "content": None}

            if path_type != "file":
                return {"error": f"Not a file (is {path_type})", "content": None}

            # Read file
            content, was_truncated = await cat_file(conn, path, max_size)

            return {
                "content": content,
                "size": len(content),
                "was_truncated": was_truncated
            }

        except Exception as e:
            return {"error": str(e), "content": None}

    # Execute all reads concurrently
    results = await asyncio.gather(
        *[read_single_file(path) for path in file_paths]
    )

    # Build result dict
    return {path: result for path, result in zip(file_paths, results)}

# Usage
files_to_read = [
    "/etc/hostname",
    "/etc/hosts",
    "/etc/resolv.conf",
    "/var/log/syslog"
]

results = await read_multiple_files(conn, files_to_read, max_size=10240)

for path, result in results.items():
    if result.get("error"):
        print(f"{path}: ERROR - {result['error']}")
    else:
        print(f"{path}: {result['size']} bytes")
        if result["was_truncated"]:
            print(f"  (truncated)")
```

**Key Points:**
- Same SSH connection can handle concurrent commands
- asyncssh multiplexes commands over single connection
- Use `asyncio.gather` for parallel execution
- Each executor call is independent (no shared state)
- Much faster than sequential reads

---

## Common Pitfalls and Solutions

### Pitfall 1: Not Checking stat_path Result

```python
# BAD: Assume path exists
content, _ = await cat_file(conn, "/might/not/exist", 1024)
# Raises RuntimeError with confusing message

# GOOD: Check first
path_type = await stat_path(conn, "/might/not/exist")
if path_type is None:
    return "Path does not exist"
if path_type == "directory":
    return "Cannot read directory as file"

content, _ = await cat_file(conn, "/might/not/exist", 1024)
```

### Pitfall 2: Ignoring Truncation Flag

```python
# BAD: Don't check truncation
content, _ = await cat_file(conn, path, 1024)
# User doesn't know file was truncated

# GOOD: Inform user
content, was_truncated = await cat_file(conn, path, 1024)
if was_truncated:
    content += "\n\n[Note: File truncated at 1024 bytes]"
```

### Pitfall 3: Not Handling Command Timeouts

```python
# BAD: Ignore exit codes
result = await run_command(conn, "/tmp", "long-running-cmd", 10)
print(result.output)  # Might be empty if timed out

# GOOD: Check for timeout
result = await run_command(conn, "/tmp", "long-running-cmd", 10)
if result.returncode == 124:
    return "Command timed out after 10 seconds"
elif result.returncode != 0:
    return f"Command failed: {result.error}"
else:
    return result.output
```

### Pitfall 4: Forgetting Connection Retry

```python
# BAD: Single connection attempt
conn = await pool.get_connection(ssh_host)  # Might fail
result = await stat_path(conn, "/etc/passwd")

# GOOD: Retry pattern
try:
    conn = await pool.get_connection(ssh_host)
except Exception:
    await pool.remove_connection(ssh_host.name)
    conn = await pool.get_connection(ssh_host)  # Retry once

result = await stat_path(conn, "/etc/passwd")
```

### Pitfall 5: Shell Injection in Commands

```python
# BAD: User input directly in command
user_pattern = request.get("pattern")  # Might be "; rm -rf /"
result = await run_command(conn, "/tmp", f"grep {user_pattern} file.txt", 30)

# GOOD: Quote user input
import shlex
safe_pattern = shlex.quote(user_pattern)
result = await run_command(conn, "/tmp", f"grep {safe_pattern} file.txt", 30)
```

### Pitfall 6: Not Using Connection Pool

```python
# BAD: Create new connection every time
import asyncssh

async def read_file(hostname, path):
    conn = await asyncssh.connect(hostname, username="root")
    result = await conn.run(f"cat {path}")
    conn.close()
    return result.stdout

# GOOD: Use connection pool
from scout_mcp.services import get_pool

async def read_file(ssh_host, path):
    pool = get_pool()
    conn = await pool.get_connection(ssh_host)  # Reuses connection
    content, _ = await cat_file(conn, path, 1048576)
    # Don't close - pool manages lifecycle
    return content
```

These patterns and examples demonstrate proper usage of the Scout MCP executor layer for building robust remote file operations.

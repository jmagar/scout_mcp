# MCP Tools and Resources Interface Research

## Summary
Scout MCP exposes a **single tool** (`scout`) for interactive operations and **two categories of resources** (generic URI-based and host-specific dynamic resources). The tool provides command execution and tree views, while resources are read-only access patterns. Both use a one-retry connection pattern with automatic stale cleanup. Resources raise `ResourceError` on failure, tools return error strings.

## Key Components

### Tools
- `/mnt/cache/code/scout_mcp/scout_mcp/tools/scout.py`: Primary MCP tool with 4 operation modes (147 lines)

### Resources
- `/mnt/cache/code/scout_mcp/scout_mcp/resources/scout.py`: Generic `scout://` file/dir access (92 lines)
- `/mnt/cache/code/scout_mcp/scout_mcp/resources/hosts.py`: List available SSH hosts (63 lines)
- `/mnt/cache/code/scout_mcp/scout_mcp/resources/docker.py`: Docker container logs and listing (116 lines)
- `/mnt/cache/code/scout_mcp/scout_mcp/resources/compose.py`: Docker Compose operations (158 lines)
- `/mnt/cache/code/scout_mcp/scout_mcp/resources/zfs.py`: ZFS pool/dataset/snapshot access (273 lines)
- `/mnt/cache/code/scout_mcp/scout_mcp/resources/syslog.py`: System log reading (64 lines)

### Supporting Infrastructure
- `/mnt/cache/code/scout_mcp/scout_mcp/services/executors.py`: 23 SSH command executors (643 lines)
- `/mnt/cache/code/scout_mcp/scout_mcp/utils/parser.py`: URI parsing logic (41 lines)
- `/mnt/cache/code/scout_mcp/scout_mcp/server.py`: Dynamic resource registration at startup (449 lines)

## Implementation Patterns

### 1. Tool vs Resource Error Handling
**Tools** (`scout.py`):
```python
async def scout(target: str, query: str | None = None, tree: bool = False) -> str:
    try:
        parsed = parse_target(target)
    except ValueError as e:
        return f"Error: {e}"  # Returns error string, never raises
```

**Resources** (`scout_resource.py`):
```python
async def scout_resource(host: str, path: str) -> str:
    ssh_host = config.get_host(host)
    if ssh_host is None:
        raise ResourceError(f"Unknown host '{host}'...")  # Raises exception
```

**Pattern**: Tools are user-facing and return friendly error strings. Resources follow MCP spec and raise `ResourceError` for all failures.

### 2. Connection Retry Pattern
Both tools and resources use identical retry logic (`/mnt/cache/code/scout_mcp/scout_mcp/tools/scout.py:76-95`):
```python
try:
    conn = await pool.get_connection(ssh_host)
except Exception as first_error:
    logger.warning("Connection to %s failed: %s, retrying after cleanup", ...)
    try:
        await pool.remove_connection(ssh_host.name)  # Clear stale
        conn = await pool.get_connection(ssh_host)    # Retry once
        logger.info("Retry connection to %s succeeded", ...)
    except Exception as retry_error:
        # Tool: return error string
        # Resource: raise ResourceError
```

**Pattern**: One retry after removing stale connection. No infinite retry loops.

### 3. Dynamic Resource Registration
At startup, server registers 9 resource types per host (`/mnt/cache/code/scout_mcp/scout_mcp/server.py:195-361`):
```python
for host_name in hosts:
    # 1. Docker logs: tootie://docker/plex/logs
    server.resource(uri=f"{host_name}://docker/{{container}}/logs")(...)

    # 2. Docker list: tootie://docker
    server.resource(uri=f"{host_name}://docker")(...)

    # 3-5. Compose: list, file, logs
    # 6-9. ZFS: overview, pool, datasets, snapshots
    # 10. Syslog
    # 11. Filesystem wildcard (LAST): tootie://{path*}
```

**Pattern**: Specific patterns registered before filesystem wildcard to prevent shadowing. Closure factory functions preserve host context.

### 4. File Truncation
All file reads respect size limit (`/mnt/cache/code/scout_mcp/scout_mcp/services/executors.py:40-75`):
```python
async def cat_file(conn, path: str, max_size: int) -> tuple[str, bool]:
    result = await conn.run(f"head -c {max_size} {path!r}", check=False)
    content = stdout.decode("utf-8", errors="replace")
    was_truncated = len(content.encode("utf-8")) >= max_size
    return (content, was_truncated)
```

Callers append truncation notice:
```python
if was_truncated:
    contents += f"\n\n[truncated at {config.max_file_size} bytes]"
```

**Pattern**: Use `head -c` for size limiting, detect truncation by comparing output length to limit.

### 5. Directory Detection
Path type determined via `stat` command (`/mnt/cache/code/scout_mcp/scout_mcp/services/executors.py:11-37`):
```python
async def stat_path(conn, path: str) -> str | None:
    result = await conn.run(f'stat -c "%F" {path!r} 2>/dev/null', check=False)
    if result.returncode != 0:
        return None
    file_type = stdout.strip().lower()
    if "directory" in file_type:
        return "directory"
    elif "regular" in file_type or "file" in file_type:
        return "file"
```

**Pattern**: Single `stat` call determines file/directory/not-found, then dispatch to appropriate handler.

### 6. Tree View Fallback
Directory tree tries `tree` command first, falls back to `find` (`/mnt/cache/code/scout_mcp/scout_mcp/services/executors.py:105-147`):
```python
async def tree_dir(conn, path: str, max_depth: int = 3) -> str:
    # Try tree command
    result = await conn.run(f"tree -L {max_depth} --noreport {path!r} 2>/dev/null", check=False)
    if result.returncode == 0:
        return stdout

    # Fall back to find
    find_cmd = f"find {path!r} -maxdepth {max_depth} -type f -o -type d 2>/dev/null | head -100"
    result = await conn.run(find_cmd, check=False)
    return stdout
```

**Pattern**: Try preferred tool, check returncode, fall back to ubiquitous alternative.

### 7. Command Execution with Timeout
Commands run in working directory with timeout wrapper (`/mnt/cache/code/scout_mcp/scout_mcp/services/executors.py:150-190`):
```python
async def run_command(conn, working_dir: str, command: str, timeout: int) -> CommandResult:
    full_command = f"cd {working_dir!r} && timeout {timeout} {command}"
    result = await conn.run(full_command, check=False)
    return CommandResult(output=stdout, error=stderr, returncode=returncode)
```

**Pattern**: Shell quoting via `repr()`, timeout via GNU `timeout` command, always capture stdout/stderr/returncode.

### 8. Online Status Checking
Hosts list checks connectivity concurrently (`/mnt/cache/code/scout_mcp/scout_mcp/tools/scout.py:54-66`):
```python
host_endpoints = {name: (host.hostname, host.port) for name, host in hosts.items()}
online_status = await check_hosts_online(host_endpoints, timeout=2.0)

for name, host in sorted(hosts.items()):
    status_icon = "✓" if online_status.get(name) else "✗"
    status_text = "online" if online_status.get(name) else "offline"
```

**Pattern**: Batch all connectivity checks, run concurrently with short timeout, don't block on slow hosts.

### 9. Docker/Compose JSON Parsing
Docker Compose uses JSON output format (`/mnt/cache/code/scout_mcp/scout_mcp/services/executors.py:287-324`):
```python
async def compose_ls(conn) -> list[dict[str, str]]:
    cmd = "docker compose ls --format json 2>&1"
    result = await conn.run(cmd, check=False)

    try:
        projects = json.loads(stdout)
        return [{"name": p.get("Name", ""), "status": p.get("Status", ""), ...}]
    except json.JSONDecodeError:
        return []  # Compose not available
```

**Pattern**: Use `--format json` for structured output, gracefully handle parse failures as "not available".

### 10. ZFS Feature Detection
ZFS resources check availability before operations (`/mnt/cache/code/scout_mcp/scout_mcp/services/executors.py:423-433`):
```python
async def zfs_check(conn) -> bool:
    cmd = "command -v zpool >/dev/null 2>&1 && zpool status >/dev/null 2>&1"
    result = await conn.run(cmd, check=False)
    return result.returncode == 0
```

Resources return friendly message if not available:
```python
has_zfs = await zfs_check(conn)
if not has_zfs:
    return "ZFS is not available on this host.\n\nThis host either does not have ZFS installed..."
```

**Pattern**: Detect features via `command -v`, provide helpful error messages explaining what's missing.

## Considerations

### 1. Security: Path Traversal
**No explicit path validation** - relies on SSH server access controls:
```python
# scouts.py:41 - path taken directly from user
normalized_path = f"/{path}" if not path.startswith("/") else path
```

**Risk**: User can request any path their SSH user has access to (e.g., `/etc/shadow`).

**Mitigation**: This is by design - SSH user permissions provide the security boundary. The tool is meant for admin/debug use, not public exposure.

### 2. Command Injection via Shell Quoting
All paths/commands use `repr()` for shell quoting:
```python
# executors.py:17
result = await conn.run(f'stat -c "%F" {path!r} 2>/dev/null', check=False)

# executors.py:53
result = await conn.run(f"head -c {max_size} {path!r}", check=False)
```

**Safety**: Python's `repr()` produces shell-safe quoted strings. Handles spaces, special chars, quotes.

**Risk**: Query parameter in `scout()` tool is passed directly without escaping:
```python
# scout.py:161
full_command = f"cd {working_dir!r} && timeout {timeout} {command}"
```

The `command` variable is the raw user input, allowing arbitrary command execution.

**Mitigation**: This is intentional - the query parameter is meant for flexible command execution (grep, rg, find, etc.). Security relies on SSH user permissions.

### 3. File Size Limits
Default 1MB limit prevents memory exhaustion:
```python
# config.py (inferred from usage)
max_file_size = int(os.getenv("SCOUT_MAX_FILE_SIZE", "1048576"))
```

**Edge Case**: Binary files decoded as UTF-8 with `errors="replace"`:
```python
# executors.py:68
content = stdout.decode("utf-8", errors="replace")
```

**Result**: Binary files appear garbled but don't crash. No MIME type detection prevents this.

### 4. Connection Pooling Stale Detection
Pool marks connections stale if closed (`/mnt/cache/code/scout_mcp/scout_mcp/models/ssh.py` - inferred):
```python
@property
def is_stale(self) -> bool:
    return not self.connection or self.connection.is_closed()
```

**Race Condition**: Connection could close between `get_connection()` check and actual use.

**Mitigation**: One-retry pattern catches this - if command fails, retry after cleanup.

### 5. Resource URI Precedence
Order matters in registration (`server.py:195-361`):
1. Docker logs: `host://docker/{container}/logs`
2. Docker list: `host://docker`
3. Compose patterns
4. ZFS patterns
5. Syslog
6. **Filesystem wildcard LAST**: `host://{path*}`

**Gotcha**: If filesystem wildcard registered first, it would shadow all specific patterns.

**Why**: FastMCP matches most-specific-first. Wildcard must be last to act as fallback.

### 6. Error Message Consistency
**Tools** format errors for human readability:
```python
return f"Error: Unknown host '{parsed.host}'. Available: {available}"
```

**Resources** follow MCP spec:
```python
raise ResourceError(f"Unknown host '{host}'. Available: {available}")
```

**Consideration**: MCP clients handle `ResourceError` specially (may show in UI differently than tool string responses).

### 7. Concurrent Host Checking
`check_hosts_online()` uses `asyncio.gather()` with timeout (`utils/ping.py` - inferred):
```python
tasks = [check_host_online(hostname, port, timeout) for name, (hostname, port) in hosts.items()]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

**Performance**: 100 hosts with 2s timeout = 2s total, not 200s.

**Edge Case**: Single slow host doesn't block entire list.

### 8. Directory Listing Format
Uses `ls -la` for consistency:
```python
# executors.py:87
result = await conn.run(f"ls -la {path!r}", check=False)
```

**Output format** (relies on GNU coreutils):
```
total 48
drwxr-xr-x 3 root root 4096 Nov 28 ...
-rw-r--r-- 1 root root  286 Nov 28 file.py
```

**Platform dependency**: BSD `ls` has different flags/output. May break on macOS/FreeBSD.

### 9. Docker Container Detection
Uses stderr for "no such container" detection:
```python
# executors.py:225-227
if result.returncode != 0:
    if "No such container" in stdout or "no such container" in stdout.lower():
        return ("", False)
```

**Fragility**: Relies on Docker's error message text. If Docker changes message, detection breaks.

**Better approach**: Use `docker inspect` before `docker logs` (but adds extra command).

### 10. ZFS Snapshot Limit
Hardcoded 50 snapshot limit:
```python
# executors.py:552
async def zfs_snapshots(conn, dataset: str | None = None, limit: int = 50):
    cmd = f"zfs list -H -t snapshot ... | tail -{limit}"
```

**Why**: Prevents overwhelming output on systems with thousands of snapshots.

**Consideration**: No pagination - user can't access older snapshots beyond limit.

## Tool Signature Analysis

### scout() Tool
```python
async def scout(target: str, query: str | None = None, tree: bool = False) -> str
```

**Parameters**:
- `target` (required): `"hosts"` OR `"hostname:/path"`
- `query` (optional): Shell command to execute (e.g., `"rg 'TODO'"`)
- `tree` (optional): Show tree view instead of `ls -la`

**Return**: Always `str` (never raises). Error messages prefixed with `"Error: "`.

**Operation Modes**:
1. **List hosts**: `target="hosts"` → returns formatted host list with online status
2. **Read file**: `target="host:/path/to/file"` → returns file contents (truncated if >1MB)
3. **List directory**: `target="host:/path/to/dir"` → returns `ls -la` output
4. **Tree directory**: `target="host:/path/to/dir"`, `tree=True` → returns `tree` or `find` output
5. **Execute command**: `target="host:/path"`, `query="grep foo"` → returns stdout/stderr/exitcode

**Examples**:
```python
scout("hosts")                                    # List all configured hosts
scout("dookie:/var/log/app.log")                  # Read file
scout("tootie:/etc/nginx")                        # List directory
scout("tootie:/etc/nginx", tree=True)             # Show tree
scout("squirts:~/code", "rg 'TODO' -t py")        # Search for TODOs in Python files
```

**Error Cases**:
```python
scout("invalid")                    # → "Error: Invalid target 'invalid'. Expected 'host:/path' or 'hosts'"
scout("unknown-host:/path")         # → "Error: Unknown host 'unknown-host'. Available: dookie, tootie, squirts"
scout("host:/nonexistent")          # → "Error: Path not found: /nonexistent"
scout("host:/etc", "invalid-cmd")   # → "(command output with stderr and exit code)"
```

## Resource URI Patterns

### 1. Generic Resources (Statically Registered)

#### scout://{host}/{path*}
**Handler**: `scout_resource(host: str, path: str)`
**Purpose**: Generic file/directory access
**Examples**:
- `scout://dookie/var/log/app.log` → Read file
- `scout://tootie/etc/nginx` → List directory with `ls -la`

**Differences from tool**:
- No command execution (read-only)
- No tree view option
- Raises `ResourceError` instead of returning error strings
- Adds header to directory listings: `"# Directory: host:path\n\n"`

#### hosts://list
**Handler**: `list_hosts_resource()`
**Purpose**: Discover available SSH hosts
**Returns**: Formatted list with online status and example URIs
**Example output**:
```
Available SSH Hosts
========================================

[✓] dookie (online)
    SSH:      root@192.168.1.100:22
    Files:    dookie://path/to/file
    Docker:   dookie://docker/{container}/logs
    Compose:  dookie://compose/{project}/logs
    ZFS:      dookie://zfs
    Syslog:   dookie://syslog
    Generic:  scout://dookie/path/to/file
```

### 2. Dynamic Resources (Per-Host Registration)

For each configured host, 9 resource types are registered:

#### {host}://docker
**Handler**: `docker_list_resource(host: str)`
**Returns**: List of containers with status, image, log URIs
**Example**: `dookie://docker`

#### {host}://docker/{container}/logs
**Handler**: `docker_logs_resource(host: str, container: str)`
**Returns**: Last 100 lines with timestamps
**Example**: `dookie://docker/plex/logs`

#### {host}://compose
**Handler**: `compose_list_resource(host: str)`
**Returns**: List of compose projects with status, config paths
**Example**: `tootie://compose`

#### {host}://compose/{project}
**Handler**: `compose_file_resource(host: str, project: str)`
**Returns**: Docker Compose YAML file contents
**MIME**: `text/yaml`
**Example**: `tootie://compose/plex`

#### {host}://compose/{project}/logs
**Handler**: `compose_logs_resource(host: str, project: str)`
**Returns**: Last 100 lines of all stack containers with timestamps
**Example**: `tootie://compose/plex/logs`

#### {host}://zfs
**Handler**: `zfs_overview_resource(host: str)`
**Returns**: All pools with health, size, usage, links to detailed views
**Example**: `dookie://zfs`

#### {host}://zfs/{pool}
**Handler**: `zfs_pool_resource(host: str, pool: str)`
**Returns**: `zpool status` output for specific pool
**Example**: `dookie://zfs/cache`

#### {host}://zfs/{pool}/datasets
**Handler**: `zfs_datasets_resource(host: str, pool: str)`
**Returns**: All datasets in pool with used/avail/mountpoint
**Example**: `dookie://zfs/cache/datasets`

#### {host}://zfs/snapshots
**Handler**: `zfs_snapshots_resource(host: str)`
**Returns**: Last 50 snapshots across all pools with creation time
**Example**: `dookie://zfs/snapshots`

#### {host}://syslog
**Handler**: `syslog_resource(host: str, lines: int = 100)`
**Returns**: Last 100 lines from journalctl or /var/log/syslog
**Auto-detects**: Tries journalctl first, falls back to syslog
**Example**: `dookie://syslog`

#### {host}://{path*}
**Handler**: `_read_host_path(host: str, path: str)` → `scout_resource()`
**Purpose**: Filesystem wildcard (registered LAST)
**Examples**:
- `dookie://var/log/nginx/access.log` → Read file
- `tootie://etc/systemd/system` → List directory

## Return Value Formats

### Tool Return Formats

#### 1. Host List (target="hosts")
```
Available hosts:
  [✓] dookie (online) -> root@192.168.1.100:22
  [✗] tootie (offline) -> root@10.0.0.5:22
  [✓] squirts (online) -> admin@192.168.1.200:22
```

#### 2. File Contents
```
#!/bin/bash
echo "Hello World"
# ... file contents ...

[truncated at 1048576 bytes]  # If truncated
```

#### 3. Directory Listing
```
total 48
drwxr-xr-x 3 root root 4096 Nov 28 10:23 .
drwxr-xr-x 8 root root 4096 Nov 28 10:20 ..
-rw-r--r-- 1 root root  286 Nov 28 10:23 nginx.conf
drwxr-xr-x 2 root root 4096 Nov 28 10:23 sites-enabled
```

#### 4. Tree View
```
/etc/nginx
├── nginx.conf
├── mime.types
└── sites-enabled
    ├── default
    └── mysite.conf

1 directory, 4 files
```

Or (if `tree` not available):
```
/etc/nginx
/etc/nginx/nginx.conf
/etc/nginx/mime.types
/etc/nginx/sites-enabled
/etc/nginx/sites-enabled/default
```

#### 5. Command Output
```
src/main.py:42:# TODO: refactor this function
src/utils.py:15:# TODO: add error handling

[stderr]
grep: /some/file: Permission denied

[exit code: 1]
```

### Resource Return Formats

Resources add headers and formatting:

#### File Contents (scout://)
```
[raw file contents, no header]
```

#### Directory Listing (scout://)
```
# Directory: dookie:/etc/nginx

total 48
drwxr-xr-x 3 root root 4096 Nov 28 10:23 .
...
```

#### Docker Logs
```
# Container Logs: plex@dookie

2024-11-28T10:23:45.123Z Starting Plex Media Server...
2024-11-28T10:23:46.234Z Server started on port 32400
...
```

#### Compose Config
```
# Compose: plex@dookie
# File: /opt/plex/docker-compose.yaml

version: '3'
services:
  plex:
    image: plexinc/pms-docker
    ...
```

#### ZFS Overview
```
# ZFS Overview: dookie
==================================================

## Pools

● cache (ONLINE)
    Size:  10.9T
    Used:  7.2T (66%)
    Free:  3.7T
    View:  dookie://zfs/cache

● backup (ONLINE)
    Size:  5.5T
    Used:  2.1T (38%)
    Free:  3.4T
    View:  dookie://zfs/backup

## Quick Links

  Snapshots: dookie://zfs/snapshots
  cache datasets: dookie://zfs/cache/datasets
  backup datasets: dookie://zfs/backup/datasets
```

## Next Steps

### For New Feature Implementation

1. **Follow the Tool vs Resource Decision Tree**:
   - Need command execution or tree views? → Add to `scout()` tool
   - Read-only structured data? → Add new resource
   - Need both? → Implement executor in `services/executors.py`, expose via both

2. **Use Existing Patterns**:
   - Connection retry: Copy from `scout.py:76-95`
   - Feature detection: Copy from `executors.py:423-433` (zfs_check)
   - JSON parsing: Copy from `executors.py:287-324` (compose_ls)
   - Dynamic registration: Copy from `server.py:195-270` (docker resources)

3. **Security Checklist**:
   - [ ] All paths quoted with `repr()` in shell commands
   - [ ] Commands use `check=False` and capture returncode
   - [ ] Binary data decoded with `errors="replace"`
   - [ ] Size limits on unbounded output (files, logs, lists)
   - [ ] Timeout on long-running commands
   - [ ] Feature detection before usage (fail gracefully if missing)

4. **Testing Considerations**:
   - Mock `asyncssh.SSHClientConnection` for unit tests
   - Test both successful and failed connection scenarios
   - Test retry logic (first failure, second success)
   - Test resource not found (containers, compose projects, ZFS pools)
   - Test feature not available (Docker, Compose, ZFS on host)

5. **Documentation Requirements**:
   - Update `CLAUDE.md` with new operations
   - Add examples to `hosts://list` output if adding new resource types
   - Update `server.py` resource count calculation
   - Add URI patterns to host list resource output

### Architecture Observations

**Strengths**:
- Clean separation: tools (interactive) vs resources (read-only)
- Consistent retry pattern prevents stale connection issues
- Dynamic registration enables host-specific URIs
- Feature detection provides graceful degradation
- Concurrent host checking doesn't block on slow hosts

**Potential Improvements**:
- Pagination for large results (ZFS snapshots, Docker logs)
- MIME type detection for file resources
- Structured error responses (JSON) for programmatic clients
- Connection pool max size limit (currently unbounded)
- Platform detection (BSD vs GNU coreutils)
- Path validation/sanitization (if security boundary changes)

**Design Philosophy**:
- Security via SSH user permissions (not application layer)
- Fail gracefully with helpful error messages
- Prefer structured output (JSON) from commands when available
- One retry with cleanup, never infinite loops
- Short timeouts prevent hanging on dead hosts

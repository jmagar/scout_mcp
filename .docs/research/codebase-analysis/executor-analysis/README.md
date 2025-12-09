# Scout MCP Executor Research - Executive Summary

## Overview

This directory contains comprehensive research on the Scout MCP server's executor implementations - the core SSH command abstraction layer that powers all remote file and command operations.

## Research Documents

### 1. [executor-implementations.docs.md](executor-implementations.docs.md)
**Detailed implementation analysis of all executors**

Covers:
- Each executor's implementation details (18 total executors)
- Input/output patterns and return types
- Error handling strategies (5 distinct patterns)
- Timeout and size limit enforcement mechanisms
- Binary/text handling and encoding normalization

Key findings:
- All executors use `asyncssh.run()` with `check=False` for return code capture
- Consistent bytes/string normalization via UTF-8 decode with `errors="replace"`
- Timeout only on `run_command` (via shell `timeout` utility, not asyncio)
- Server-side size limiting using `head -c` for memory safety
- Five distinct error handling patterns based on use case

### 2. [architecture-flow.docs.md](architecture-flow.docs.md)
**Visual architecture diagrams and data flow analysis**

Covers:
- Complete request flow from MCP client to SSH server
- Connection lifecycle and pooling behavior
- Error propagation through layers
- Configuration flow from environment to executors
- Data model relationships and dependencies
- Thread safety and concurrency model

Key findings:
- Connection pool maintains one connection per host (reused across requests)
- Automatic cleanup every `idle_timeout / 2` seconds
- Connection retry pattern: fail → remove → retry once
- asyncssh connections are thread-safe for concurrent command execution
- Singleton pattern for Config and ConnectionPool (lazy initialization)

### 3. [implementation-examples.docs.md](implementation-examples.docs.md)
**Practical code patterns and usage examples**

Covers:
- 10 detailed usage patterns with complete code examples
- Common pitfalls and solutions
- Binary file detection before reading
- Docker/ZFS/syslog integration patterns
- Parallel executor calls using asyncio.gather
- Proper error handling for each executor type

Key findings:
- Always check `stat_path` before `cat_file` to avoid confusing errors
- Connection retry pattern is critical for reliability
- Same connection supports concurrent executor calls (SSH multiplexing)
- Truncation detection has off-by-one edge case (`>=` should be `>`)
- Shell injection risk in `run_command` (user input needs quoting)

## Quick Reference

### Core Executors (5)

| Executor | Purpose | Returns | Error Strategy |
|----------|---------|---------|----------------|
| `stat_path` | Check if file/directory/missing | `str \| None` | Return None |
| `cat_file` | Read file with size limit | `tuple[str, bool]` | Raise RuntimeError |
| `ls_dir` | List directory contents | `str` | Raise RuntimeError |
| `tree_dir` | Show directory tree | `str` | Graceful degradation |
| `run_command` | Execute arbitrary command | `CommandResult` | Never raises |

### Extended Executors (13)

- **Docker (4)**: `docker_logs`, `docker_ps`, `docker_inspect`, ...
- **Compose (3)**: `compose_ls`, `compose_config`, `compose_logs`
- **ZFS (5)**: `zfs_check`, `zfs_pools`, `zfs_datasets`, `zfs_snapshots`, `zfs_pool_status`
- **Syslog (1)**: `syslog_read` (journalctl → syslog fallback)

All extended executors use silent failure pattern (return empty lists/False on error).

### Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `SCOUT_MAX_FILE_SIZE` | 1048576 (1MB) | Size limit for cat_file |
| `SCOUT_COMMAND_TIMEOUT` | 30 seconds | Timeout for run_command |
| `SCOUT_IDLE_TIMEOUT` | 60 seconds | Connection pool cleanup interval |
| `SCOUT_TRANSPORT` | http | Protocol (http or stdio) |
| `SCOUT_HTTP_HOST` | 0.0.0.0 | HTTP bind address |
| `SCOUT_HTTP_PORT` | 8000 | HTTP server port |

Legacy `MCP_CAT_*` prefix still supported for backward compatibility.

### File Locations

```
/mnt/cache/code/scout_mcp/
├── scout_mcp/
│   ├── services/
│   │   ├── executors.py       # All executor implementations (643 lines)
│   │   ├── pool.py             # Connection pooling (171 lines)
│   │   └── state.py            # Global singletons
│   ├── models/
│   │   ├── command.py          # CommandResult dataclass
│   │   ├── ssh.py              # SSHHost, PooledConnection
│   │   └── target.py           # ScoutTarget
│   ├── tools/
│   │   └── scout.py            # Primary tool using executors
│   ├── resources/
│   │   ├── scout.py            # scout:// resource
│   │   └── hosts.py            # hosts:// resource
│   └── config.py               # Config with environment overrides
└── tests/
    └── test_executors.py       # Unit tests (180 lines)
```

## Critical Considerations for New Features

### 1. Always Use Connection Pool
```python
from scout_mcp.services import get_pool

pool = get_pool()
conn = await pool.get_connection(ssh_host)  # Reuses connection
# Never close connection - pool manages lifecycle
```

### 2. Implement Connection Retry
```python
try:
    conn = await pool.get_connection(ssh_host)
except Exception:
    await pool.remove_connection(ssh_host.name)
    conn = await pool.get_connection(ssh_host)  # Retry once
```

### 3. Check Path Type Before Operations
```python
path_type = await stat_path(conn, path)
if path_type is None:
    return "Path not found"
if path_type == "file":
    content, _ = await cat_file(conn, path, max_size)
else:
    listing = await ls_dir(conn, path)
```

### 4. Handle Truncation in cat_file
```python
content, was_truncated = await cat_file(conn, path, max_size)
if was_truncated:
    content += f"\n\n[File truncated at {max_size} bytes]"
```

### 5. Check Timeout Exit Codes
```python
result = await run_command(conn, working_dir, command, timeout)
if result.returncode == 124:
    return "Command timed out"
elif result.returncode != 0:
    return f"Command failed: {result.error}"
```

## Known Issues and Gotchas

1. **Truncation Detection Off-by-One**: Line 73 in executors.py uses `>=` instead of `>`, causing false positive when file is exactly `max_size` bytes

2. **No Binary File Detection**: `cat_file` will attempt to read any file, resulting in garbage output for binaries. Consider adding MIME type check.

3. **No Universal Timeout**: Only `run_command` has timeout. Other executors could hang on unresponsive SSH connections.

4. **Path Traversal Not Blocked**: Executors blindly execute paths. Security relies entirely on SSH server access controls.

5. **Shell Injection in run_command**: The `command` parameter is NOT quoted (intentional for pipes/redirects), so callers must sanitize user input.

6. **No Connection Limit**: Pool allows unlimited connections (one per host). Could exhaust SSH server's `MaxSessions`.

## Testing Coverage

- **Total tests**: 120+ across entire project
- **Coverage**: ~81% overall
- **Executor-specific**: `/mnt/cache/code/scout_mcp/tests/test_executors.py` (180 lines)
- **Gaps**: Docker/ZFS/Compose executors, encoding edge cases, truncation boundary

## Performance Characteristics

### Connection Pool Benefits
- **First request to host**: ~200-500ms (SSH handshake + command)
- **Subsequent requests**: ~50-100ms (command only, connection reused)
- **Cleanup overhead**: Background task every 30s (idle_timeout/2)

### Size Limits
- **cat_file**: 1MB default (configurable)
- **tree_dir**: 100 files max on find fallback
- **Command output**: No limit (relies on timeout)

### Concurrency
- **Multiple hosts**: Fully concurrent (separate connections)
- **Same host**: Fully concurrent (SSH multiplexing)
- **Connection pool lock**: Minimal contention (only during get/cleanup)

## Next Steps

See individual documents for:
- **Detailed implementation analysis** → [executor-implementations.docs.md](executor-implementations.docs.md)
- **Architecture and data flow** → [architecture-flow.docs.md](architecture-flow.docs.md)
- **Code patterns and examples** → [implementation-examples.docs.md](implementation-examples.docs.md)

## Research Metadata

- **Research Date**: 2025-12-03
- **Codebase Version**: refactor/cleanup-legacy-modules branch
- **Files Analyzed**: 12 source files, 1 test file
- **Total Lines Reviewed**: ~1,400 lines of implementation code
- **Documentation Generated**: 4 files, ~1,200 lines

## How to Use This Research

1. **Planning new features**: Start with implementation-examples.docs.md for patterns
2. **Understanding architecture**: Review architecture-flow.docs.md for system design
3. **Deep dive on specific executor**: See executor-implementations.docs.md
4. **Quick reference**: Use this README for common patterns and gotchas

All research documents are written for developers implementing new features or debugging existing executor behavior.

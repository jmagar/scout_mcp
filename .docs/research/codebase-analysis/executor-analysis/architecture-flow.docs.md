# Executor Architecture and Data Flow

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         MCP Client                               │
│                    (Claude Desktop/CLI)                          │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ MCP Protocol (HTTP or STDIO)
                 │
┌────────────────▼────────────────────────────────────────────────┐
│                      FastMCP Server                              │
│                     (server.py - 21 lines)                       │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Tools      │  │  Resources   │  │  Middleware  │          │
│  │  scout()     │  │ scout://     │  │  Error       │          │
│  │              │  │ hosts://     │  │  Timing      │          │
│  └──────┬───────┘  └──────┬───────┘  │  Logging     │          │
│         │                 │           └──────────────┘          │
└─────────┼─────────────────┼─────────────────────────────────────┘
          │                 │
          │   Shared Services Layer
          │                 │
┌─────────▼─────────────────▼─────────────────────────────────────┐
│                      Services Layer                              │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  State Management (state.py)                            │   │
│  │  - get_config() → Config singleton                      │   │
│  │  - get_pool() → ConnectionPool singleton                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ConnectionPool (pool.py - 171 lines)                   │   │
│  │  - get_connection(SSHHost) → asyncssh.Connection        │   │
│  │  - One connection per host (reused)                     │   │
│  │  - Auto cleanup (idle_timeout / 2 interval)             │   │
│  │  - Thread-safe via asyncio.Lock                         │   │
│  └─────────────┬───────────────────────────────────────────┘   │
│                │                                                 │
│  ┌─────────────▼───────────────────────────────────────────┐   │
│  │  Executors (executors.py - 643 lines)                   │   │
│  │                                                           │   │
│  │  Core (5):                                               │   │
│  │  - stat_path(conn, path) → str|None                     │   │
│  │  - cat_file(conn, path, max_size) → tuple[str, bool]    │   │
│  │  - ls_dir(conn, path) → str                             │   │
│  │  - tree_dir(conn, path, max_depth) → str                │   │
│  │  - run_command(conn, dir, cmd, timeout) → CommandResult │   │
│  │                                                           │   │
│  │  Extended (13):                                          │   │
│  │  - docker_* (4): logs, ps, inspect, ...                 │   │
│  │  - compose_* (3): ls, config, logs                      │   │
│  │  - zfs_* (5): check, pools, status, datasets, snapshots │   │
│  │  - syslog_read (1): journalctl/syslog reader            │   │
│  └─────────────┬───────────────────────────────────────────┘   │
└────────────────┼─────────────────────────────────────────────────┘
                 │
                 │ asyncssh (SSH Protocol)
                 │
┌────────────────▼─────────────────────────────────────────────────┐
│                     Remote SSH Hosts                              │
│              (Linux/Unix systems with SSH access)                 │
│                                                                    │
│  /var/log/app.log    /etc/nginx/    ~/code/    Docker/ZFS        │
└───────────────────────────────────────────────────────────────────┘
```

## Request Flow Diagram

### Tool Request: scout("dookie:/var/log/app.log")

```
1. MCP Client
   │
   ├─→ "scout" tool call with target="dookie:/var/log/app.log"
   │
2. FastMCP Server (server.py)
   │
   ├─→ Route to scout() function
   │
3. scout() Tool (tools/scout.py)
   │
   ├─→ parse_target("dookie:/var/log/app.log")
   │   └─→ ScoutTarget(host="dookie", path="/var/log/app.log")
   │
   ├─→ get_config() → Config singleton
   │   └─→ config.get_host("dookie") → SSHHost object
   │
   ├─→ get_pool() → ConnectionPool singleton
   │   └─→ pool.get_connection(SSHHost)
   │       │
   │       ├─→ Check cache for existing connection
   │       │   └─→ If exists and not stale: touch() and return
   │       │
   │       ├─→ If stale/missing: Create new
   │       │   └─→ asyncssh.connect(hostname, port, user, keys)
   │       │
   │       └─→ Return: asyncssh.SSHClientConnection
   │
   ├─→ stat_path(conn, "/var/log/app.log")
   │   │
   │   └─→ conn.run('stat -c "%F" /var/log/app.log 2>/dev/null')
   │       └─→ Returns: "file"
   │
   ├─→ cat_file(conn, "/var/log/app.log", max_size=1048576)
   │   │
   │   └─→ conn.run('head -c 1048576 /var/log/app.log')
   │       │
   │       ├─→ Decode bytes to UTF-8
   │       ├─→ Check truncation: len(content) >= max_size
   │       └─→ Returns: (content, False)
   │
   └─→ Return content string to MCP client
```

### Resource Request: scout://dookie/etc/nginx

```
1. MCP Client
   │
   ├─→ Read resource "scout://dookie/etc/nginx"
   │
2. FastMCP Server (server.py)
   │
   ├─→ Route to scout_resource(host="dookie", path="etc/nginx")
   │
3. scout_resource() (resources/scout.py)
   │
   ├─→ Normalize path: "etc/nginx" → "/etc/nginx"
   │
   ├─→ get_config() → Config
   │   └─→ config.get_host("dookie")
   │       └─→ Raises ResourceError if not found
   │
   ├─→ get_pool() → ConnectionPool
   │   └─→ pool.get_connection(SSHHost)
   │       └─→ (same connection reuse as above)
   │
   ├─→ stat_path(conn, "/etc/nginx")
   │   └─→ Returns: "directory"
   │
   ├─→ ls_dir(conn, "/etc/nginx")
   │   │
   │   └─→ conn.run('ls -la /etc/nginx')
   │       └─→ Returns formatted listing
   │
   └─→ Return "# Directory: dookie:/etc/nginx\n\n" + listing
```

### Command Execution: scout("dookie:/var/log", "grep ERROR app.log")

```
1. scout() receives query parameter
   │
   ├─→ Skip stat_path (command execution mode)
   │
   ├─→ run_command(conn, "/var/log", "grep ERROR app.log", timeout=30)
   │   │
   │   └─→ conn.run('cd /var/log && timeout 30 grep ERROR app.log')
   │       │
   │       ├─→ stdout: matching log lines
   │       ├─→ stderr: empty
   │       ├─→ returncode: 0 (or 1 if no match, 124 if timeout)
   │       │
   │       └─→ Returns: CommandResult(output, error, returncode)
   │
   └─→ Format output:
       ├─→ If output: include stdout
       ├─→ If error: include "[stderr]\n" + stderr
       ├─→ If returncode != 0: include "[exit code: N]"
       └─→ Return combined string
```

## Connection Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                     Connection States                            │
└─────────────────────────────────────────────────────────────────┘

1. First Request to Host
   │
   ├─→ pool.get_connection(ssh_host)
   │   ├─→ Lock acquired (asyncio.Lock)
   │   ├─→ Check _connections dict: NOT FOUND
   │   ├─→ asyncssh.connect(hostname, port, user, keys)
   │   ├─→ Create PooledConnection(conn, now())
   │   ├─→ Store in _connections[host.name]
   │   ├─→ Start cleanup task if not running
   │   └─→ Return connection
   │
   └─→ Executor uses connection for command

2. Subsequent Requests (Same Host)
   │
   ├─→ pool.get_connection(ssh_host)
   │   ├─→ Lock acquired
   │   ├─→ Check _connections dict: FOUND
   │   ├─→ Check is_stale: conn.is_closed → False
   │   ├─→ pooled.touch() → Update last_used timestamp
   │   └─→ Return existing connection
   │
   └─→ Executor reuses same SSH session

3. Connection Goes Stale (closed remotely)
   │
   ├─→ pool.get_connection(ssh_host)
   │   ├─→ Check is_stale: conn.is_closed → True
   │   ├─→ Log: "Connection is stale, creating new"
   │   ├─→ Create new connection (same as #1)
   │   └─→ Replace in pool
   │
   └─→ Old connection discarded

4. Background Cleanup Task
   │
   ├─→ Runs every idle_timeout / 2 seconds
   │   ├─→ Lock acquired
   │   ├─→ For each connection:
   │   │   ├─→ Check: last_used < now - idle_timeout
   │   │   ├─→ Check: is_stale (conn.is_closed)
   │   │   └─→ If either: close() and remove
   │   ├─→ If no connections left: task exits
   │   └─→ Lock released
   │
   └─→ Prevents indefinite idle connections

5. Connection Retry Pattern (in callers)
   │
   ├─→ try: pool.get_connection(ssh_host)
   │   └─→ Exception (network error, auth failure)
   │       │
   │       ├─→ pool.remove_connection(host.name)
   │       │   ├─→ Close and delete from pool
   │       │   └─→ Clear stale state
   │       │
   │       └─→ pool.get_connection(ssh_host) again
   │           └─→ Fresh connection attempt
```

## Error Propagation Patterns

### Pattern 1: Tools (Always Return String)

```
scout() Tool
  ├─→ try:
  │     ├─→ executor()
  │     └─→ Returns result
  │
  └─→ except Exception as e:
        └─→ return f"Error: {e}"

Result: Never raises, always returns user-facing error string
Used in: /mnt/cache/code/scout_mcp/scout_mcp/tools/scout.py
```

### Pattern 2: Resources (Raise ResourceError)

```
scout_resource()
  ├─→ Validation
  │     └─→ if invalid: raise ResourceError("message")
  │
  ├─→ try:
  │     └─→ executor()
  │
  └─→ except Exception as e:
        └─→ raise ResourceError("context") from e

Result: Raises MCP standard ResourceError
Used in: /mnt/cache/code/scout_mcp/scout_mcp/resources/scout.py
```

### Pattern 3: Executors (Mixed)

```
stat_path()
  └─→ if returncode != 0: return None  (expected failure)

cat_file(), ls_dir()
  └─→ if returncode != 0: raise RuntimeError(stderr)  (unexpected failure)

run_command()
  └─→ Always return CommandResult(output, error, returncode)  (no failure)

docker_*/zfs_*/compose_*
  └─→ if returncode != 0: return [] or ("", False)  (graceful degradation)
```

## Configuration Flow

```
Environment Variables
  │
  ├─→ SCOUT_TRANSPORT (http|stdio)
  ├─→ SCOUT_HTTP_HOST (0.0.0.0)
  ├─→ SCOUT_HTTP_PORT (8000)
  ├─→ SCOUT_MAX_FILE_SIZE (1048576 bytes)
  ├─→ SCOUT_COMMAND_TIMEOUT (30 seconds)
  └─→ SCOUT_IDLE_TIMEOUT (60 seconds)
      │
      ├─→ Legacy support: MCP_CAT_* prefix
      └─→ SCOUT_* takes precedence
          │
          ▼
Config.__post_init__()
  │
  ├─→ Parse environment variables
  ├─→ Apply overrides to dataclass fields
  └─→ Store in Config singleton
      │
      ▼
get_config() → Config instance
  │
  ├─→ Used by tools/resources for limits
  ├─→ max_file_size → cat_file(max_size)
  ├─→ command_timeout → run_command(timeout)
  └─→ idle_timeout → ConnectionPool(idle_timeout)
```

## Data Model Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                      Data Models                             │
└─────────────────────────────────────────────────────────────┘

ScoutTarget (parsed from user input)
  ├─ host: str | None              # "dookie"
  ├─ path: str                     # "/var/log/app.log"
  └─ is_hosts_command: bool        # False
      │
      │ Lookup
      ▼
SSHHost (from ~/.ssh/config)
  ├─ name: str                     # "dookie"
  ├─ hostname: str                 # "100.122.19.93"
  ├─ user: str                     # "root"
  ├─ port: int                     # 22
  └─ identity_file: str | None     # "/home/user/.ssh/id_ed25519"
      │
      │ Connect
      ▼
PooledConnection (in pool)
  ├─ connection: SSHClientConnection  # asyncssh object
  ├─ last_used: datetime               # 2025-12-03 14:32:15
  │
  └─ Methods:
      ├─ touch() → Update last_used to now()
      └─ is_stale → bool (checks conn.is_closed)
          │
          │ Execute
          ▼
CommandResult (from run_command)
  ├─ output: str                    # stdout content
  ├─ error: str                     # stderr content
  └─ returncode: int                # exit code (0 = success)
```

## Executor Dependency Graph

```
Higher-level Functions
  │
  ├─→ scout() tool
  │   ├─→ stat_path()      (determine type)
  │   ├─→ cat_file()       (if file)
  │   ├─→ ls_dir()         (if directory)
  │   ├─→ tree_dir()       (if tree=True)
  │   └─→ run_command()    (if query provided)
  │
  ├─→ scout_resource()
  │   ├─→ stat_path()      (determine type)
  │   ├─→ cat_file()       (if file)
  │   └─→ ls_dir()         (if directory)
  │
  └─→ (Future resources/tools could use)
      ├─→ docker_ps()
      ├─→ docker_logs()
      ├─→ zfs_pools()
      └─→ syslog_read()

All executors depend on:
  ├─→ asyncssh.SSHClientConnection (from pool)
  ├─→ Config (for max_size, timeout)
  └─→ Bytes/string normalization pattern
```

## Thread Safety and Concurrency

```
┌─────────────────────────────────────────────────────────────┐
│              Concurrency Safety Model                        │
└─────────────────────────────────────────────────────────────┘

ConnectionPool
  │
  ├─→ _lock: asyncio.Lock
  │   ├─→ Acquired in: get_connection(), _cleanup_idle()
  │   └─→ Prevents race conditions on _connections dict
  │
  ├─→ _connections: dict[str, PooledConnection]
  │   └─→ Protected by _lock (never accessed outside lock)
  │
  └─→ _cleanup_task: asyncio.Task | None
      └─→ Single background task per pool instance

SSH Connection
  │
  ├─→ asyncssh.SSHClientConnection
  │   └─→ Thread-safe for concurrent command execution
  │       └─→ Multiple executors can use same connection
  │
  └─→ conn.run() can be called concurrently
      └─→ SSH protocol multiplexes commands

Singleton Pattern
  │
  ├─→ _config: Config | None (module-level)
  │   └─→ Lazy initialization, no lock needed
  │       └─→ Python GIL prevents race in simple assignment
  │
  └─→ _pool: ConnectionPool | None (module-level)
      └─→ Same lazy pattern as config

Result: Safe for concurrent requests to different OR same hosts
```

This architecture enables efficient SSH connection reuse while maintaining clean separation of concerns across tools, resources, and core executor functions.

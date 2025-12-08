# services/

Stateful business logic: connection pooling, SSH command execution, global state.

## Modules

### state.py - Global Singletons
```python
_config: Config | None = None
_pool: ConnectionPool | None = None

def get_config() -> Config:    # Lazy singleton
def get_pool() -> ConnectionPool:  # Lazy singleton
```

Used throughout codebase without dependency injection:
```python
from scout_mcp.services import get_config, get_pool
config = get_config()
pool = get_pool()
```

### pool.py - Connection Pooling
```python
class ConnectionPool:
    def __init__(self, idle_timeout: int = 60)
    async def get_connection(self, host: SSHHost) -> asyncssh.SSHClientConnection
    async def remove_connection(self, host_name: str) -> None
    async def close_all(self) -> None
```

**Key Features:**
- One connection per host, reused across requests
- Thread-safe via `asyncio.Lock`
- Background cleanup every `idle_timeout/2` seconds
- Stale connections (closed or idle) auto-removed

**Connection Flow:**
1. Check if connection exists and not stale
2. If valid: touch() and return
3. If stale/missing: create new via asyncssh.connect()
4. Start cleanup task if first connection

### Localhost Detection

The server automatically detects when a target host is the same machine running Scout MCP:

- Compares SSH host names against server hostname (case-insensitive)
- Handles both short names and FQDNs
- Automatically uses `127.0.0.1:22` for localhost connections
- Avoids external IP connection issues for same-machine access

Example:
```python
# If Scout MCP is running on "tootie"
scout("tootie:/var/log")  # Connects to 127.0.0.1:22 (localhost)
scout("remote:/var/log")  # Connects to remote:22 (network)
```

This ensures resources work correctly when accessing the server's own filesystem, Docker containers, ZFS pools, etc.

### executors.py - SSH Commands
```python
async def stat_path(conn, path) -> str | None
    # Returns: 'file', 'directory', or None

async def cat_file(conn, path, max_size) -> tuple[str, bool]
    # Returns: (contents, was_truncated)

async def ls_dir(conn, path) -> str
    # Returns: ls -la output

async def tree_dir(conn, path, max_depth=3) -> str
    # Returns: tree or find output

async def run_command(conn, working_dir, command, timeout) -> CommandResult
    # Returns: CommandResult(output, error, returncode)
```

**Patterns:**
- All use `check=False` to capture return codes
- Decode bytes as UTF-8 with error replacement
- `tree_dir` falls back to `find` if `tree` not available

## Error Handling

Connection retry pattern (used in tools/resources):
```python
try:
    conn = await pool.get_connection(ssh_host)
except Exception:
    await pool.remove_connection(ssh_host.name)  # Clear stale
    conn = await pool.get_connection(ssh_host)   # Retry once
```

## Testing Utilities

```python
from scout_mcp.services import reset_state, set_config, set_pool

# In test fixtures:
reset_state()  # Clear all singletons

# For custom config in tests:
set_config(my_test_config)
set_pool(my_test_pool)
```

## Import

```python
from scout_mcp.services import get_config, get_pool, ConnectionPool
from scout_mcp.services import reset_state, set_config, set_pool  # Testing
from scout_mcp.services.executors import cat_file, ls_dir, run_command, stat_path, tree_dir
```

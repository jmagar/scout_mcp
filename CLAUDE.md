# Scout MCP

MCP server for remote file operations via SSH. Enables Claude to read files, list directories, and execute commands on remote Linux/Unix systems.

## Quick Reference

```bash
# Run server (HTTP on 0.0.0.0:8000)
uv run python -m scout_mcp

# Run server on custom port
SCOUT_HTTP_PORT=9000 uv run python -m scout_mcp

# Run server on localhost only
SCOUT_HTTP_HOST=127.0.0.1 uv run python -m scout_mcp

# Run with STDIO transport (for Claude Desktop)
SCOUT_TRANSPORT=stdio uv run python -m scout_mcp

# Run tests
uv run pytest tests/ -v

# Type checking
uv run mypy scout_mcp/

# Linting
uv run ruff check scout_mcp/ tests/ --fix
```

## Architecture

```
scout_mcp/
├── server.py          # FastMCP server (thin wrapper, wires components)
├── config.py          # SSH config parsing, host discovery
├── __main__.py        # Entry point
├── models/            # Dataclasses (ScoutTarget, SSHHost, CommandResult)
├── services/          # Business logic (pool, executors, state)
├── utils/             # Helpers (parser, ping, mime)
├── tools/             # MCP tools (scout)
├── resources/         # MCP resources (scout://, hosts://)
├── middleware/        # Request/response processing
└── prompts/           # MCP prompts (placeholder)
```

## Core Concepts

### Scout Tool
Primary interface for remote operations:
```python
scout("hosts")                           # List available SSH hosts
scout("hostname:/path")                  # Read file or list directory
scout("hostname:/path", "grep pattern")  # Execute command
scout("hostname:/path", tree=True)       # Show directory tree
```

### Resources
URI-based read-only access:
- `scout://{host}/{path}` - Read files or list directories
- `hosts://list` - List hosts with online status

### Connection Pooling
- One connection per host, reused across requests
- Automatic idle timeout cleanup (default: 60s)
- One-retry pattern on connection failure

### SSH Host Discovery
Reads `~/.ssh/config` for host definitions. Supports allowlist/blocklist filtering.

## Configuration

### Environment Variables
| Variable | Default | Purpose |
|----------|---------|---------|
| `SCOUT_TRANSPORT` | http | Transport protocol: "http" or "stdio" |
| `SCOUT_HTTP_HOST` | 0.0.0.0 | HTTP server bind address |
| `SCOUT_HTTP_PORT` | 8000 | HTTP server port |
| `SCOUT_MAX_FILE_SIZE` | 1048576 | Max file size in bytes (1MB) |
| `SCOUT_COMMAND_TIMEOUT` | 30 | Command timeout in seconds |
| `SCOUT_IDLE_TIMEOUT` | 60 | Connection idle timeout |
| `SCOUT_LOG_LEVEL` | DEBUG | Log level (DEBUG, INFO, WARNING, ERROR) |
| `SCOUT_LOG_PAYLOADS` | false | Enable payload logging |
| `SCOUT_SLOW_THRESHOLD_MS` | 1000 | Slow request threshold |
| `SCOUT_INCLUDE_TRACEBACK` | false | Include tracebacks in error logs |

Note: Legacy `MCP_CAT_*` prefix still supported for backward compatibility.

### Logging
The server provides comprehensive logging for debugging and monitoring:

```bash
# Run with debug logging
SCOUT_LOG_LEVEL=DEBUG uv run python -m scout_mcp

# View connection pool events
# Logs show: connection creation, reuse, cleanup, and failures
```

**Log events include:**
- Server startup/shutdown with host counts
- SSH connection creation and reuse
- Connection pool cleanup (idle/stale)
- Connection retry attempts
- Request timing (via middleware)

### MCP Client Configuration (HTTP - Default)
```json
{
  "mcpServers": {
    "scout_mcp": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

### MCP Client Configuration (STDIO - Legacy)
```json
{
  "mcpServers": {
    "scout_mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/code/scout_mcp", "python", "-m", "scout_mcp"],
      "env": {
        "SCOUT_TRANSPORT": "stdio"
      }
    }
  }
}
```

### Health Check Endpoint
When running with HTTP transport, a health check endpoint is available:
- **URL:** `GET /health`
- **Response:** `200 OK` with body `"OK"`

## Development

### Dependencies
- **fastmcp** >=2.0.0 - MCP server framework
- **asyncssh** >=2.14.0 - Async SSH client
- **pytest** >=8.0.0 - Testing
- **ruff** >=0.4.0 - Linting
- **mypy** >=1.10.0 - Type checking

### Code Style
- Python 3.11+, type hints required
- 88 char line length (Ruff default)
- f-strings for formatting
- Async/await for all I/O

### Testing
- 120+ tests, ~81% coverage
- `pytest-asyncio` with auto mode
- Mock SSH connections for unit tests

## Key Patterns

### Global State Singletons
```python
from scout_mcp.services import get_config, get_pool
config = get_config()  # Lazy singleton
pool = get_pool()      # Lazy singleton
```

### Error Handling
- Tools return error strings (never raise)
- Resources raise `ResourceError`
- Connection failures: auto-retry once with cleanup

### Async-First
All I/O is async. SSH operations use `asyncssh`, connection pool uses `asyncio.Lock`.

## Module Imports

```python
# Models
from scout_mcp.models import ScoutTarget, SSHHost, PooledConnection, CommandResult

# Services
from scout_mcp.services import get_config, get_pool, ConnectionPool
from scout_mcp.services.executors import cat_file, ls_dir, run_command, stat_path, tree_dir

# Utils
from scout_mcp.utils import parse_target, check_host_online, get_mime_type

# Tools/Resources
from scout_mcp.tools import scout
from scout_mcp.resources import scout_resource, list_hosts_resource
```

## Security Notes

- No path traversal protection (relies on SSH server access controls)
- File size limits prevent memory exhaustion
- Command execution uses shell quoting via `repr()`
- Assumes trusted MCP client (no auth on tool)

## Recent Changes

- **Comprehensive logging** for MCP client connections, SSH pool, and server lifecycle
- `SCOUT_LOG_LEVEL` environment variable for configurable log levels
- **Streamable HTTP transport by default** (was STDIO)
- Health check endpoint at `/health`
- Transport configuration via environment variables
- Middleware stack: ErrorHandling → Timing → Logging
- Module reorganization: flat → models/services/utils/tools/resources

# scout_mcp Package

Core MCP server package. Thin `server.py` wires together tools, resources, and middleware.

## Entry Points

- `__main__.py` - CLI entry: `uv run python -m scout_mcp`
- `server.py` - FastMCP server initialization (21 lines)
- `config.py` - SSH config parsing and host discovery

## Module Structure

| Directory | Purpose |
|-----------|---------|
| `models/` | Dataclasses: ScoutTarget, SSHHost, CommandResult |
| `services/` | State, connection pool, SSH executors |
| `utils/` | URI parsing, ping, MIME detection |
| `tools/` | MCP tool: `scout()` |
| `resources/` | MCP resources: `scout://`, `hosts://` |
| `middleware/` | Logging, timing, error handling |
| `prompts/` | MCP prompts (placeholder) |

## server.py Design

Thin wrapper that only wires components:
```python
from fastmcp import FastMCP
from scout_mcp.resources import list_hosts_resource, scout_resource
from scout_mcp.tools import scout

mcp = FastMCP("scout_mcp")
mcp.tool()(scout)
mcp.resource("scout://{host}/{path*}")(scout_resource)
mcp.resource("hosts://list")(list_hosts_resource)
```

All business logic lives in tools/, resources/, and services/.

## config.py

Parses `~/.ssh/config` for host definitions:
```python
@dataclass
class SSHHost:
    name: str           # Alias from ssh config
    hostname: str       # Actual hostname/IP
    user: str = "root"
    port: int = 22
    identity_file: str | None = None
```

Key methods:
- `get_hosts()` - All configured hosts
- `get_host(name)` - Single host lookup
- `_parse_ssh_config()` - Lazy parsing

## Execution Flow

```
Client Request
    ↓
FastMCP Server
    ↓
Middleware: Error → Timing → Logging
    ↓
Tool/Resource Handler
    ↓
services/ (state, pool, executors)
    ↓
asyncssh → Remote Host
```

## Import Patterns

```python
# From package root
from scout_mcp.config import Config
from scout_mcp.server import mcp

# From submodules
from scout_mcp.models import ScoutTarget, SSHHost
from scout_mcp.services import get_config, get_pool
from scout_mcp.utils import parse_target
from scout_mcp.tools import scout
from scout_mcp.resources import scout_resource
```

## Testing

Tests mirror this structure in `tests/`:
- `test_config.py` - Config parsing
- `test_integration.py` - End-to-end flows
- `test_module_structure.py` - Import verification
- `benchmarks/` - Performance tests

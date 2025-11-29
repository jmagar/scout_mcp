# resources/

MCP resource implementations. URI-based read-only access to remote systems.

## Resources

### scout_resource (`scout.py`)
```python
async def scout_resource(host: str, path: str) -> str:
    """Read file or list directory via scout:// URI."""
```

**URI Pattern:** `scout://{host}/{path*}`

**Examples:**
```
scout://dookie/var/log/app.log     → Read file
scout://tootie/etc/nginx           → List directory
scout://squirts/home/user/.bashrc  → Read file
```

**Error Handling:** Raises `ResourceError` (MCP standard) on:
- Unknown host
- Connection failure
- Path not found

### list_hosts_resource (`hosts.py`)
```python
async def list_hosts_resource() -> str:
    """List available SSH hosts with online status."""
```

**URI Pattern:** `hosts://list`

**Output Format:**
```
Available SSH Hosts
==================

✓ dookie (100.122.19.93:22)
✓ tootie (100.120.242.29:29229)
✗ squirts (10.0.0.5:22) - offline

Access via: scout://hostname/path
```

## Tools vs Resources

| Aspect | Tools | Resources |
|--------|-------|-----------|
| Error handling | Return strings | Raise ResourceError |
| Commands | Full (hosts, query, tree) | Read-only |
| URI format | `host:/path` | `scout://host/path` |

## Implementation Details

### scout_resource Flow
1. Validate host exists (raise ResourceError if not)
2. Normalize path (add leading `/` if missing)
3. Get connection with one retry
4. Stat path → file or directory
5. Return contents or listing

### hosts_resource Flow
1. Get all configured hosts
2. Concurrent connectivity check
3. Format with status indicators

## Import

```python
from scout_mcp.resources import scout_resource, list_hosts_resource
```

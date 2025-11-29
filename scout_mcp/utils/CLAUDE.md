# utils/

Stateless helper functions for parsing, network operations, and MIME detection.

## Modules

### parser.py - URI Parsing
```python
def parse_target(target: str) -> ScoutTarget:
    """Parse scout target URI.

    Formats:
        "hosts"           → ScoutTarget(host=None, is_hosts_command=True)
        "hostname:/path"  → ScoutTarget(host="hostname", path="/path")

    Raises:
        ValueError: Invalid format, empty host, or empty path
    """
```

**Validation:**
- Case-insensitive "hosts" matching
- Must contain exactly one colon
- Host and path cannot be empty

### ping.py - Host Connectivity
```python
async def check_host_online(hostname: str, port: int, timeout: float = 2.0) -> bool:
    """Check if host is reachable via TCP connection."""

async def check_hosts_online(
    hosts: dict[str, tuple[str, int]],
    timeout: float = 2.0
) -> dict[str, bool]:
    """Check multiple hosts concurrently."""
```

**Characteristics:**
- TCP socket connection only (no SSH auth)
- Default 2 second timeout
- Returns False on timeout or OSError

**Usage:**
```python
online = await check_host_online("192.168.1.100", 22)

status = await check_hosts_online({
    "host1": ("192.168.1.100", 22),
    "host2": ("10.0.0.5", 22)
})
# {"host1": True, "host2": False}
```

### mime.py - MIME Type Detection
```python
def get_mime_type(path: str) -> str:
    """Infer MIME type from file extension. Defaults to 'text/plain'."""
```

**Supported:**
- Config: .conf, .cfg, .ini, .yaml, .yml, .toml, .json, .xml
- Scripts: .sh, .py, .js, .ts, .rb, .go, .rs
- Web: .html, .css
- Docs: .md, .txt, .log, .csv

## Import

```python
from scout_mcp.utils import parse_target, check_host_online, check_hosts_online, get_mime_type
```

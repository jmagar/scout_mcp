# tools/

MCP tool implementations. Primary interface for Claude interactions.

## scout.py - Main Tool

```python
async def scout(
    target: str,
    query: str | None = None,
    tree: bool = False
) -> str:
    """Scout remote files and directories via SSH."""
```

### Commands

| Input | Behavior |
|-------|----------|
| `scout("hosts")` | List available SSH hosts |
| `scout("host:/path")` | Read file or list directory |
| `scout("host:/path", tree=True)` | Show directory tree |
| `scout("host:/path", "cmd")` | Execute shell command |
| `scout("host:/remote", beam="/local")` | Upload or download file |

### Examples

```python
# List hosts
scout("hosts")

# Read file
scout("dookie:/var/log/app.log")

# List directory
scout("tootie:/etc/nginx")

# Show tree
scout("squirts:/home/user/code", tree=True)

# Run command
scout("dookie:/var/log", "grep ERROR app.log")
scout("squirts:~/code", "rg 'TODO' -t py")

# Upload file (local → remote)
scout("shart:/mnt/cache/docs/file.txt", beam="/tmp/local.txt")

# Download file (remote → local)
scout("squirts:/etc/hostname", beam="/tmp/hostname")

# Auto-detects direction based on local file existence

# Remote-to-Remote Transfers

# Transfer between two remote hosts
scout(beam_source="shart:/mnt/data/file.txt", beam_target="squirts:/backup/file.txt")

# Optimized: If MCP server runs on shart, this becomes a direct upload
scout(beam_source="shart:/local/file.txt", beam_target="squirts:/remote/file.txt")

# Optimized: If MCP server runs on squirts, this becomes a direct download
scout(beam_source="shart:/remote/file.txt", beam_target="squirts:/local/file.txt")
```

### Error Handling

- **Invalid target**: Returns error message (no exception)
- **Unknown host**: Returns available hosts list
- **Connection failure**: Auto-retry once with stale cleanup
- **Path not found**: Returns error message
- **Command failure**: Returns stdout, stderr, and exit code

### File Truncation

Large files are truncated at `config.max_file_size`:
```
[file contents...]

---
[Note: File truncated at 1048576 bytes]
```

### Response Format

**File:**
```
[file contents]
```

**Directory:**
```
total 48
drwxr-xr-x 3 root root 4096 Nov 28 ...
-rw-r--r-- 1 root root  286 Nov 28 file.py
```

**Command:**
```
[stdout]

---
Errors:
[stderr]

Exit code: 0
```

## Import

```python
from scout_mcp.tools import scout
```

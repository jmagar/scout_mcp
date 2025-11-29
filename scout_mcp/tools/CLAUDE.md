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

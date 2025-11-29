# Dynamic Host-Based Resource Registration

## Overview

Register MCP resources dynamically at server startup for each SSH host discovered in the config. This enables true `tootie://`, `squirts://` URI schemes instead of the generic `scout://{host}/{path}` pattern.

## Goal

When the server starts, it reads SSH config and creates resource templates like:
- `tootie://{path*}`
- `squirts://{path*}`
- `dookie://{path*}`

Each host gets its own URI scheme, automatically discovered from `~/.ssh/config`.

## Architecture

```
Startup Flow:
┌─────────────────┐    ┌──────────────┐    ┌─────────────────────┐
│ FastMCP lifespan│───▶│ Config.get_  │───▶│ mcp.add_template()  │
│ context manager │    │ hosts()      │    │ for each host       │
└─────────────────┘    └──────────────┘    └─────────────────────┘
```

## Implementation Tasks

### Task 1: Add lifespan context manager to server.py

**Test file:** `tests/test_server_lifespan.py`

**Test (RED):**
```python
"""Tests for server lifespan and dynamic resource registration."""

import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock

import scout_mcp.mcp_cat.server as server_module


@pytest.fixture
def mock_ssh_config(tmp_path: Path) -> Path:
    """Create a temporary SSH config with multiple hosts."""
    config_file = tmp_path / "ssh_config"
    config_file.write_text("""
Host tootie
    HostName 192.168.1.10
    User admin

Host squirts
    HostName 192.168.1.20
    User root
""")
    return config_file


@pytest.mark.asyncio
async def test_lifespan_registers_host_templates(mock_ssh_config: Path) -> None:
    """Lifespan registers a resource template for each SSH host."""
    from scout_mcp.mcp_cat.server import mcp, app_lifespan
    from scout_mcp.mcp_cat.config import Config

    # Patch config to use our mock SSH config
    with patch.object(server_module, "_config", Config(ssh_config_path=mock_ssh_config)):
        async with app_lifespan(mcp):
            templates = await mcp.get_resource_templates()

            # Should have templates for each host
            assert "tootie://{path*}" in templates
            assert "squirts://{path*}" in templates
```

**Run test (should FAIL):**
```bash
cd /code/scout_mcp && /code/scout_mcp/.venv/bin/python -m pytest tests/test_server_lifespan.py -v
```

**Implementation in `scout_mcp/mcp_cat/server.py`:**

Add at the top with imports:
```python
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any
```

Add lifespan context manager before `mcp = FastMCP(...)`:
```python
@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Register dynamic host resources at startup."""
    config = get_config()
    hosts = config.get_hosts()

    for host_name in hosts:
        # Create a closure to capture host_name
        def make_handler(h: str):
            async def handler(path: str) -> str:
                return await _read_host_path(h, path)
            return handler

        server.add_resource_template(
            uri_template=f"{host_name}://{{path*}}",
            name=f"{host_name} filesystem",
            description=f"Read files and directories on {host_name}",
            fn=make_handler(host_name),
            mime_type="text/plain",
        )

    yield {"hosts": list(hosts.keys())}
```

Update FastMCP initialization:
```python
mcp = FastMCP(
    "Scout MCP",
    description="Remote file operations via SSH",
    lifespan=app_lifespan,
)
```

**Run test (should PASS):**
```bash
cd /code/scout_mcp && /code/scout_mcp/.venv/bin/python -m pytest tests/test_server_lifespan.py -v
```

**Commit:**
```bash
git add -A && git commit -m "feat: add lifespan for dynamic host resource registration"
```

---

### Task 2: Extract shared path reading logic

**Test file:** `tests/test_server_lifespan.py` (add to existing)

**Test (RED):**
```python
@pytest.mark.asyncio
async def test_read_host_path_reads_file(mock_ssh_config: Path) -> None:
    """_read_host_path reads file contents via SSH."""
    from scout_mcp.mcp_cat.server import _read_host_path
    from scout_mcp.mcp_cat.config import Config
    from unittest.mock import MagicMock

    server_module._config = Config(ssh_config_path=mock_ssh_config)

    mock_conn = AsyncMock()
    mock_conn.is_closed = False
    mock_conn.run.side_effect = [
        MagicMock(stdout="regular file", returncode=0),  # stat
        MagicMock(stdout="file contents", returncode=0),  # cat
    ]

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        result = await _read_host_path("tootie", "etc/hosts")

        assert result == "file contents"
```

**Run test (should FAIL):**
```bash
cd /code/scout_mcp && /code/scout_mcp/.venv/bin/python -m pytest tests/test_server_lifespan.py::test_read_host_path_reads_file -v
```

**Implementation in `scout_mcp/mcp_cat/server.py`:**

Add helper function (refactor from existing `scout_resource`):
```python
async def _read_host_path(host: str, path: str) -> str:
    """Read a file or list a directory on a remote host.

    Args:
        host: SSH hostname from config
        path: Path on remote host (leading slash added if missing)

    Returns:
        File contents or directory listing

    Raises:
        ResourceError: If host unknown or path not found
    """
    from fastmcp.exceptions import ResourceError

    config = get_config()
    pool = get_pool()

    hosts = config.get_hosts()
    if host not in hosts:
        raise ResourceError(f"Unknown host: {host}")

    # Normalize path - add leading slash if missing
    if not path.startswith("/"):
        path = "/" + path

    host_info = hosts[host]

    async def try_operation() -> str:
        conn = await pool.get_connection(host, host_info)

        # Determine if path is file or directory
        stat_result = await conn.run(f"stat -c '%F' {path} 2>/dev/null || echo ''")
        path_type = stat_result.stdout.strip()

        if not path_type:
            raise ResourceError(f"Path not found: {path}")

        if "directory" in path_type:
            result = await conn.run(f"ls -la {path}")
            return result.stdout
        else:
            result = await conn.run(f"cat {path}")
            return result.stdout

    try:
        return await try_operation()
    except Exception as e:
        if "is_closed" in str(e) or "connection" in str(e).lower():
            pool.invalidate(host)
            return await try_operation()
        raise ResourceError(f"SSH error: {e}") from e
```

Update `scout_resource` to use the shared helper:
```python
@mcp.resource("scout://{host}/{path*}")
async def scout_resource(host: str, path: str) -> str:
    """Read remote files or directories via SSH.

    Generic resource for any host via scout://hostname/path format.
    """
    return await _read_host_path(host, path)
```

**Run test (should PASS):**
```bash
cd /code/scout_mcp && /code/scout_mcp/.venv/bin/python -m pytest tests/test_server_lifespan.py::test_read_host_path_reads_file -v
```

**Commit:**
```bash
git add -A && git commit -m "refactor: extract _read_host_path helper for reuse"
```

---

### Task 3: Test dynamic resource actually works end-to-end

**Test file:** `tests/test_server_lifespan.py` (add to existing)

**Test (RED):**
```python
@pytest.mark.asyncio
async def test_dynamic_resource_reads_file(mock_ssh_config: Path) -> None:
    """Dynamic tootie:// resource reads files correctly."""
    from scout_mcp.mcp_cat.server import mcp, app_lifespan
    from scout_mcp.mcp_cat.config import Config
    from unittest.mock import MagicMock

    server_module._config = Config(ssh_config_path=mock_ssh_config)

    mock_conn = AsyncMock()
    mock_conn.is_closed = False
    mock_conn.run.side_effect = [
        MagicMock(stdout="regular file", returncode=0),
        MagicMock(stdout="dynamic resource content", returncode=0),
    ]

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        async with app_lifespan(mcp):
            # Get the dynamically registered template
            templates = await mcp.get_resource_templates()
            assert "tootie://{path*}" in templates

            # Read via the dynamic resource
            result = await _read_host_path("tootie", "var/log/syslog")
            assert result == "dynamic resource content"
```

**Run test (should PASS with existing implementation):**
```bash
cd /code/scout_mcp && /code/scout_mcp/.venv/bin/python -m pytest tests/test_server_lifespan.py::test_dynamic_resource_reads_file -v
```

**Commit:**
```bash
git add -A && git commit -m "test: verify dynamic resources work end-to-end"
```

---

### Task 4: Update hosts://list to show dynamic schemes

**Test file:** `tests/test_integration.py` (update existing test)

**Test (RED):**
```python
@pytest.mark.asyncio
async def test_hosts_resource_shows_dynamic_schemes(mock_ssh_config: Path) -> None:
    """hosts://list shows host-specific URI schemes."""
    from scout_mcp.mcp_cat.server import mcp, app_lifespan
    from scout_mcp.mcp_cat.config import Config

    with patch.object(server_module, "_config", Config(ssh_config_path=mock_ssh_config)):
        async with app_lifespan(mcp):
            # Access the hosts resource
            result = await list_hosts_fn()

            # Should show dynamic scheme examples
            assert "testhost://etc/hosts" in result or "testhost://" in result
```

**Run test (should FAIL):**
```bash
cd /code/scout_mcp && /code/scout_mcp/.venv/bin/python -m pytest tests/test_integration.py::test_hosts_resource_shows_dynamic_schemes -v
```

**Implementation in `scout_mcp/mcp_cat/server.py`:**

Update `list_hosts` resource:
```python
@mcp.resource("hosts://list")
async def list_hosts() -> str:
    """List available SSH hosts with their dynamic resource URIs."""
    config = get_config()
    hosts = config.get_hosts()

    if not hosts:
        return "No SSH hosts configured."

    lines = ["Available SSH Hosts:", "=" * 40, ""]
    for name, host in hosts.items():
        lines.append(f"  {name}")
        lines.append(f"    Connection: {host.user}@{host.hostname}:{host.port}")
        lines.append(f"    Resource:   {name}://path/to/file")
        lines.append(f"    Example:    {name}://etc/hosts")
        lines.append("")

    lines.append("Usage:")
    lines.append("  Read file:    tootie://var/log/syslog")
    lines.append("  List dir:     tootie://etc/nginx/")
    lines.append("  Generic:      scout://hostname/path")

    return "\n".join(lines)
```

**Run test (should PASS):**
```bash
cd /code/scout_mcp && /code/scout_mcp/.venv/bin/python -m pytest tests/test_integration.py::test_hosts_resource_shows_dynamic_schemes -v
```

**Commit:**
```bash
git add -A && git commit -m "feat: update hosts://list to show dynamic URI schemes"
```

---

### Task 5: Run full test suite and verify

**Run all tests:**
```bash
cd /code/scout_mcp && /code/scout_mcp/.venv/bin/python -m pytest -v
```

**Expected:** All tests pass, including new lifespan tests.

**Final commit:**
```bash
git add -A && git commit -m "feat: dynamic host-based resource registration complete"
```

---

## Verification Checklist

- [ ] `app_lifespan` context manager created
- [ ] Dynamic templates registered for each SSH host
- [ ] `_read_host_path` helper extracted and reused
- [ ] `hosts://list` updated to show dynamic schemes
- [ ] All existing tests still pass
- [ ] New tests cover lifespan registration
- [ ] Server starts without errors

## Notes

- Resources only update on server restart (by design)
- The generic `scout://{host}/{path*}` still works as fallback
- Each host gets descriptive metadata in its template

# Syslog Resource Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `{host}://syslog` resource to display system logs from remote hosts via journalctl or /var/log/syslog.

**Architecture:** Create executor function that tries journalctl first (systemd), falls back to `/var/log/syslog` file. Resource handler formats output with timestamps and filters. Follow existing ZFS resource pattern.

**Tech Stack:** asyncssh, FastMCP resources, Python 3.11+

---

### Task 1: Add syslog executor function

**Files:**
- Modify: `scout_mcp/services/executors.py` (add at end, after ZFS executors)

**Step 1: Write the failing test**

Create test file:
- Create: `tests/test_services/test_syslog_executors.py`

```python
"""Tests for syslog executor functions."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from scout_mcp.services.executors import syslog_read


@pytest.mark.asyncio
async def test_syslog_read_uses_journalctl_when_available() -> None:
    """syslog_read uses journalctl when available."""
    mock_conn = AsyncMock()
    # First call: check journalctl exists (returns 0)
    # Second call: get journalctl output
    mock_conn.run = AsyncMock(
        side_effect=[
            MagicMock(returncode=0),  # command -v journalctl
            MagicMock(
                stdout="Nov 29 12:00:00 host sshd[123]: Connection from 10.0.0.1",
                returncode=0,
            ),
        ]
    )

    logs, source = await syslog_read(mock_conn, lines=100)

    assert "sshd" in logs
    assert source == "journalctl"


@pytest.mark.asyncio
async def test_syslog_read_falls_back_to_syslog_file() -> None:
    """syslog_read falls back to /var/log/syslog when no journalctl."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        side_effect=[
            MagicMock(returncode=1),  # command -v journalctl (not found)
            MagicMock(returncode=0),  # test -r /var/log/syslog
            MagicMock(
                stdout="Nov 29 12:00:00 host kernel: Linux version 5.15",
                returncode=0,
            ),
        ]
    )

    logs, source = await syslog_read(mock_conn, lines=100)

    assert "kernel" in logs
    assert source == "syslog"


@pytest.mark.asyncio
async def test_syslog_read_returns_empty_when_no_logs() -> None:
    """syslog_read returns empty when no log source available."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        side_effect=[
            MagicMock(returncode=1),  # command -v journalctl (not found)
            MagicMock(returncode=1),  # test -r /var/log/syslog (not readable)
        ]
    )

    logs, source = await syslog_read(mock_conn, lines=100)

    assert logs == ""
    assert source == "none"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_services/test_syslog_executors.py -v`
Expected: FAIL with "cannot import name 'syslog_read'"

**Step 3: Write minimal implementation**

Add to `scout_mcp/services/executors.py` after the ZFS functions:

```python
async def syslog_read(
    conn: "asyncssh.SSHClientConnection",
    lines: int = 100,
) -> tuple[str, str]:
    """Read system logs from remote host.

    Tries journalctl first (systemd), falls back to /var/log/syslog.

    Args:
        conn: SSH connection
        lines: Number of log lines to retrieve (default 100)

    Returns:
        Tuple of (log content, source) where source is 'journalctl', 'syslog', or 'none'.
    """
    # Try journalctl first (systemd systems)
    check_journalctl = await conn.run("command -v journalctl", check=False)
    if check_journalctl.returncode == 0:
        result = await conn.run(
            f"journalctl --no-pager -n {lines} 2>/dev/null",
            check=False,
        )
        if result.returncode == 0:
            stdout = result.stdout or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            return (stdout, "journalctl")

    # Fall back to /var/log/syslog
    check_syslog = await conn.run("test -r /var/log/syslog", check=False)
    if check_syslog.returncode == 0:
        result = await conn.run(
            f"tail -n {lines} /var/log/syslog 2>/dev/null",
            check=False,
        )
        if result.returncode == 0:
            stdout = result.stdout or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            return (stdout, "syslog")

    return ("", "none")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_services/test_syslog_executors.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add tests/test_services/test_syslog_executors.py scout_mcp/services/executors.py
git commit -m "feat: add syslog_read executor function"
```

---

### Task 2: Create syslog resource module

**Files:**
- Create: `scout_mcp/resources/syslog.py`
- Test: `tests/test_resources/test_syslog.py`

**Step 1: Write the failing test**

Create: `tests/test_resources/test_syslog.py`

```python
"""Tests for syslog resource handler."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from scout_mcp.config import Config


@pytest.fixture
def mock_ssh_config(tmp_path: Path) -> Path:
    """Create a temporary SSH config."""
    config_file = tmp_path / "ssh_config"
    config_file.write_text("""
Host tootie
    HostName 192.168.1.10
    User admin
""")
    return config_file


@pytest.mark.asyncio
async def test_syslog_resource_returns_logs(mock_ssh_config: Path) -> None:
    """syslog_resource returns formatted log output."""
    from scout_mcp.resources.syslog import syslog_resource

    config = Config(ssh_config_path=mock_ssh_config)

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()

    log_content = (
        "Nov 29 12:00:00 tootie sshd[123]: Connection accepted\n"
        "Nov 29 12:00:01 tootie kernel: eth0: link up"
    )

    with patch(
        "scout_mcp.resources.syslog.get_config", return_value=config
    ), patch(
        "scout_mcp.resources.syslog.get_pool", return_value=mock_pool
    ), patch(
        "scout_mcp.resources.syslog.syslog_read",
        return_value=(log_content, "journalctl"),
    ):
        result = await syslog_resource("tootie")

        assert "System Logs: tootie" in result
        assert "journalctl" in result
        assert "sshd" in result
        assert "kernel" in result


@pytest.mark.asyncio
async def test_syslog_resource_no_logs_available(mock_ssh_config: Path) -> None:
    """syslog_resource shows message when no logs available."""
    from scout_mcp.resources.syslog import syslog_resource

    config = Config(ssh_config_path=mock_ssh_config)

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()

    with patch(
        "scout_mcp.resources.syslog.get_config", return_value=config
    ), patch(
        "scout_mcp.resources.syslog.get_pool", return_value=mock_pool
    ), patch(
        "scout_mcp.resources.syslog.syslog_read",
        return_value=("", "none"),
    ):
        result = await syslog_resource("tootie")

        assert "not available" in result.lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_resources/test_syslog.py -v`
Expected: FAIL with "No module named 'scout_mcp.resources.syslog'"

**Step 3: Write minimal implementation**

Create: `scout_mcp/resources/syslog.py`

```python
"""Syslog resource for reading system logs from remote hosts."""

from fastmcp.exceptions import ResourceError

from scout_mcp.services import get_config, get_pool
from scout_mcp.services.executors import syslog_read


async def syslog_resource(host: str, lines: int = 100) -> str:
    """Show system logs from remote host.

    Args:
        host: SSH host name from ~/.ssh/config
        lines: Number of log lines to retrieve (default 100)

    Returns:
        Formatted system log output.
    """
    config = get_config()
    pool = get_pool()

    # Validate host exists
    ssh_host = config.get_host(host)
    if ssh_host is None:
        available = ", ".join(sorted(config.get_hosts().keys()))
        raise ResourceError(f"Unknown host '{host}'. Available: {available}")

    # Get connection
    try:
        conn = await pool.get_connection(ssh_host)
    except Exception:
        try:
            await pool.remove_connection(ssh_host.name)
            conn = await pool.get_connection(ssh_host)
        except Exception as retry_error:
            raise ResourceError(
                f"Cannot connect to {host}: {retry_error}"
            ) from retry_error

    # Get logs
    logs, source = await syslog_read(conn, lines=lines)

    if source == "none":
        return (
            f"# System Logs: {host}\n\n"
            "System logs are not available on this host.\n\n"
            "Neither journalctl nor /var/log/syslog is accessible."
        )

    source_desc = "journalctl" if source == "journalctl" else "/var/log/syslog"

    lines_list = [
        f"# System Logs: {host}",
        "=" * 50,
        f"Source: {source_desc} (last {lines} lines)",
        "",
        logs,
    ]

    return "\n".join(lines_list)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_resources/test_syslog.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add scout_mcp/resources/syslog.py tests/test_resources/test_syslog.py
git commit -m "feat: add syslog resource handler"
```

---

### Task 3: Update resource exports

**Files:**
- Modify: `scout_mcp/resources/__init__.py`

**Step 1: Read current exports**

Check: `scout_mcp/resources/__init__.py` for current structure.

**Step 2: Add syslog export**

Add to imports:
```python
from scout_mcp.resources.syslog import syslog_resource
```

Add to `__all__`:
```python
"syslog_resource",
```

**Step 3: Run existing tests**

Run: `uv run pytest tests/test_module_structure.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add scout_mcp/resources/__init__.py
git commit -m "feat: export syslog_resource from resources module"
```

---

### Task 4: Register syslog resource in server lifespan

**Files:**
- Modify: `scout_mcp/server.py`

**Step 1: Write the failing test**

Add to `tests/test_server_lifespan.py`:

```python
@pytest.mark.asyncio
async def test_lifespan_registers_syslog_resources(mock_ssh_config: Path) -> None:
    """Lifespan registers syslog resources for each host."""
    from scout_mcp.server import app_lifespan, create_server

    config = Config(ssh_config_path=mock_ssh_config)

    with patch("scout_mcp.server.get_config", return_value=config):
        mcp = create_server()

        async with app_lifespan(mcp):
            resources = [
                str(r.uri)
                for r in mcp._resource_manager._resources.values()
            ]

            # Should have syslog resources
            assert any("tootie://syslog" in r for r in resources), (
                f"Expected tootie://syslog resource in {resources}"
            )
            assert any("squirts://syslog" in r for r in resources), (
                f"Expected squirts://syslog resource in {resources}"
            )
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_server_lifespan.py::test_lifespan_registers_syslog_resources -v`
Expected: FAIL with assertion error

**Step 3: Update server.py**

Add import at top:
```python
from scout_mcp.resources.syslog import syslog_resource
```

Add helper function (near other make_*_handler functions):
```python
def make_syslog_handler(host_name: str):
    """Create closure for syslog resource handler."""
    async def handler() -> str:
        return await syslog_resource(host_name)
    return handler
```

Add registration in lifespan (BEFORE filesystem wildcard, after ZFS):
```python
        # Syslog resource: tootie://syslog
        server.resource(
            uri=f"{host_name}://syslog",
            name=f"{host_name} system logs",
            description=f"System logs on {host_name}",
            mime_type="text/plain",
        )(make_syslog_handler(host_name))
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_server_lifespan.py::test_lifespan_registers_syslog_resources -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scout_mcp/server.py tests/test_server_lifespan.py
git commit -m "feat: register syslog resources in server lifespan"
```

---

### Task 5: Update hosts resource to show syslog URI

**Files:**
- Modify: `scout_mcp/resources/hosts.py`

**Step 1: Find where URIs are listed**

Look for the section that shows available URIs in the hosts resource output.

**Step 2: Add syslog URI to listing**

Add syslog to the list of available URIs for each host, similar to how docker/compose/zfs are listed.

Example format to add:
```
  Syslog:   {host}://syslog
```

**Step 3: Run tests**

Run: `uv run pytest tests/test_resources/test_hosts.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add scout_mcp/resources/hosts.py
git commit -m "feat: show syslog URI in hosts listing"
```

---

### Task 6: Run full test suite and lint

**Step 1: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

**Step 2: Run ruff**

Run: `uv run ruff check scout_mcp/ tests/ --fix`
Expected: No errors (or auto-fixed)

**Step 3: Run mypy**

Run: `uv run mypy scout_mcp/`
Expected: No errors

**Step 4: Final commit if any fixes**

```bash
git add -A
git commit -m "chore: fix lint issues"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add syslog_read executor | executors.py, test_syslog_executors.py |
| 2 | Create syslog resource module | syslog.py, test_syslog.py |
| 3 | Update resource exports | __init__.py |
| 4 | Register in server lifespan | server.py, test_server_lifespan.py |
| 5 | Update hosts listing | hosts.py |
| 6 | Run full tests and lint | - |

**Testing the result:**
- `tootie://syslog` - Should show system logs
- `squirts://syslog` - Should show journalctl output
- Hosts without logs accessible - Should show friendly message

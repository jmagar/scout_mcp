# MCP-Cat Enhancements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 6 enhancements to MCP-Cat: identity file support, hosts resource, truncation notices, tree command, env var config, and connection retry.

**Architecture:** Minimal changes to existing modules - each enhancement is isolated and testable.

**Tech Stack:** Python 3.11+, FastMCP, asyncssh

---

## Task 1: Identity File Support

**Files:**
- Modify: `scout_mcp/mcp_cat/pool.py:52-58`
- Modify: `tests/test_pool.py`

**Step 1: Write failing test for identity file**

Add to `tests/test_pool.py`:

```python
@pytest.mark.asyncio
async def test_get_connection_uses_identity_file(mock_ssh_host: SSHHost) -> None:
    """Connection uses identity file when specified."""
    mock_ssh_host.identity_file = "~/.ssh/id_ed25519"
    pool = ConnectionPool(idle_timeout=60)

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        await pool.get_connection(mock_ssh_host)

        mock_connect.assert_called_once()
        call_kwargs = mock_connect.call_args[1]
        assert "client_keys" in call_kwargs
        assert call_kwargs["client_keys"] == ["~/.ssh/id_ed25519"]
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_pool.py::test_get_connection_uses_identity_file -v
```

Expected: FAIL - client_keys not passed

**Step 3: Update pool.py to pass identity file**

Replace lines 52-58 in `scout_mcp/mcp_cat/pool.py`:

```python
            # Create new connection
            client_keys = [host.identity_file] if host.identity_file else None
            conn = await asyncssh.connect(
                host.hostname,
                port=host.port,
                username=host.user,
                known_hosts=None,
                client_keys=client_keys,
            )
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_pool.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add scout_mcp/mcp_cat/pool.py tests/test_pool.py
git commit -m "feat: add identity file support to SSH connections"
```

---

## Task 2: Environment Variable Configuration

**Files:**
- Modify: `scout_mcp/mcp_cat/config.py`
- Modify: `tests/test_config.py`

**Step 1: Write failing test for env var support**

Add to `tests/test_config.py`:

```python
def test_env_vars_override_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables override default config values."""
    monkeypatch.setenv("MCP_CAT_MAX_FILE_SIZE", "5242880")
    monkeypatch.setenv("MCP_CAT_COMMAND_TIMEOUT", "60")
    monkeypatch.setenv("MCP_CAT_IDLE_TIMEOUT", "120")

    config = Config(ssh_config_path=tmp_path / "nonexistent")

    assert config.max_file_size == 5242880
    assert config.command_timeout == 60
    assert config.idle_timeout == 120


def test_invalid_env_var_uses_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid environment variable values fall back to defaults."""
    monkeypatch.setenv("MCP_CAT_MAX_FILE_SIZE", "not_a_number")

    config = Config(ssh_config_path=tmp_path / "nonexistent")

    assert config.max_file_size == 1_048_576  # default
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_config.py::test_env_vars_override_defaults -v
```

Expected: FAIL - env vars not read

**Step 3: Add __post_init__ to Config**

Add after line 31 in `scout_mcp/mcp_cat/config.py`:

```python
    def __post_init__(self) -> None:
        """Apply environment variable overrides."""
        import os

        if val := os.getenv("MCP_CAT_MAX_FILE_SIZE"):
            try:
                self.max_file_size = int(val)
            except ValueError:
                pass  # Keep default

        if val := os.getenv("MCP_CAT_COMMAND_TIMEOUT"):
            try:
                self.command_timeout = int(val)
            except ValueError:
                pass

        if val := os.getenv("MCP_CAT_IDLE_TIMEOUT"):
            try:
                self.idle_timeout = int(val)
            except ValueError:
                pass
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_config.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add scout_mcp/mcp_cat/config.py tests/test_config.py
git commit -m "feat: add environment variable configuration support"
```

---

## Task 3: Hosts Resource with Online Status

**Files:**
- Modify: `scout_mcp/mcp_cat/server.py`
- Create: `scout_mcp/mcp_cat/ping.py`
- Modify: `tests/test_integration.py`

**Step 1: Create ping utility module**

Create `scout_mcp/mcp_cat/ping.py`:

```python
"""Host connectivity checking utilities."""

import asyncio
import socket


async def check_host_online(hostname: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a host is reachable via TCP connection.

    Args:
        hostname: Host to check.
        port: Port to connect to (usually SSH port).
        timeout: Connection timeout in seconds.

    Returns:
        True if host is reachable, False otherwise.
    """
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(hostname, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, asyncio.TimeoutError, socket.error):
        return False


async def check_hosts_online(
    hosts: dict[str, tuple[str, int]],
    timeout: float = 2.0,
) -> dict[str, bool]:
    """Check multiple hosts concurrently.

    Args:
        hosts: Dict of {name: (hostname, port)}.
        timeout: Connection timeout per host.

    Returns:
        Dict of {name: is_online}.
    """
    tasks = {
        name: check_host_online(hostname, port, timeout)
        for name, (hostname, port) in hosts.items()
    }

    results = {}
    for name, coro in tasks.items():
        results[name] = await coro

    return results
```

**Step 2: Write test for ping utility**

Create `tests/test_ping.py`:

```python
"""Tests for host connectivity checking."""

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from mcp_cat.ping import check_host_online, check_hosts_online


@pytest.mark.asyncio
async def test_check_host_online_reachable() -> None:
    """Returns True when host is reachable."""
    mock_writer = MagicMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()

    with patch("asyncio.open_connection", new_callable=AsyncMock) as mock_conn:
        mock_conn.return_value = (MagicMock(), mock_writer)

        result = await check_host_online("192.168.1.1", 22)

        assert result is True


@pytest.mark.asyncio
async def test_check_host_online_unreachable() -> None:
    """Returns False when host is unreachable."""
    with patch("asyncio.open_connection", new_callable=AsyncMock) as mock_conn:
        mock_conn.side_effect = asyncio.TimeoutError()

        result = await check_host_online("192.168.1.1", 22)

        assert result is False


@pytest.mark.asyncio
async def test_check_hosts_online_multiple() -> None:
    """Checks multiple hosts and returns status dict."""
    mock_writer = MagicMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()

    call_count = 0

    async def mock_open_connection(host: str, port: int) -> tuple:
        nonlocal call_count
        call_count += 1
        if host == "192.168.1.1":
            return (MagicMock(), mock_writer)
        raise asyncio.TimeoutError()

    with patch("asyncio.open_connection", side_effect=mock_open_connection):
        hosts = {
            "online_host": ("192.168.1.1", 22),
            "offline_host": ("192.168.1.2", 22),
        }

        results = await check_hosts_online(hosts)

        assert results["online_host"] is True
        assert results["offline_host"] is False
```

**Step 3: Run ping tests**

```bash
uv run pytest tests/test_ping.py -v
```

Expected: All tests PASS

**Step 4: Write failing test for hosts resource**

Add to `tests/test_integration.py`:

```python
def test_hosts_resource_exists() -> None:
    """Verify hosts resource is registered."""
    from mcp_cat.server import mcp

    # Check resource is registered (FastMCP stores resources differently)
    assert hasattr(mcp, "resource")
```
```

**Step 5: Add hosts resource to server.py**

Add after the scout tool in `scout_mcp/mcp_cat/server.py`:

```python
@mcp.resource("hosts://list")
async def list_hosts_resource() -> str:
    """List available SSH hosts with online status.

    Returns:
        Formatted list of available SSH hosts with connectivity status.
    """
    from mcp_cat.ping import check_hosts_online

    config = get_config()
    hosts = config.get_hosts()

    if not hosts:
        return "No SSH hosts configured."

    # Build dict for concurrent checking
    host_endpoints = {
        name: (host.hostname, host.port)
        for name, host in hosts.items()
    }

    # Check all hosts concurrently
    online_status = await check_hosts_online(host_endpoints, timeout=2.0)

    lines = ["Available SSH hosts:"]
    for name, host in sorted(hosts.items()):
        status = "online" if online_status.get(name) else "offline"
        status_icon = "\u2713" if online_status.get(name) else "\u2717"
        lines.append(
            f"  [{status_icon}] {name} -> {host.user}@{host.hostname}:{host.port} ({status})"
        )
    return "\n".join(lines)
```

**Step 6: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: All tests PASS

**Step 7: Commit**

```bash
git add scout_mcp/mcp_cat/ping.py scout_mcp/mcp_cat/server.py tests/test_ping.py tests/test_integration.py
git commit -m "feat: add hosts://list resource with online status"
```

---

## Task 4: File Truncation Notice

**Files:**
- Modify: `scout_mcp/mcp_cat/executors.py:51-82`
- Modify: `scout_mcp/mcp_cat/server.py`
- Modify: `tests/test_executors.py`

**Step 1: Write failing test for truncation info**

Add to `tests/test_executors.py`:

```python
@pytest.mark.asyncio
async def test_cat_file_returns_truncation_info(mock_connection: AsyncMock) -> None:
    """cat_file returns tuple with truncation flag."""
    # Simulate file exactly at max size
    content = "x" * 1024
    mock_connection.run.return_value = MagicMock(
        stdout=content,
        returncode=0
    )

    result, was_truncated = await cat_file(mock_connection, "/big/file", max_size=1024)

    assert result == content
    assert was_truncated is True


@pytest.mark.asyncio
async def test_cat_file_not_truncated(mock_connection: AsyncMock) -> None:
    """cat_file indicates when file is not truncated."""
    content = "small file"
    mock_connection.run.return_value = MagicMock(
        stdout=content,
        returncode=0
    )

    result, was_truncated = await cat_file(mock_connection, "/small/file", max_size=1024)

    assert result == content
    assert was_truncated is False
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_executors.py::test_cat_file_returns_truncation_info -v
```

Expected: FAIL - cat_file returns str, not tuple

**Step 3: Update cat_file to return truncation info**

Replace cat_file function in `scout_mcp/mcp_cat/executors.py`:

```python
async def cat_file(
    conn: "asyncssh.SSHClientConnection",
    path: str,
    max_size: int,
) -> tuple[str, bool]:
    """Read file contents, limited to max_size bytes.

    Returns:
        Tuple of (file contents, was_truncated flag).

    Raises:
        RuntimeError: If file cannot be read.
    """
    result = await conn.run(
        f'head -c {max_size} {path!r}',
        check=False
    )

    if result.returncode != 0:
        stderr = result.stderr
        if isinstance(stderr, bytes):
            error_msg = stderr.decode("utf-8", errors="replace")
        else:
            error_msg = stderr or ""
        raise RuntimeError(f"Failed to read {path}: {error_msg}")

    stdout = result.stdout
    if stdout is None:
        return "", False
    if isinstance(stdout, bytes):
        content = stdout.decode("utf-8", errors="replace")
    else:
        content = stdout

    # Check if we hit the size limit (likely truncated)
    was_truncated = len(content) >= max_size

    return content, was_truncated
```

**Step 4: Update server.py to show truncation notice**

Update the file reading section in `scout_mcp/mcp_cat/server.py`:

```python
        if path_type == "file":
            contents, was_truncated = await cat_file(
                conn, parsed.path, config.max_file_size
            )
            if was_truncated:
                return f"{contents}\n\n[truncated at {config.max_file_size} bytes]"
            return contents
```

**Step 5: Update existing cat_file tests**

Update `tests/test_executors.py` to handle tuple return:

```python
@pytest.mark.asyncio
async def test_cat_file_returns_contents(mock_connection: AsyncMock) -> None:
    """cat_file returns file contents."""
    mock_connection.run.return_value = MagicMock(
        stdout="file contents here",
        returncode=0
    )

    result, was_truncated = await cat_file(mock_connection, "/etc/hosts", max_size=1024)

    assert result == "file contents here"
    assert was_truncated is False


@pytest.mark.asyncio
async def test_cat_file_respects_max_size(mock_connection: AsyncMock) -> None:
    """cat_file uses head to limit file size."""
    mock_connection.run.return_value = MagicMock(
        stdout="truncated",
        returncode=0
    )

    result, _ = await cat_file(mock_connection, "/var/log/huge.log", max_size=1024)

    call_args = mock_connection.run.call_args[0][0]
    assert "head -c 1024" in call_args
```

**Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_executors.py tests/test_integration.py -v
```

Expected: All tests PASS

**Step 7: Commit**

```bash
git add scout_mcp/mcp_cat/executors.py scout_mcp/mcp_cat/server.py tests/test_executors.py
git commit -m "feat: add truncation notice for large files"
```

---

## Task 5: Tree Command for Directories

**Files:**
- Modify: `scout_mcp/mcp_cat/executors.py`
- Modify: `scout_mcp/mcp_cat/server.py`
- Modify: `tests/test_executors.py`

**Step 1: Write failing test for tree_dir**

Add to `tests/test_executors.py`:

```python
@pytest.mark.asyncio
async def test_tree_dir_returns_tree_output(mock_connection: AsyncMock) -> None:
    """tree_dir returns tree output when available."""
    mock_connection.run.return_value = MagicMock(
        stdout=".\n├── file1.txt\n└── subdir/",
        returncode=0
    )

    result = await tree_dir(mock_connection, "/home/user", max_depth=2)

    assert "file1.txt" in result
    assert "subdir" in result


@pytest.mark.asyncio
async def test_tree_dir_falls_back_to_find(mock_connection: AsyncMock) -> None:
    """tree_dir falls back to find when tree unavailable."""
    # First call (tree) fails, second call (find) succeeds
    mock_connection.run.side_effect = [
        MagicMock(stdout="", returncode=127),  # tree not found
        MagicMock(stdout="./file1.txt\n./subdir/file2.txt", returncode=0),
    ]

    result = await tree_dir(mock_connection, "/home/user", max_depth=2)

    assert "file1.txt" in result
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_executors.py::test_tree_dir_returns_tree_output -v
```

Expected: FAIL - tree_dir not defined

**Step 3: Add tree_dir function to executors.py**

Add after ls_dir in `scout_mcp/mcp_cat/executors.py`:

```python
async def tree_dir(
    conn: "asyncssh.SSHClientConnection",
    path: str,
    max_depth: int = 3,
) -> str:
    """Show directory tree structure.

    Tries 'tree' command first, falls back to 'find' if unavailable.

    Returns:
        Directory tree as formatted string.
    """
    # Try tree command first
    result = await conn.run(
        f'tree -L {max_depth} --noreport {path!r} 2>/dev/null',
        check=False
    )

    if result.returncode == 0:
        stdout = result.stdout
        if stdout is None:
            return ""
        if isinstance(stdout, bytes):
            return stdout.decode("utf-8", errors="replace")
        return stdout

    # Fall back to find
    result = await conn.run(
        f'find {path!r} -maxdepth {max_depth} -type f -o -type d 2>/dev/null | head -100',
        check=False
    )

    stdout = result.stdout
    if stdout is None:
        return ""
    if isinstance(stdout, bytes):
        return stdout.decode("utf-8", errors="replace")
    return stdout
```

**Step 4: Update server.py to add tree parameter**

Update the scout tool signature and directory handling in `scout_mcp/mcp_cat/server.py`:

```python
@mcp.tool()
async def scout(
    target: str,
    query: str | None = None,
    tree: bool = False,
) -> str:
    """Scout remote files and directories via SSH.

    Args:
        target: Either 'hosts' to list available hosts,
            or 'hostname:/path' to target a path.
        query: Optional shell command to execute
            (e.g., "rg 'pattern'", "find . -name '*.py'").
        tree: If True, show directory tree instead of ls -la.
    ...
```

And update the directory listing section:

```python
        else:
            if tree:
                from mcp_cat.executors import tree_dir
                listing = await tree_dir(conn, parsed.path)
            else:
                listing = await ls_dir(conn, parsed.path)
            return listing
```

**Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/ -v
```

Expected: All tests PASS

**Step 6: Commit**

```bash
git add scout_mcp/mcp_cat/executors.py scout_mcp/mcp_cat/server.py tests/test_executors.py
git commit -m "feat: add tree command for directory visualization"
```

---

## Task 6: Connection Retry Logic

**Files:**
- Modify: `scout_mcp/mcp_cat/pool.py`
- Modify: `scout_mcp/mcp_cat/server.py`
- Modify: `tests/test_pool.py`

**Step 1: Write failing test for remove_connection**

Add to `tests/test_pool.py`:

```python
@pytest.mark.asyncio
async def test_remove_connection_clears_from_pool(mock_ssh_host: SSHHost) -> None:
    """remove_connection removes host from pool."""
    pool = ConnectionPool(idle_timeout=60)

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        await pool.get_connection(mock_ssh_host)
        assert mock_ssh_host.name in pool._connections

        await pool.remove_connection(mock_ssh_host.name)
        assert mock_ssh_host.name not in pool._connections
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_pool.py::test_remove_connection_clears_from_pool -v
```

Expected: FAIL - remove_connection not defined

**Step 3: Add remove_connection to pool.py**

Add after close_all in `scout_mcp/mcp_cat/pool.py`:

```python
    async def remove_connection(self, host_name: str) -> None:
        """Remove a specific connection from the pool.

        Args:
            host_name: Name of the host to remove.
        """
        async with self._lock:
            if host_name in self._connections:
                pooled = self._connections[host_name]
                pooled.connection.close()
                del self._connections[host_name]
```

**Step 4: Update server.py with retry logic**

Update the connection section in `scout_mcp/mcp_cat/server.py`:

```python
    # Get connection (with one retry on failure)
    try:
        conn = await pool.get_connection(ssh_host)
    except Exception as first_error:
        # Connection failed - clear stale connection and retry once
        try:
            await pool.remove_connection(ssh_host.name)
            conn = await pool.get_connection(ssh_host)
        except Exception as retry_error:
            return f"Error: Cannot connect to {ssh_host.name}: {retry_error}"
```

**Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/ -v
```

Expected: All tests PASS

**Step 6: Run linting and type checking**

```bash
uv run ruff check scout_mcp/ tests/
uv run mypy scout_mcp/
```

Expected: No errors

**Step 7: Commit**

```bash
git add scout_mcp/mcp_cat/pool.py scout_mcp/mcp_cat/server.py tests/test_pool.py
git commit -m "feat: add connection retry logic for dropped SSH sessions"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Identity file support | pool.py, test_pool.py |
| 2 | Environment variable config | config.py, test_config.py |
| 3 | Hosts resource with online status | ping.py, server.py, test_ping.py, test_integration.py |
| 4 | File truncation notice | executors.py, server.py, test_executors.py |
| 5 | Tree command | executors.py, server.py, test_executors.py |
| 6 | Connection retry | pool.py, server.py, test_pool.py |

**Total: 6 tasks, ~35 steps**

# Docker Logs Resource Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Add Docker container log resources to scout_mcp, enabling URIs like `tootie://docker/plex/logs` to fetch container logs from remote hosts.

**URI Pattern:** `{host}://docker/{container}/logs`

**Example:** `tootie://docker/plex/logs` → fetches logs from `plex` container on `tootie`

---

## Task 1: Add Docker Executor Functions

**File:** `scout_mcp/services/executors.py`

**What:** Add three new executor functions for Docker operations.

**Add after line 191 (after `run_command` function):**

```python
async def docker_logs(
    conn: "asyncssh.SSHClientConnection",
    container: str,
    tail: int = 100,
    timestamps: bool = True,
) -> tuple[str, bool]:
    """Fetch Docker container logs.

    Args:
        conn: SSH connection to execute command on.
        container: Container name or ID.
        tail: Number of lines from end (default: 100).
        timestamps: Include timestamps in output (default: True).

    Returns:
        Tuple of (logs content, container_exists boolean).

    Raises:
        RuntimeError: If Docker command fails unexpectedly.
    """
    ts_flag = "--timestamps" if timestamps else ""
    cmd = f"docker logs --tail {tail} {ts_flag} {container!r} 2>&1"

    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        stdout = ""
    elif isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")

    # Check for "No such container" error
    if result.returncode != 0:
        if "No such container" in stdout or "no such container" in stdout.lower():
            return ("", False)
        # Docker daemon not running or other error
        raise RuntimeError(f"Docker error: {stdout}")

    return (stdout, True)


async def docker_ps(
    conn: "asyncssh.SSHClientConnection",
) -> list[dict[str, str]]:
    """List Docker containers on remote host.

    Returns:
        List of dicts with 'name', 'status', 'image' keys.
        Empty list if Docker not available.
    """
    cmd = "docker ps -a --format '{{.Names}}\\t{{.Status}}\\t{{.Image}}' 2>&1"

    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        return []
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")

    # Check for Docker errors
    if result.returncode != 0:
        return []  # Docker not available

    containers = []
    for line in stdout.strip().split("\n"):
        if not line or "\t" not in line:
            continue
        parts = line.split("\t", 2)
        if len(parts) >= 3:
            containers.append({
                "name": parts[0],
                "status": parts[1],
                "image": parts[2],
            })

    return containers


async def docker_inspect(
    conn: "asyncssh.SSHClientConnection",
    container: str,
) -> bool:
    """Check if Docker container exists.

    Returns:
        True if container exists, False otherwise.
    """
    cmd = f"docker inspect --format '{{{{.Name}}}}' {container!r} 2>/dev/null"

    result = await conn.run(cmd, check=False)
    return result.returncode == 0
```

**Verify:** Run `uv run pytest tests/test_services/test_executors.py -v -k docker` (will fail until tests added).

---

## Task 2: Create Docker Resource Module

**File:** `scout_mcp/resources/docker.py` (NEW FILE)

**What:** Create the Docker logs resource handler.

```python
"""Docker resource for reading container logs from remote hosts."""

from fastmcp.exceptions import ResourceError

from scout_mcp.services import get_config, get_pool
from scout_mcp.services.executors import docker_logs, docker_ps


async def docker_logs_resource(host: str, container: str) -> str:
    """Read Docker container logs from remote host.

    Args:
        host: SSH host name from ~/.ssh/config
        container: Docker container name

    Returns:
        Container log output with timestamps.

    Raises:
        ResourceError: If host unknown, connection fails, or container not found.
    """
    config = get_config()
    pool = get_pool()

    # Validate host exists
    ssh_host = config.get_host(host)
    if ssh_host is None:
        available = ", ".join(sorted(config.get_hosts().keys()))
        raise ResourceError(f"Unknown host '{host}'. Available: {available}")

    # Get connection (with one retry on failure)
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

    # Fetch logs
    try:
        logs, exists = await docker_logs(conn, container, tail=100, timestamps=True)
    except RuntimeError as e:
        raise ResourceError(f"Docker error on {host}: {e}") from e

    if not exists:
        raise ResourceError(
            f"Container '{container}' not found on {host}. "
            f"Use docker://{host}/list to see available containers."
        )

    if not logs.strip():
        return f"# Container: {container}@{host}\n\n(no logs available)"

    header = f"# Container Logs: {container}@{host}\n\n"
    return header + logs


async def docker_list_resource(host: str) -> str:
    """List Docker containers on remote host.

    Args:
        host: SSH host name from ~/.ssh/config

    Returns:
        Formatted list of containers with status.
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

    # List containers
    containers = await docker_ps(conn)

    if not containers:
        return f"# Docker Containers on {host}\n\nNo containers found (or Docker not available)."

    lines = [
        f"# Docker Containers on {host}",
        "=" * 50,
        "",
    ]

    for c in containers:
        status_icon = "●" if "Up" in c["status"] else "○"
        lines.append(f"{status_icon} {c['name']}")
        lines.append(f"    Status: {c['status']}")
        lines.append(f"    Image:  {c['image']}")
        lines.append(f"    Logs:   {host}://docker/{c['name']}/logs")
        lines.append("")

    return "\n".join(lines)
```

**Verify:** File exists and imports cleanly: `uv run python -c "from scout_mcp.resources.docker import docker_logs_resource, docker_list_resource"`

---

## Task 3: Export Docker Resources from Package

**File:** `scout_mcp/resources/__init__.py`

**What:** Add exports for the new Docker resources.

**Replace entire file with:**

```python
"""MCP resources for Scout MCP."""

from scout_mcp.resources.docker import docker_list_resource, docker_logs_resource
from scout_mcp.resources.hosts import list_hosts_resource
from scout_mcp.resources.scout import scout_resource

__all__ = [
    "docker_list_resource",
    "docker_logs_resource",
    "list_hosts_resource",
    "scout_resource",
]
```

**Verify:** `uv run python -c "from scout_mcp.resources import docker_logs_resource, docker_list_resource"`

---

## Task 4: Register Docker Resources in Server Lifespan

**File:** `scout_mcp/server.py`

**What:** Register dynamic Docker resources for each host during lifespan.

**Step 4a:** Update imports at line 19.

Replace:
```python
from scout_mcp.resources import list_hosts_resource, scout_resource
```

With:
```python
from scout_mcp.resources import (
    docker_list_resource,
    docker_logs_resource,
    list_hosts_resource,
    scout_resource,
)
```

**Step 4b:** Add helper function after `_read_host_path` (after line 34).

```python
async def _read_docker_logs(host: str, container: str) -> str:
    """Read Docker container logs on a remote host.

    Args:
        host: SSH host name
        container: Docker container name

    Returns:
        Container logs
    """
    return await docker_logs_resource(host, container)


async def _list_docker_containers(host: str) -> str:
    """List Docker containers on a remote host.

    Args:
        host: SSH host name

    Returns:
        Formatted container list
    """
    return await docker_list_resource(host)
```

**Step 4c:** Update `app_lifespan` to register Docker resources. Add after the filesystem resource registration loop (after line 67, before `yield`).

```python
    # Register Docker resources for each host
    for host_name in hosts:

        def make_docker_logs_handler(h: str) -> Any:
            async def handler(container: str) -> str:
                return await _read_docker_logs(h, container)

            return handler

        def make_docker_list_handler(h: str) -> Any:
            async def handler() -> str:
                return await _list_docker_containers(h)

            return handler

        # Docker logs: tootie://docker/plex/logs
        server.resource(
            uri=f"{host_name}://docker/{{container}}/logs",
            name=f"{host_name} docker logs",
            description=f"Read Docker container logs on {host_name}",
            mime_type="text/plain",
        )(make_docker_logs_handler(host_name))

        # Docker list: tootie://docker/list
        server.resource(
            uri=f"{host_name}://docker/list",
            name=f"{host_name} docker containers",
            description=f"List Docker containers on {host_name}",
            mime_type="text/plain",
        )(make_docker_list_handler(host_name))
```

**Verify:** `uv run python -c "from scout_mcp.server import create_server; mcp = create_server(); print('OK')"`

---

## Task 5: Update hosts://list to Show Docker Resources

**File:** `scout_mcp/resources/hosts.py`

**What:** Add Docker resource URIs to the hosts listing output.

**Update lines 33-37** to add Docker URI:

Replace:
```python
        lines.append(f"[{status_icon}] {name} ({status})")
        lines.append(f"    SSH:      {host_info}")
        lines.append(f"    Direct:   {name}://path/to/file")
        lines.append(f"    Generic:  scout://{name}/path/to/file")
        lines.append("")
```

With:
```python
        lines.append(f"[{status_icon}] {name} ({status})")
        lines.append(f"    SSH:      {host_info}")
        lines.append(f"    Files:    {name}://path/to/file")
        lines.append(f"    Docker:   {name}://docker/{{container}}/logs")
        lines.append(f"    Generic:  scout://{name}/path/to/file")
        lines.append("")
```

**Update example section (around line 42-45)** to include Docker examples:

Replace:
```python
    example_hosts = list(sorted(hosts.keys()))[:2]
    for h in example_hosts:
        lines.append(f"  {h}://etc/hosts          (host-specific)")
        lines.append(f"  scout://{h}/var/log      (generic fallback)")
```

With:
```python
    example_hosts = list(sorted(hosts.keys()))[:2]
    for h in example_hosts:
        lines.append(f"  {h}://etc/hosts             (files)")
        lines.append(f"  {h}://docker/nginx/logs     (docker logs)")
        lines.append(f"  {h}://docker/list           (list containers)")
```

**Verify:** `uv run pytest tests/test_resources/test_hosts.py -v`

---

## Task 6: Add Unit Tests for Docker Executors

**File:** `tests/test_services/test_docker_executors.py` (NEW FILE)

```python
"""Tests for Docker executor functions."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from scout_mcp.services.executors import docker_inspect, docker_logs, docker_ps


@pytest.mark.asyncio
async def test_docker_logs_returns_logs() -> None:
    """docker_logs returns container logs."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="2024-01-01T00:00:00Z Log line 1\n2024-01-01T00:00:01Z Log line 2",
            returncode=0,
        )
    )

    logs, exists = await docker_logs(mock_conn, "plex")

    assert exists is True
    assert "Log line 1" in logs
    assert "Log line 2" in logs
    mock_conn.run.assert_called_once()


@pytest.mark.asyncio
async def test_docker_logs_container_not_found() -> None:
    """docker_logs returns exists=False for missing container."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="Error: No such container: missing",
            returncode=1,
        )
    )

    logs, exists = await docker_logs(mock_conn, "missing")

    assert exists is False
    assert logs == ""


@pytest.mark.asyncio
async def test_docker_logs_docker_error_raises() -> None:
    """docker_logs raises RuntimeError on Docker daemon errors."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="Cannot connect to Docker daemon",
            returncode=1,
        )
    )

    with pytest.raises(RuntimeError, match="Docker error"):
        await docker_logs(mock_conn, "plex")


@pytest.mark.asyncio
async def test_docker_ps_returns_containers() -> None:
    """docker_ps returns list of containers."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="plex\tUp 2 days\tplexinc/pms-docker\nnginx\tExited (0)\tnginx:latest",
            returncode=0,
        )
    )

    containers = await docker_ps(mock_conn)

    assert len(containers) == 2
    assert containers[0]["name"] == "plex"
    assert "Up" in containers[0]["status"]
    assert containers[1]["name"] == "nginx"


@pytest.mark.asyncio
async def test_docker_ps_returns_empty_when_docker_unavailable() -> None:
    """docker_ps returns empty list when Docker not available."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="docker: command not found",
            returncode=127,
        )
    )

    containers = await docker_ps(mock_conn)

    assert containers == []


@pytest.mark.asyncio
async def test_docker_inspect_returns_true_when_exists() -> None:
    """docker_inspect returns True for existing container."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(returncode=0)
    )

    exists = await docker_inspect(mock_conn, "plex")

    assert exists is True


@pytest.mark.asyncio
async def test_docker_inspect_returns_false_when_missing() -> None:
    """docker_inspect returns False for missing container."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(returncode=1)
    )

    exists = await docker_inspect(mock_conn, "missing")

    assert exists is False
```

**Verify:** `uv run pytest tests/test_services/test_docker_executors.py -v`

---

## Task 7: Add Unit Tests for Docker Resources

**File:** `tests/test_resources/test_docker.py` (NEW FILE)

```python
"""Tests for Docker resource handlers."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp.exceptions import ResourceError

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
async def test_docker_logs_resource_returns_logs(mock_ssh_config: Path) -> None:
    """docker_logs_resource returns formatted container logs."""
    from scout_mcp.resources.docker import docker_logs_resource

    config = Config(ssh_config_path=mock_ssh_config)

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()

    with patch(
        "scout_mcp.resources.docker.get_config", return_value=config
    ), patch(
        "scout_mcp.resources.docker.get_pool", return_value=mock_pool
    ), patch(
        "scout_mcp.resources.docker.docker_logs",
        return_value=("2024-01-01T00:00:00Z Test log line", True),
    ):

        result = await docker_logs_resource("tootie", "plex")

        assert "Container Logs: plex@tootie" in result
        assert "Test log line" in result


@pytest.mark.asyncio
async def test_docker_logs_resource_unknown_host(mock_ssh_config: Path) -> None:
    """docker_logs_resource raises ResourceError for unknown host."""
    from scout_mcp.resources.docker import docker_logs_resource

    config = Config(ssh_config_path=mock_ssh_config)

    with patch(
        "scout_mcp.resources.docker.get_config", return_value=config
    ), pytest.raises(ResourceError, match="Unknown host 'unknown'"):
        await docker_logs_resource("unknown", "plex")


@pytest.mark.asyncio
async def test_docker_logs_resource_container_not_found(mock_ssh_config: Path) -> None:
    """docker_logs_resource raises ResourceError for missing container."""
    from scout_mcp.resources.docker import docker_logs_resource

    config = Config(ssh_config_path=mock_ssh_config)

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()

    with patch(
        "scout_mcp.resources.docker.get_config", return_value=config
    ), patch(
        "scout_mcp.resources.docker.get_pool", return_value=mock_pool
    ), patch(
        "scout_mcp.resources.docker.docker_logs",
        return_value=("", False),
    ), pytest.raises(ResourceError, match="not found"):
        await docker_logs_resource("tootie", "missing")


@pytest.mark.asyncio
async def test_docker_list_resource_returns_containers(mock_ssh_config: Path) -> None:
    """docker_list_resource returns formatted container list."""
    from scout_mcp.resources.docker import docker_list_resource

    config = Config(ssh_config_path=mock_ssh_config)

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()

    containers = [
        {"name": "plex", "status": "Up 2 days", "image": "plexinc/pms-docker"},
        {"name": "nginx", "status": "Exited (0)", "image": "nginx:latest"},
    ]

    with patch(
        "scout_mcp.resources.docker.get_config", return_value=config
    ), patch(
        "scout_mcp.resources.docker.get_pool", return_value=mock_pool
    ), patch(
        "scout_mcp.resources.docker.docker_ps",
        return_value=containers,
    ):

        result = await docker_list_resource("tootie")

        assert "Docker Containers on tootie" in result
        assert "plex" in result
        assert "nginx" in result
        assert "tootie://docker/plex/logs" in result
```

**Verify:** `uv run pytest tests/test_resources/test_docker.py -v`

---

## Task 8: Add Integration Test for Docker Resource Registration

**File:** `tests/test_server_lifespan.py`

**What:** Add test verifying Docker resources are registered in lifespan.

**Add after line 207 (at end of file):**

```python
@pytest.mark.asyncio
async def test_lifespan_registers_docker_templates(mock_ssh_config: Path) -> None:
    """Lifespan registers Docker resource templates for each host."""
    from scout_mcp.server import app_lifespan, create_server

    config = Config(ssh_config_path=mock_ssh_config)

    with patch("scout_mcp.server.get_config", return_value=config):
        mcp = create_server()

        async with app_lifespan(mcp) as result:
            templates = [
                t.uri_template
                for t in mcp._resource_manager._templates.values()
            ]

            # Should have docker logs templates
            assert any("tootie://docker/" in t and "/logs" in t for t in templates), (
                f"Expected tootie://docker/*/logs template in {templates}"
            )
            assert any("squirts://docker/" in t and "/logs" in t for t in templates), (
                f"Expected squirts://docker/*/logs template in {templates}"
            )

            # Should have docker list templates
            assert any("tootie://docker/list" in t for t in templates), (
                f"Expected tootie://docker/list template in {templates}"
            )

            # Should still have filesystem templates
            assert any("tootie://" in t and "docker" not in t for t in templates), (
                f"Expected tootie://path template in {templates}"
            )
```

**Verify:** `uv run pytest tests/test_server_lifespan.py -v`

---

## Task 9: Run Full Test Suite

**What:** Verify all tests pass.

```bash
uv run pytest tests/ -v
```

**Expected:** All tests pass, including:
- `tests/test_services/test_docker_executors.py` (6 tests)
- `tests/test_resources/test_docker.py` (4 tests)
- `tests/test_server_lifespan.py::test_lifespan_registers_docker_templates`
- All existing tests still pass

---

## Task 10: Manual Verification

**What:** Test the feature end-to-end.

```bash
# Start the server
uv run python -m scout_mcp &

# In another terminal, use mcp-client or fastmcp to test:
# 1. List containers on a host
# Resource URI: tootie://docker/list

# 2. Read container logs
# Resource URI: tootie://docker/plex/logs

# 3. Verify hosts://list shows Docker URIs
# Resource URI: hosts://list
```

**Expected:** All resources return appropriate content.

---

## Summary

| Task | File | Action |
|------|------|--------|
| 1 | `services/executors.py` | Add `docker_logs`, `docker_ps`, `docker_inspect` |
| 2 | `resources/docker.py` | Create `docker_logs_resource`, `docker_list_resource` |
| 3 | `resources/__init__.py` | Export new resources |
| 4 | `server.py` | Register Docker resources in lifespan |
| 5 | `resources/hosts.py` | Update hosts list to show Docker URIs |
| 6 | `tests/.../test_docker_executors.py` | Add executor tests |
| 7 | `tests/.../test_docker.py` | Add resource tests |
| 8 | `tests/test_server_lifespan.py` | Add Docker registration test |
| 9 | - | Run full test suite |
| 10 | - | Manual verification |

**New URIs Available After Implementation:**
- `{host}://docker/{container}/logs` - Container logs
- `{host}://docker/list` - List containers on host

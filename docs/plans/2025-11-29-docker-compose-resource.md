# Docker Compose Resource Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Add Docker Compose resources to scout_mcp, enabling URIs to list projects, view compose files, and read stack logs.

**URI Patterns:**
- `{host}://compose` → List all Docker Compose projects
- `{host}://compose/{project}` → Show docker-compose.yaml contents
- `{host}://compose/{project}/logs` → Show stack logs

**Examples:**
- `tootie://compose` → Lists plex, immich, portainer, etc.
- `tootie://compose/plex` → Shows plex docker-compose.yaml
- `tootie://compose/plex/logs` → Shows logs for plex stack

---

## Task 1: Add Docker Compose Executor Functions

**File:** `scout_mcp/services/executors.py`

**What:** Add three new executor functions for Docker Compose operations.

**Add after the `docker_inspect` function (after line 284):**

```python
async def compose_ls(
    conn: "asyncssh.SSHClientConnection",
) -> list[dict[str, str]]:
    """List Docker Compose projects on remote host.

    Returns:
        List of dicts with 'name', 'status', 'config_file' keys.
        Empty list if Docker Compose not available.
    """
    cmd = "docker compose ls --format json 2>&1"

    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        return []
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")

    # Check for errors
    if result.returncode != 0:
        return []

    # Parse JSON output
    import json
    try:
        projects = json.loads(stdout)
        return [
            {
                "name": p.get("Name", ""),
                "status": p.get("Status", ""),
                "config_file": p.get("ConfigFiles", ""),
            }
            for p in projects
        ]
    except json.JSONDecodeError:
        return []


async def compose_config(
    conn: "asyncssh.SSHClientConnection",
    project: str,
) -> tuple[str, str | None]:
    """Read Docker Compose config file for a project.

    Args:
        conn: SSH connection.
        project: Compose project name.

    Returns:
        Tuple of (config_content, config_path) or ("", None) if not found.
    """
    # First get the config file path
    cmd = f"docker compose ls --format json 2>&1"
    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        return ("", None)
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")

    if result.returncode != 0:
        return ("", None)

    # Find the project
    import json
    try:
        projects = json.loads(stdout)
        config_file = None
        for p in projects:
            if p.get("Name") == project:
                config_file = p.get("ConfigFiles")
                break

        if not config_file:
            return ("", None)

        # Read the config file
        read_result = await conn.run(f"cat {config_file!r}", check=False)

        if read_result.returncode != 0:
            return ("", config_file)

        content = read_result.stdout
        if content is None:
            return ("", config_file)
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")

        return (content, config_file)

    except json.JSONDecodeError:
        return ("", None)


async def compose_logs(
    conn: "asyncssh.SSHClientConnection",
    project: str,
    tail: int = 100,
    timestamps: bool = True,
) -> tuple[str, bool]:
    """Fetch Docker Compose stack logs.

    Args:
        conn: SSH connection.
        project: Compose project name.
        tail: Number of lines from end (default: 100).
        timestamps: Include timestamps (default: True).

    Returns:
        Tuple of (logs content, project_exists boolean).
    """
    ts_flag = "--timestamps" if timestamps else ""
    cmd = f"docker compose -p {project!r} logs --tail {tail} {ts_flag} 2>&1"

    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        stdout = ""
    elif isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")

    # Check for project not found
    if result.returncode != 0:
        if "no configuration file provided" in stdout.lower():
            return ("", False)
        # Other error - still return output
        return (stdout, True)

    return (stdout, True)
```

**Verify:** `uv run python -c "from scout_mcp.services.executors import compose_ls, compose_config, compose_logs; print('OK')"`

---

## Task 2: Create Compose Resource Module

**File:** `scout_mcp/resources/compose.py` (NEW FILE)

**What:** Create the Docker Compose resource handlers.

```python
"""Docker Compose resource for reading compose configs and logs from remote hosts."""

from fastmcp.exceptions import ResourceError

from scout_mcp.services import get_config, get_pool
from scout_mcp.services.executors import compose_config, compose_logs, compose_ls


async def compose_list_resource(host: str) -> str:
    """List Docker Compose projects on remote host.

    Args:
        host: SSH host name from ~/.ssh/config

    Returns:
        Formatted list of compose projects.
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

    # List projects
    projects = await compose_ls(conn)

    if not projects:
        return f"# Docker Compose Projects on {host}\n\nNo projects found (or Docker Compose not available)."

    lines = [
        f"# Docker Compose Projects on {host}",
        "=" * 50,
        "",
    ]

    for p in projects:
        status_icon = "●" if "running" in p["status"].lower() else "○"
        lines.append(f"{status_icon} {p['name']}")
        lines.append(f"    Status: {p['status']}")
        lines.append(f"    Config: {p['config_file']}")
        lines.append(f"    View:   {host}://compose/{p['name']}")
        lines.append(f"    Logs:   {host}://compose/{p['name']}/logs")
        lines.append("")

    return "\n".join(lines)


async def compose_file_resource(host: str, project: str) -> str:
    """Read Docker Compose config file for a project.

    Args:
        host: SSH host name from ~/.ssh/config
        project: Compose project name

    Returns:
        Compose file contents.
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

    # Get config
    content, config_path = await compose_config(conn, project)

    if config_path is None:
        raise ResourceError(
            f"Compose project '{project}' not found on {host}. "
            f"Use {host}://compose to see available projects."
        )

    if not content:
        raise ResourceError(f"Cannot read compose file: {config_path}")

    header = f"# Compose: {project}@{host}\n# File: {config_path}\n\n"
    return header + content


async def compose_logs_resource(host: str, project: str) -> str:
    """Read Docker Compose stack logs.

    Args:
        host: SSH host name from ~/.ssh/config
        project: Compose project name

    Returns:
        Stack logs with timestamps.
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

    # Fetch logs
    logs, exists = await compose_logs(conn, project, tail=100, timestamps=True)

    if not exists:
        raise ResourceError(
            f"Compose project '{project}' not found on {host}. "
            f"Use {host}://compose to see available projects."
        )

    if not logs.strip():
        return f"# Compose Logs: {project}@{host}\n\n(no logs available)"

    header = f"# Compose Logs: {project}@{host}\n\n"
    return header + logs
```

**Verify:** `uv run python -c "from scout_mcp.resources.compose import compose_list_resource, compose_file_resource, compose_logs_resource; print('OK')"`

---

## Task 3: Export Compose Resources from Package

**File:** `scout_mcp/resources/__init__.py`

**What:** Add exports for the new Compose resources.

**Replace entire file with:**

```python
"""MCP resources for Scout MCP."""

from scout_mcp.resources.compose import (
    compose_file_resource,
    compose_list_resource,
    compose_logs_resource,
)
from scout_mcp.resources.docker import docker_list_resource, docker_logs_resource
from scout_mcp.resources.hosts import list_hosts_resource
from scout_mcp.resources.scout import scout_resource

__all__ = [
    "compose_file_resource",
    "compose_list_resource",
    "compose_logs_resource",
    "docker_list_resource",
    "docker_logs_resource",
    "list_hosts_resource",
    "scout_resource",
]
```

**Verify:** `uv run python -c "from scout_mcp.resources import compose_list_resource, compose_file_resource, compose_logs_resource; print('OK')"`

---

## Task 4: Register Compose Resources in Server Lifespan

**File:** `scout_mcp/server.py`

**What:** Register dynamic Compose resources for each host during lifespan.

**Step 4a:** Update imports (line 19-24).

Replace:
```python
from scout_mcp.resources import (
    docker_list_resource,
    docker_logs_resource,
    list_hosts_resource,
    scout_resource,
)
```

With:
```python
from scout_mcp.resources import (
    compose_file_resource,
    compose_list_resource,
    compose_logs_resource,
    docker_list_resource,
    docker_logs_resource,
    list_hosts_resource,
    scout_resource,
)
```

**Step 4b:** Add helper functions after `_list_docker_containers` (after line 59).

```python
async def _list_compose_projects(host: str) -> str:
    """List Docker Compose projects on a remote host."""
    return await compose_list_resource(host)


async def _read_compose_file(host: str, project: str) -> str:
    """Read Docker Compose config file."""
    return await compose_file_resource(host, project)


async def _read_compose_logs(host: str, project: str) -> str:
    """Read Docker Compose stack logs."""
    return await compose_logs_resource(host, project)
```

**Step 4c:** Add Compose resource registration in `app_lifespan`. Add after the Docker resources loop (after line 128, before `yield`).

```python
    # Register Compose resources for each host
    for host_name in hosts:

        def make_compose_list_handler(h: str) -> Any:
            async def handler() -> str:
                return await _list_compose_projects(h)

            return handler

        def make_compose_file_handler(h: str) -> Any:
            async def handler(project: str) -> str:
                return await _read_compose_file(h, project)

            return handler

        def make_compose_logs_handler(h: str) -> Any:
            async def handler(project: str) -> str:
                return await _read_compose_logs(h, project)

            return handler

        # Compose list: tootie://compose
        server.resource(
            uri=f"{host_name}://compose",
            name=f"{host_name} compose projects",
            description=f"List Docker Compose projects on {host_name}",
            mime_type="text/plain",
        )(make_compose_list_handler(host_name))

        # Compose file: tootie://compose/plex
        server.resource(
            uri=f"{host_name}://compose/{{project}}",
            name=f"{host_name} compose file",
            description=f"Read Docker Compose config on {host_name}",
            mime_type="text/yaml",
        )(make_compose_file_handler(host_name))

        # Compose logs: tootie://compose/plex/logs
        server.resource(
            uri=f"{host_name}://compose/{{project}}/logs",
            name=f"{host_name} compose logs",
            description=f"Read Docker Compose stack logs on {host_name}",
            mime_type="text/plain",
        )(make_compose_logs_handler(host_name))
```

**Verify:** `uv run python -c "from scout_mcp.server import create_server; mcp = create_server(); print('OK')"`

---

## Task 5: Update hosts://list to Show Compose Resources

**File:** `scout_mcp/resources/hosts.py`

**What:** Add Compose resource URIs to the hosts listing.

**Update lines 33-38** to add Compose URI:

Replace:
```python
        lines.append(f"[{status_icon}] {name} ({status})")
        lines.append(f"    SSH:      {host_info}")
        lines.append(f"    Files:    {name}://path/to/file")
        lines.append(f"    Docker:   {name}://docker/{{container}}/logs")
        lines.append(f"    Generic:  scout://{name}/path/to/file")
        lines.append("")
```

With:
```python
        lines.append(f"[{status_icon}] {name} ({status})")
        lines.append(f"    SSH:      {host_info}")
        lines.append(f"    Files:    {name}://path/to/file")
        lines.append(f"    Docker:   {name}://docker/{{container}}/logs")
        lines.append(f"    Compose:  {name}://compose/{{project}}/logs")
        lines.append(f"    Generic:  scout://{name}/path/to/file")
        lines.append("")
```

**Update example section (lines 43-47):**

Replace:
```python
    example_hosts = list(sorted(hosts.keys()))[:2]
    for h in example_hosts:
        lines.append(f"  {h}://etc/hosts             (files)")
        lines.append(f"  {h}://docker/nginx/logs     (docker logs)")
        lines.append(f"  {h}://docker                (list containers)")
```

With:
```python
    example_hosts = list(sorted(hosts.keys()))[:2]
    for h in example_hosts:
        lines.append(f"  {h}://etc/hosts             (files)")
        lines.append(f"  {h}://docker                (list containers)")
        lines.append(f"  {h}://docker/nginx/logs     (container logs)")
        lines.append(f"  {h}://compose               (list projects)")
        lines.append(f"  {h}://compose/plex          (compose file)")
        lines.append(f"  {h}://compose/plex/logs     (stack logs)")
```

**Verify:** `uv run pytest tests/test_resources/test_hosts.py -v`

---

## Task 6: Add Unit Tests for Compose Executors

**File:** `tests/test_services/test_compose_executors.py` (NEW FILE)

```python
"""Tests for Docker Compose executor functions."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from scout_mcp.services.executors import compose_config, compose_logs, compose_ls


@pytest.mark.asyncio
async def test_compose_ls_returns_projects() -> None:
    """compose_ls returns list of compose projects."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout='[{"Name":"plex","Status":"running(1)","ConfigFiles":"/compose/plex/docker-compose.yaml"}]',
            returncode=0,
        )
    )

    projects = await compose_ls(mock_conn)

    assert len(projects) == 1
    assert projects[0]["name"] == "plex"
    assert "running" in projects[0]["status"]
    assert "/compose/plex" in projects[0]["config_file"]


@pytest.mark.asyncio
async def test_compose_ls_returns_empty_on_error() -> None:
    """compose_ls returns empty list on Docker error."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="docker compose not found",
            returncode=127,
        )
    )

    projects = await compose_ls(mock_conn)

    assert projects == []


@pytest.mark.asyncio
async def test_compose_config_returns_content() -> None:
    """compose_config returns config file content."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        side_effect=[
            MagicMock(
                stdout='[{"Name":"plex","Status":"running(1)","ConfigFiles":"/compose/plex/docker-compose.yaml"}]',
                returncode=0,
            ),
            MagicMock(
                stdout="services:\n  plex:\n    image: plex",
                returncode=0,
            ),
        ]
    )

    content, path = await compose_config(mock_conn, "plex")

    assert "services:" in content
    assert path == "/compose/plex/docker-compose.yaml"


@pytest.mark.asyncio
async def test_compose_config_project_not_found() -> None:
    """compose_config returns empty for missing project."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout='[{"Name":"other","Status":"running(1)","ConfigFiles":"/compose/other/docker-compose.yaml"}]',
            returncode=0,
        )
    )

    content, path = await compose_config(mock_conn, "missing")

    assert content == ""
    assert path is None


@pytest.mark.asyncio
async def test_compose_logs_returns_logs() -> None:
    """compose_logs returns stack logs."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="plex  | Starting Plex Media Server",
            returncode=0,
        )
    )

    logs, exists = await compose_logs(mock_conn, "plex")

    assert exists is True
    assert "Starting Plex" in logs


@pytest.mark.asyncio
async def test_compose_logs_project_not_found() -> None:
    """compose_logs returns exists=False for missing project."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="no configuration file provided: not found",
            returncode=1,
        )
    )

    logs, exists = await compose_logs(mock_conn, "missing")

    assert exists is False
    assert logs == ""
```

**Verify:** `uv run pytest tests/test_services/test_compose_executors.py -v`

---

## Task 7: Add Unit Tests for Compose Resources

**File:** `tests/test_resources/test_compose.py` (NEW FILE)

```python
"""Tests for Docker Compose resource handlers."""

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
async def test_compose_list_resource_returns_projects(mock_ssh_config: Path) -> None:
    """compose_list_resource returns formatted project list."""
    from scout_mcp.resources.compose import compose_list_resource

    config = Config(ssh_config_path=mock_ssh_config)

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()

    projects = [
        {"name": "plex", "status": "running(1)", "config_file": "/compose/plex/docker-compose.yaml"},
        {"name": "nginx", "status": "exited(0)", "config_file": "/compose/nginx/docker-compose.yaml"},
    ]

    with patch(
        "scout_mcp.resources.compose.get_config", return_value=config
    ), patch(
        "scout_mcp.resources.compose.get_pool", return_value=mock_pool
    ), patch(
        "scout_mcp.resources.compose.compose_ls",
        return_value=projects,
    ):

        result = await compose_list_resource("tootie")

        assert "Docker Compose Projects on tootie" in result
        assert "plex" in result
        assert "nginx" in result
        assert "tootie://compose/plex" in result


@pytest.mark.asyncio
async def test_compose_file_resource_returns_config(mock_ssh_config: Path) -> None:
    """compose_file_resource returns compose file contents."""
    from scout_mcp.resources.compose import compose_file_resource

    config = Config(ssh_config_path=mock_ssh_config)

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()

    with patch(
        "scout_mcp.resources.compose.get_config", return_value=config
    ), patch(
        "scout_mcp.resources.compose.get_pool", return_value=mock_pool
    ), patch(
        "scout_mcp.resources.compose.compose_config",
        return_value=("services:\n  plex:\n    image: plex", "/compose/plex/docker-compose.yaml"),
    ):

        result = await compose_file_resource("tootie", "plex")

        assert "plex@tootie" in result
        assert "services:" in result


@pytest.mark.asyncio
async def test_compose_file_resource_project_not_found(mock_ssh_config: Path) -> None:
    """compose_file_resource raises ResourceError for missing project."""
    from scout_mcp.resources.compose import compose_file_resource

    config = Config(ssh_config_path=mock_ssh_config)

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()

    with patch(
        "scout_mcp.resources.compose.get_config", return_value=config
    ), patch(
        "scout_mcp.resources.compose.get_pool", return_value=mock_pool
    ), patch(
        "scout_mcp.resources.compose.compose_config",
        return_value=("", None),
    ), pytest.raises(ResourceError, match="not found"):
        await compose_file_resource("tootie", "missing")


@pytest.mark.asyncio
async def test_compose_logs_resource_returns_logs(mock_ssh_config: Path) -> None:
    """compose_logs_resource returns formatted logs."""
    from scout_mcp.resources.compose import compose_logs_resource

    config = Config(ssh_config_path=mock_ssh_config)

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()

    with patch(
        "scout_mcp.resources.compose.get_config", return_value=config
    ), patch(
        "scout_mcp.resources.compose.get_pool", return_value=mock_pool
    ), patch(
        "scout_mcp.resources.compose.compose_logs",
        return_value=("plex  | Starting server", True),
    ):

        result = await compose_logs_resource("tootie", "plex")

        assert "Compose Logs: plex@tootie" in result
        assert "Starting server" in result
```

**Verify:** `uv run pytest tests/test_resources/test_compose.py -v`

---

## Task 8: Add Integration Test for Compose Resource Registration

**File:** `tests/test_server_lifespan.py`

**What:** Add test verifying Compose resources are registered in lifespan.

**Add at end of file:**

```python
@pytest.mark.asyncio
async def test_lifespan_registers_compose_templates(mock_ssh_config: Path) -> None:
    """Lifespan registers Compose resource templates for each host."""
    from scout_mcp.server import app_lifespan, create_server

    config = Config(ssh_config_path=mock_ssh_config)

    with patch("scout_mcp.server.get_config", return_value=config):
        mcp = create_server()

        async with app_lifespan(mcp) as result:
            templates = [
                t.uri_template
                for t in mcp._resource_manager._templates.values()
            ]

            resources = [
                str(r.uri)
                for r in mcp._resource_manager._resources.values()
            ]

            # Should have compose file templates
            assert any("tootie://compose/" in t and "project" in t for t in templates), (
                f"Expected tootie://compose/{{project}} template in {templates}"
            )

            # Should have compose logs templates
            assert any("tootie://compose/" in t and "/logs" in t for t in templates), (
                f"Expected tootie://compose/{{project}}/logs template in {templates}"
            )

            # Should have compose list resources
            assert any("tootie://compose" in r and "project" not in r for r in resources), (
                f"Expected tootie://compose resource in {resources}"
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
- `tests/test_services/test_compose_executors.py` (6 tests)
- `tests/test_resources/test_compose.py` (4 tests)
- `tests/test_server_lifespan.py::test_lifespan_registers_compose_templates`
- All existing tests still pass

---

## Summary

| Task | File | Action |
|------|------|--------|
| 1 | `services/executors.py` | Add `compose_ls`, `compose_config`, `compose_logs` |
| 2 | `resources/compose.py` | Create `compose_list_resource`, `compose_file_resource`, `compose_logs_resource` |
| 3 | `resources/__init__.py` | Export new resources |
| 4 | `server.py` | Register Compose resources in lifespan |
| 5 | `resources/hosts.py` | Update hosts list to show Compose URIs |
| 6 | `tests/.../test_compose_executors.py` | Add executor tests |
| 7 | `tests/.../test_compose.py` | Add resource tests |
| 8 | `tests/test_server_lifespan.py` | Add Compose registration test |
| 9 | - | Run full test suite |

**New URIs Available After Implementation:**
- `{host}://compose` - List all compose projects
- `{host}://compose/{project}` - Show compose file
- `{host}://compose/{project}/logs` - Stack logs

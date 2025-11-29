# ZFS Resources Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add read-only ZFS resources to scout_mcp for viewing pool status, dataset info, and snapshots on remote hosts.

**Architecture:** Executor functions detect ZFS availability via `zpool status`. Resources return friendly "ZFS not available" message when ZFS is missing. URIs follow existing pattern: `{host}://zfs` for overview, `{host}://zfs/{pool}` for pool details, `{host}://zfs/snapshots` for snapshot list.

**Tech Stack:** asyncssh for SSH commands, FastMCP resources, existing connection pool

---

## Task 1: Add ZFS Executor Functions

**File:** `scout_mcp/services/executors.py`

**Step 1: Add zfs_check executor**

Add after `compose_logs` function (end of file):

```python
async def zfs_check(
    conn: "asyncssh.SSHClientConnection",
) -> bool:
    """Check if ZFS is available on remote host.

    Returns:
        True if ZFS is available, False otherwise.
    """
    cmd = "command -v zpool >/dev/null 2>&1 && zpool status >/dev/null 2>&1"
    result = await conn.run(cmd, check=False)
    return result.returncode == 0


async def zfs_pools(
    conn: "asyncssh.SSHClientConnection",
) -> list[dict[str, str]]:
    """List ZFS pools on remote host.

    Returns:
        List of dicts with 'name', 'size', 'alloc', 'free', 'cap', 'health' keys.
        Empty list if ZFS not available.
    """
    cmd = "zpool list -H -o name,size,alloc,free,cap,health 2>/dev/null"
    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        return []
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")

    if result.returncode != 0:
        return []

    pools = []
    for line in stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 6:
            pools.append({
                "name": parts[0],
                "size": parts[1],
                "alloc": parts[2],
                "free": parts[3],
                "cap": parts[4],
                "health": parts[5],
            })
    return pools


async def zfs_pool_status(
    conn: "asyncssh.SSHClientConnection",
    pool: str,
) -> tuple[str, bool]:
    """Get detailed status of a ZFS pool.

    Args:
        conn: SSH connection.
        pool: Pool name.

    Returns:
        Tuple of (status_output, pool_exists).
    """
    cmd = f"zpool status {pool!r} 2>&1"
    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        stdout = ""
    elif isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")

    if result.returncode != 0:
        if "no such pool" in stdout.lower():
            return ("", False)
        return (stdout, True)

    return (stdout, True)


async def zfs_datasets(
    conn: "asyncssh.SSHClientConnection",
    pool: str | None = None,
) -> list[dict[str, str]]:
    """List ZFS datasets on remote host.

    Args:
        conn: SSH connection.
        pool: Optional pool name to filter by.

    Returns:
        List of dicts with 'name', 'used', 'avail', 'refer', 'mountpoint' keys.
    """
    if pool:
        cmd = f"zfs list -H -r -o name,used,avail,refer,mountpoint {pool!r} 2>/dev/null"
    else:
        cmd = "zfs list -H -o name,used,avail,refer,mountpoint 2>/dev/null"

    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        return []
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")

    if result.returncode != 0:
        return []

    datasets = []
    for line in stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 5:
            datasets.append({
                "name": parts[0],
                "used": parts[1],
                "avail": parts[2],
                "refer": parts[3],
                "mountpoint": parts[4],
            })
    return datasets


async def zfs_snapshots(
    conn: "asyncssh.SSHClientConnection",
    dataset: str | None = None,
    limit: int = 50,
) -> list[dict[str, str]]:
    """List ZFS snapshots on remote host.

    Args:
        conn: SSH connection.
        dataset: Optional dataset name to filter by.
        limit: Maximum number of snapshots to return.

    Returns:
        List of dicts with 'name', 'used', 'creation' keys.
    """
    if dataset:
        cmd = f"zfs list -H -t snapshot -r -o name,used,creation {dataset!r} 2>/dev/null | tail -{limit}"
    else:
        cmd = f"zfs list -H -t snapshot -o name,used,creation 2>/dev/null | tail -{limit}"

    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        return []
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")

    if result.returncode != 0:
        return []

    snapshots = []
    for line in stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t", 2)
        if len(parts) >= 3:
            snapshots.append({
                "name": parts[0],
                "used": parts[1],
                "creation": parts[2],
            })
    return snapshots
```

**Step 2: Verify import works**

Run: `uv run python -c "from scout_mcp.services.executors import zfs_check, zfs_pools, zfs_pool_status, zfs_datasets, zfs_snapshots; print('OK')"`

Expected: `OK`

---

## Task 2: Create ZFS Resource Module

**File:** `scout_mcp/resources/zfs.py` (NEW)

```python
"""ZFS resource for reading pool and dataset info from remote hosts."""

from fastmcp.exceptions import ResourceError

from scout_mcp.services import get_config, get_pool
from scout_mcp.services.executors import (
    zfs_check,
    zfs_datasets,
    zfs_pool_status,
    zfs_pools,
    zfs_snapshots,
)


async def zfs_overview_resource(host: str) -> str:
    """Show ZFS overview for remote host.

    Args:
        host: SSH host name from ~/.ssh/config

    Returns:
        Formatted ZFS overview with pools and usage.
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

    # Check if ZFS is available
    has_zfs = await zfs_check(conn)
    if not has_zfs:
        return (
            f"# ZFS on {host}\n\n"
            "ZFS is not available on this host.\n\n"
            "This host either does not have ZFS installed or the zpool "
            "command is not accessible."
        )

    # Get pools
    pools_list = await zfs_pools(conn)

    if not pools_list:
        return (
            f"# ZFS on {host}\n\n"
            "ZFS is installed but no pools are configured."
        )

    lines = [
        f"# ZFS Overview: {host}",
        "=" * 50,
        "",
        "## Pools",
        "",
    ]

    for p in pools_list:
        health_icon = "●" if p["health"] == "ONLINE" else "○"
        lines.append(f"{health_icon} {p['name']} ({p['health']})")
        lines.append(f"    Size:  {p['size']}")
        lines.append(f"    Used:  {p['alloc']} ({p['cap']})")
        lines.append(f"    Free:  {p['free']}")
        lines.append(f"    View:  {host}://zfs/{p['name']}")
        lines.append("")

    lines.append("## Quick Links")
    lines.append("")
    lines.append(f"  Snapshots: {host}://zfs/snapshots")
    for p in pools_list:
        lines.append(f"  {p['name']} datasets: {host}://zfs/{p['name']}/datasets")

    return "\n".join(lines)


async def zfs_pool_resource(host: str, pool_name: str) -> str:
    """Show detailed ZFS pool status.

    Args:
        host: SSH host name from ~/.ssh/config
        pool_name: ZFS pool name

    Returns:
        Pool status output.
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

    # Check if ZFS is available
    has_zfs = await zfs_check(conn)
    if not has_zfs:
        return (
            f"# ZFS Pool: {pool_name}@{host}\n\n"
            "ZFS is not available on this host."
        )

    # Get pool status
    status, exists = await zfs_pool_status(conn, pool_name)

    if not exists:
        pools_list = await zfs_pools(conn)
        available_pools = ", ".join(p["name"] for p in pools_list) or "none"
        raise ResourceError(
            f"Pool '{pool_name}' not found on {host}. "
            f"Available pools: {available_pools}"
        )

    header = f"# ZFS Pool: {pool_name}@{host}\n\n"
    return header + status


async def zfs_datasets_resource(host: str, pool_name: str) -> str:
    """Show ZFS datasets for a pool.

    Args:
        host: SSH host name from ~/.ssh/config
        pool_name: ZFS pool name

    Returns:
        Formatted dataset list.
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

    # Check if ZFS is available
    has_zfs = await zfs_check(conn)
    if not has_zfs:
        return (
            f"# ZFS Datasets: {pool_name}@{host}\n\n"
            "ZFS is not available on this host."
        )

    # Get datasets
    datasets_list = await zfs_datasets(conn, pool_name)

    if not datasets_list:
        raise ResourceError(
            f"Pool '{pool_name}' not found or has no datasets on {host}. "
            f"Use {host}://zfs to see available pools."
        )

    lines = [
        f"# ZFS Datasets: {pool_name}@{host}",
        "=" * 50,
        "",
        f"{'NAME':<50} {'USED':>8} {'AVAIL':>8} {'REFER':>8} MOUNTPOINT",
        "-" * 90,
    ]

    for d in datasets_list:
        name = d["name"]
        if len(name) > 48:
            name = "..." + name[-45:]
        lines.append(
            f"{name:<50} {d['used']:>8} {d['avail']:>8} {d['refer']:>8} {d['mountpoint']}"
        )

    return "\n".join(lines)


async def zfs_snapshots_resource(host: str) -> str:
    """Show ZFS snapshots on host.

    Args:
        host: SSH host name from ~/.ssh/config

    Returns:
        Formatted snapshot list.
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

    # Check if ZFS is available
    has_zfs = await zfs_check(conn)
    if not has_zfs:
        return (
            f"# ZFS Snapshots: {host}\n\n"
            "ZFS is not available on this host."
        )

    # Get snapshots
    snapshots_list = await zfs_snapshots(conn, limit=50)

    if not snapshots_list:
        return (
            f"# ZFS Snapshots: {host}\n\n"
            "No snapshots found."
        )

    lines = [
        f"# ZFS Snapshots: {host}",
        "=" * 50,
        f"(showing last 50 snapshots)",
        "",
    ]

    for s in snapshots_list:
        lines.append(f"  {s['name']}")
        lines.append(f"      Used: {s['used']:<10} Created: {s['creation']}")
        lines.append("")

    return "\n".join(lines)
```

**Step 2: Verify import works**

Run: `uv run python -c "from scout_mcp.resources.zfs import zfs_overview_resource, zfs_pool_resource, zfs_datasets_resource, zfs_snapshots_resource; print('OK')"`

Expected: `OK`

---

## Task 3: Update Resource Exports

**File:** `scout_mcp/resources/__init__.py`

Replace entire file with:

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
from scout_mcp.resources.zfs import (
    zfs_datasets_resource,
    zfs_overview_resource,
    zfs_pool_resource,
    zfs_snapshots_resource,
)

__all__ = [
    "compose_file_resource",
    "compose_list_resource",
    "compose_logs_resource",
    "docker_list_resource",
    "docker_logs_resource",
    "list_hosts_resource",
    "scout_resource",
    "zfs_datasets_resource",
    "zfs_overview_resource",
    "zfs_pool_resource",
    "zfs_snapshots_resource",
]
```

**Verify:**

Run: `uv run python -c "from scout_mcp.resources import zfs_overview_resource, zfs_pool_resource, zfs_datasets_resource, zfs_snapshots_resource; print('OK')"`

Expected: `OK`

---

## Task 4: Register ZFS Resources in Server Lifespan

**File:** `scout_mcp/server.py`

**Step 1: Update imports (around line 19)**

Replace:
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
    zfs_datasets_resource,
    zfs_overview_resource,
    zfs_pool_resource,
    zfs_snapshots_resource,
)
```

**Step 2: Add helper functions (after `_read_compose_logs`, around line 82)**

```python
async def _zfs_overview(host: str) -> str:
    """Get ZFS overview for a remote host."""
    return await zfs_overview_resource(host)


async def _zfs_pool(host: str, pool: str) -> str:
    """Get ZFS pool status."""
    return await zfs_pool_resource(host, pool)


async def _zfs_datasets(host: str, pool: str) -> str:
    """Get ZFS datasets for a pool."""
    return await zfs_datasets_resource(host, pool)


async def _zfs_snapshots(host: str) -> str:
    """Get ZFS snapshots."""
    return await zfs_snapshots_resource(host)
```

**Step 3: Add ZFS resource registration in `app_lifespan` (after Compose loop, before filesystem wildcard)**

Add before `# Register filesystem wildcard LAST`:

```python
    # Register ZFS resources for each host
    for host_name in hosts:

        def make_zfs_overview_handler(h: str) -> Any:
            async def handler() -> str:
                return await _zfs_overview(h)

            return handler

        def make_zfs_pool_handler(h: str) -> Any:
            async def handler(pool: str) -> str:
                return await _zfs_pool(h, pool)

            return handler

        def make_zfs_datasets_handler(h: str) -> Any:
            async def handler(pool: str) -> str:
                return await _zfs_datasets(h, pool)

            return handler

        def make_zfs_snapshots_handler(h: str) -> Any:
            async def handler() -> str:
                return await _zfs_snapshots(h)

            return handler

        # ZFS overview: tootie://zfs
        server.resource(
            uri=f"{host_name}://zfs",
            name=f"{host_name} zfs overview",
            description=f"ZFS pool overview on {host_name}",
            mime_type="text/plain",
        )(make_zfs_overview_handler(host_name))

        # ZFS pool: tootie://zfs/cache
        server.resource(
            uri=f"{host_name}://zfs/{{pool}}",
            name=f"{host_name} zfs pool",
            description=f"ZFS pool status on {host_name}",
            mime_type="text/plain",
        )(make_zfs_pool_handler(host_name))

        # ZFS datasets: tootie://zfs/cache/datasets
        server.resource(
            uri=f"{host_name}://zfs/{{pool}}/datasets",
            name=f"{host_name} zfs datasets",
            description=f"ZFS datasets on {host_name}",
            mime_type="text/plain",
        )(make_zfs_datasets_handler(host_name))

        # ZFS snapshots: tootie://zfs/snapshots
        server.resource(
            uri=f"{host_name}://zfs/snapshots",
            name=f"{host_name} zfs snapshots",
            description=f"ZFS snapshots on {host_name}",
            mime_type="text/plain",
        )(make_zfs_snapshots_handler(host_name))
```

**Verify:**

Run: `uv run python -c "from scout_mcp.server import create_server; mcp = create_server(); print('OK')"`

Expected: `OK`

---

## Task 5: Update hosts://list Resource

**File:** `scout_mcp/resources/hosts.py`

**Step 1: Add ZFS URI to host listing (around line 37)**

Replace:
```python
        lines.append(f"[{status_icon}] {name} ({status})")
        lines.append(f"    SSH:      {host_info}")
        lines.append(f"    Files:    {name}://path/to/file")
        lines.append(f"    Docker:   {name}://docker/{{container}}/logs")
        lines.append(f"    Compose:  {name}://compose/{{project}}/logs")
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
        lines.append(f"    ZFS:      {name}://zfs")
        lines.append(f"    Generic:  scout://{name}/path/to/file")
        lines.append("")
```

**Step 2: Update examples section (around line 49)**

Replace:
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
        lines.append(f"  {h}://zfs                   (zfs overview)")
        lines.append(f"  {h}://zfs/cache             (pool status)")
        lines.append(f"  {h}://zfs/snapshots         (all snapshots)")
```

---

## Task 6: Add Unit Tests for ZFS Executors

**File:** `tests/test_services/test_zfs_executors.py` (NEW)

```python
"""Tests for ZFS executor functions."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from scout_mcp.services.executors import (
    zfs_check,
    zfs_datasets,
    zfs_pool_status,
    zfs_pools,
    zfs_snapshots,
)


@pytest.mark.asyncio
async def test_zfs_check_returns_true_when_available() -> None:
    """zfs_check returns True when ZFS is available."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(returncode=0)
    )

    result = await zfs_check(mock_conn)

    assert result is True


@pytest.mark.asyncio
async def test_zfs_check_returns_false_when_unavailable() -> None:
    """zfs_check returns False when ZFS is not available."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(returncode=127)
    )

    result = await zfs_check(mock_conn)

    assert result is False


@pytest.mark.asyncio
async def test_zfs_pools_returns_pool_list() -> None:
    """zfs_pools returns list of pools."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="cache\t5.45T\t3.47T\t1.99T\t63%\tONLINE\n",
            returncode=0,
        )
    )

    pools = await zfs_pools(mock_conn)

    assert len(pools) == 1
    assert pools[0]["name"] == "cache"
    assert pools[0]["health"] == "ONLINE"
    assert pools[0]["cap"] == "63%"


@pytest.mark.asyncio
async def test_zfs_pools_returns_empty_on_error() -> None:
    """zfs_pools returns empty list when ZFS unavailable."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="command not found: zpool",
            returncode=127,
        )
    )

    pools = await zfs_pools(mock_conn)

    assert pools == []


@pytest.mark.asyncio
async def test_zfs_pool_status_returns_status() -> None:
    """zfs_pool_status returns pool status."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="  pool: cache\n state: ONLINE\n",
            returncode=0,
        )
    )

    status, exists = await zfs_pool_status(mock_conn, "cache")

    assert exists is True
    assert "pool: cache" in status
    assert "ONLINE" in status


@pytest.mark.asyncio
async def test_zfs_pool_status_not_found() -> None:
    """zfs_pool_status returns exists=False for missing pool."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="cannot open 'missing': no such pool",
            returncode=1,
        )
    )

    status, exists = await zfs_pool_status(mock_conn, "missing")

    assert exists is False
    assert status == ""


@pytest.mark.asyncio
async def test_zfs_datasets_returns_datasets() -> None:
    """zfs_datasets returns dataset list."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="cache\t2.51T\t1.21T\t47.8G\t/mnt/cache\ncache/appdata\t753G\t1.21T\t8.50G\t/mnt/cache/appdata\n",
            returncode=0,
        )
    )

    datasets = await zfs_datasets(mock_conn, "cache")

    assert len(datasets) == 2
    assert datasets[0]["name"] == "cache"
    assert datasets[1]["name"] == "cache/appdata"


@pytest.mark.asyncio
async def test_zfs_snapshots_returns_snapshots() -> None:
    """zfs_snapshots returns snapshot list."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="cache@snap1\t124G\tSun Nov 23  6:49 2025\ncache/appdata@snap2\t256K\tTue Jul 29  9:24 2025\n",
            returncode=0,
        )
    )

    snapshots = await zfs_snapshots(mock_conn)

    assert len(snapshots) == 2
    assert snapshots[0]["name"] == "cache@snap1"
    assert snapshots[0]["used"] == "124G"
```

**Verify:**

Run: `uv run pytest tests/test_services/test_zfs_executors.py -v`

Expected: All 9 tests pass

---

## Task 7: Add Unit Tests for ZFS Resources

**File:** `tests/test_resources/test_zfs.py` (NEW)

```python
"""Tests for ZFS resource handlers."""

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
async def test_zfs_overview_resource_returns_pools(mock_ssh_config: Path) -> None:
    """zfs_overview_resource returns formatted pool list."""
    from scout_mcp.resources.zfs import zfs_overview_resource

    config = Config(ssh_config_path=mock_ssh_config)

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()

    pools = [
        {"name": "cache", "size": "5.45T", "alloc": "3.47T", "free": "1.99T", "cap": "63%", "health": "ONLINE"},
    ]

    with patch(
        "scout_mcp.resources.zfs.get_config", return_value=config
    ), patch(
        "scout_mcp.resources.zfs.get_pool", return_value=mock_pool
    ), patch(
        "scout_mcp.resources.zfs.zfs_check", return_value=True
    ), patch(
        "scout_mcp.resources.zfs.zfs_pools", return_value=pools
    ):

        result = await zfs_overview_resource("tootie")

        assert "ZFS Overview: tootie" in result
        assert "cache" in result
        assert "ONLINE" in result
        assert "tootie://zfs/cache" in result


@pytest.mark.asyncio
async def test_zfs_overview_resource_no_zfs(mock_ssh_config: Path) -> None:
    """zfs_overview_resource returns message when ZFS not available."""
    from scout_mcp.resources.zfs import zfs_overview_resource

    config = Config(ssh_config_path=mock_ssh_config)

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()

    with patch(
        "scout_mcp.resources.zfs.get_config", return_value=config
    ), patch(
        "scout_mcp.resources.zfs.get_pool", return_value=mock_pool
    ), patch(
        "scout_mcp.resources.zfs.zfs_check", return_value=False
    ):

        result = await zfs_overview_resource("tootie")

        assert "ZFS is not available" in result


@pytest.mark.asyncio
async def test_zfs_pool_resource_returns_status(mock_ssh_config: Path) -> None:
    """zfs_pool_resource returns pool status."""
    from scout_mcp.resources.zfs import zfs_pool_resource

    config = Config(ssh_config_path=mock_ssh_config)

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()

    with patch(
        "scout_mcp.resources.zfs.get_config", return_value=config
    ), patch(
        "scout_mcp.resources.zfs.get_pool", return_value=mock_pool
    ), patch(
        "scout_mcp.resources.zfs.zfs_check", return_value=True
    ), patch(
        "scout_mcp.resources.zfs.zfs_pool_status",
        return_value=("  pool: cache\n state: ONLINE", True)
    ):

        result = await zfs_pool_resource("tootie", "cache")

        assert "ZFS Pool: cache@tootie" in result
        assert "ONLINE" in result


@pytest.mark.asyncio
async def test_zfs_pool_resource_not_found(mock_ssh_config: Path) -> None:
    """zfs_pool_resource raises ResourceError for missing pool."""
    from scout_mcp.resources.zfs import zfs_pool_resource

    config = Config(ssh_config_path=mock_ssh_config)

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()

    with patch(
        "scout_mcp.resources.zfs.get_config", return_value=config
    ), patch(
        "scout_mcp.resources.zfs.get_pool", return_value=mock_pool
    ), patch(
        "scout_mcp.resources.zfs.zfs_check", return_value=True
    ), patch(
        "scout_mcp.resources.zfs.zfs_pool_status", return_value=("", False)
    ), patch(
        "scout_mcp.resources.zfs.zfs_pools", return_value=[]
    ), pytest.raises(ResourceError, match="not found"):
        await zfs_pool_resource("tootie", "missing")


@pytest.mark.asyncio
async def test_zfs_snapshots_resource_returns_snapshots(mock_ssh_config: Path) -> None:
    """zfs_snapshots_resource returns snapshot list."""
    from scout_mcp.resources.zfs import zfs_snapshots_resource

    config = Config(ssh_config_path=mock_ssh_config)

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()

    snapshots = [
        {"name": "cache@snap1", "used": "124G", "creation": "Sun Nov 23  6:49 2025"},
    ]

    with patch(
        "scout_mcp.resources.zfs.get_config", return_value=config
    ), patch(
        "scout_mcp.resources.zfs.get_pool", return_value=mock_pool
    ), patch(
        "scout_mcp.resources.zfs.zfs_check", return_value=True
    ), patch(
        "scout_mcp.resources.zfs.zfs_snapshots", return_value=snapshots
    ):

        result = await zfs_snapshots_resource("tootie")

        assert "ZFS Snapshots: tootie" in result
        assert "cache@snap1" in result
        assert "124G" in result
```

**Verify:**

Run: `uv run pytest tests/test_resources/test_zfs.py -v`

Expected: All 5 tests pass

---

## Task 8: Add Integration Test for ZFS Resource Registration

**File:** `tests/test_server_lifespan.py`

Add at end of file:

```python
@pytest.mark.asyncio
async def test_lifespan_registers_zfs_templates(mock_ssh_config: Path) -> None:
    """Lifespan registers ZFS resource templates for each host."""
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

            # Should have zfs pool templates
            assert any("tootie://zfs/" in t and "pool" in t for t in templates), (
                f"Expected tootie://zfs/{{pool}} template in {templates}"
            )

            # Should have zfs datasets templates
            assert any("tootie://zfs/" in t and "/datasets" in t for t in templates), (
                f"Expected tootie://zfs/{{pool}}/datasets template in {templates}"
            )

            # Should have zfs overview resources
            assert any("tootie://zfs" in r and "pool" not in r for r in resources), (
                f"Expected tootie://zfs resource in {resources}"
            )

            # Should have zfs snapshots resources
            assert any("tootie://zfs/snapshots" in r for r in resources), (
                f"Expected tootie://zfs/snapshots resource in {resources}"
            )
```

**Verify:**

Run: `uv run pytest tests/test_server_lifespan.py -v`

Expected: All 8 tests pass

---

## Task 9: Run Full Test Suite and Lint

**Step 1: Run all tests**

Run: `uv run pytest tests/ -v`

Expected: All tests pass (~170+ tests)

**Step 2: Run linter**

Run: `uv run ruff check scout_mcp/ --fix`

Expected: All checks passed

**Step 3: Run type checker**

Run: `uv run mypy scout_mcp/`

Expected: Success: no issues found

---

## Summary

| Task | File | Action |
|------|------|--------|
| 1 | `services/executors.py` | Add `zfs_check`, `zfs_pools`, `zfs_pool_status`, `zfs_datasets`, `zfs_snapshots` |
| 2 | `resources/zfs.py` | Create resource handlers |
| 3 | `resources/__init__.py` | Export new resources |
| 4 | `server.py` | Register ZFS resources in lifespan |
| 5 | `resources/hosts.py` | Update hosts list to show ZFS URIs |
| 6 | `tests/.../test_zfs_executors.py` | Add executor tests |
| 7 | `tests/.../test_zfs.py` | Add resource tests |
| 8 | `tests/test_server_lifespan.py` | Add ZFS registration test |
| 9 | - | Run full test suite and lint |

**New URIs Available After Implementation:**
- `{host}://zfs` - ZFS overview (pools, health, usage)
- `{host}://zfs/{pool}` - Pool status (`zpool status`)
- `{host}://zfs/{pool}/datasets` - Dataset list for pool
- `{host}://zfs/snapshots` - Recent snapshots

**ZFS Detection:**
- If host doesn't have ZFS, resources return friendly message instead of error
- Detection uses `command -v zpool && zpool status` to verify availability

"""Tests for ZFS resource handlers."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp.exceptions import ResourceError

from scout_mcp.config import Config
from scout_mcp.dependencies import Dependencies


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


@pytest.fixture
def deps(mock_ssh_config: Path) -> Dependencies:
    """Create Dependencies with mock config and pool."""
    config = Config.from_ssh_config(ssh_config_path=mock_ssh_config)
    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()
    return Dependencies(config=config, pool=mock_pool)


@pytest.mark.asyncio
async def test_zfs_overview_resource_returns_pools(deps: Dependencies) -> None:
    """zfs_overview_resource returns formatted pool list."""
    from scout_mcp.resources.zfs import zfs_overview_resource

    pools = [
        {
            "name": "cache",
            "size": "5.45T",
            "alloc": "3.47T",
            "free": "1.99T",
            "cap": "63%",
            "health": "ONLINE",
        },
    ]

    with (
        patch("scout_mcp.resources.zfs.zfs_check", return_value=True),
        patch("scout_mcp.resources.zfs.zfs_pools", return_value=pools),
    ):
        result = await zfs_overview_resource("tootie", deps)

        assert "ZFS Overview: tootie" in result
        assert "cache" in result
        assert "ONLINE" in result
        assert "tootie://zfs/cache" in result


@pytest.mark.asyncio
async def test_zfs_overview_resource_no_zfs(deps: Dependencies) -> None:
    """zfs_overview_resource returns message when ZFS not available."""
    from scout_mcp.resources.zfs import zfs_overview_resource

    with patch("scout_mcp.resources.zfs.zfs_check", return_value=False):
        result = await zfs_overview_resource("tootie", deps)

        assert "ZFS is not available" in result


@pytest.mark.asyncio
async def test_zfs_pool_resource_returns_status(deps: Dependencies) -> None:
    """zfs_pool_resource returns pool status."""
    from scout_mcp.resources.zfs import zfs_pool_resource

    status_output = """  pool: cache
 state: ONLINE
config:

        NAME        STATE     READ WRITE CKSUM
        cache       ONLINE       0     0     0
          sdc       ONLINE       0     0     0
"""

    with (
        patch("scout_mcp.resources.zfs.zfs_check", return_value=True),
        patch("scout_mcp.resources.zfs.zfs_pool_status", return_value=(status_output, True)),
    ):
        result = await zfs_pool_resource("tootie", "cache", deps)

        assert "ZFS Pool: cache@tootie" in result
        assert "ONLINE" in result


@pytest.mark.asyncio
async def test_zfs_pool_resource_not_found(deps: Dependencies) -> None:
    """zfs_pool_resource raises ResourceError for unknown pool."""
    from scout_mcp.resources.zfs import zfs_pool_resource

    with (
        patch("scout_mcp.resources.zfs.zfs_check", return_value=True),
        patch("scout_mcp.resources.zfs.zfs_pool_status", return_value=("", False)),
        patch("scout_mcp.resources.zfs.zfs_pools", return_value=[{"name": "cache"}]),
        pytest.raises(ResourceError, match="not found"),
    ):
        await zfs_pool_resource("tootie", "missing", deps)


@pytest.mark.asyncio
async def test_zfs_snapshots_resource_returns_snapshots(deps: Dependencies) -> None:
    """zfs_snapshots_resource returns snapshot list."""
    from scout_mcp.resources.zfs import zfs_snapshots_resource

    snapshots = [
        {
            "name": "cache@snap1",
            "used": "124G",
            "creation": "Sun Nov 23  6:49 2025",
        },
    ]

    with (
        patch("scout_mcp.resources.zfs.zfs_check", return_value=True),
        patch("scout_mcp.resources.zfs.zfs_snapshots", return_value=snapshots),
    ):
        result = await zfs_snapshots_resource("tootie", deps)

        assert "ZFS Snapshots: tootie" in result
        assert "cache@snap1" in result

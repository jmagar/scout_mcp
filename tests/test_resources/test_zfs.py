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
        patch("scout_mcp.resources.zfs.get_config", return_value=config),
        patch("scout_mcp.services.state.get_pool", return_value=mock_pool),
        patch("scout_mcp.resources.zfs.zfs_check", return_value=True),
        patch("scout_mcp.resources.zfs.zfs_pools", return_value=pools),
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

    with (
        patch("scout_mcp.resources.zfs.get_config", return_value=config),
        patch("scout_mcp.services.state.get_pool", return_value=mock_pool),
        patch("scout_mcp.resources.zfs.zfs_check", return_value=False),
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

    with (
        patch("scout_mcp.resources.zfs.get_config", return_value=config),
        patch("scout_mcp.services.state.get_pool", return_value=mock_pool),
        patch("scout_mcp.resources.zfs.zfs_check", return_value=True),
        patch(
            "scout_mcp.resources.zfs.zfs_pool_status",
            return_value=("  pool: cache\n state: ONLINE", True),
        ),
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

    with (
        patch("scout_mcp.resources.zfs.get_config", return_value=config),
        patch("scout_mcp.services.state.get_pool", return_value=mock_pool),
        patch("scout_mcp.resources.zfs.zfs_check", return_value=True),
        patch("scout_mcp.resources.zfs.zfs_pool_status", return_value=("", False)),
        patch("scout_mcp.resources.zfs.zfs_pools", return_value=[]),
        pytest.raises(ResourceError, match="not found"),
    ):
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
        {
            "name": "cache@snap1",
            "used": "124G",
            "creation": "Sun Nov 23  6:49 2025",
        },
    ]

    with (
        patch("scout_mcp.resources.zfs.get_config", return_value=config),
        patch("scout_mcp.services.state.get_pool", return_value=mock_pool),
        patch("scout_mcp.resources.zfs.zfs_check", return_value=True),
        patch("scout_mcp.resources.zfs.zfs_snapshots", return_value=snapshots),
    ):
        result = await zfs_snapshots_resource("tootie")

        assert "ZFS Snapshots: tootie" in result
        assert "cache@snap1" in result
        assert "124G" in result

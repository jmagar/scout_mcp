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
            stdout=(
                "cache\t2.51T\t1.21T\t47.8G\t/mnt/cache\n"
                "cache/appdata\t753G\t1.21T\t8.50G\t/mnt/cache/appdata\n"
            ),
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
            stdout=(
                "cache@snap1\t124G\tSun Nov 23  6:49 2025\n"
                "cache/appdata@snap2\t256K\tTue Jul 29  9:24 2025\n"
            ),
            returncode=0,
        )
    )

    snapshots = await zfs_snapshots(mock_conn)

    assert len(snapshots) == 2
    assert snapshots[0]["name"] == "cache@snap1"
    assert snapshots[0]["used"] == "124G"

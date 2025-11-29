"""Tests for host connectivity checking."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scout_mcp.utils.ping import check_host_online, check_hosts_online


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
        mock_conn.side_effect = TimeoutError()

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
        raise TimeoutError()

    with patch("asyncio.open_connection", side_effect=mock_open_connection):
        hosts = {
            "online_host": ("192.168.1.1", 22),
            "offline_host": ("192.168.1.2", 22),
        }

        results = await check_hosts_online(hosts)

        assert results["online_host"] is True
        assert results["offline_host"] is False


@pytest.mark.asyncio
async def test_check_hosts_online_runs_concurrently() -> None:
    """Verify hosts are checked concurrently, not sequentially."""
    # Each check takes 0.1s - if sequential, 3 hosts = 0.3s+
    # If concurrent, should complete in ~0.1s
    delay_per_host = 0.1

    async def slow_check(host: str, port: int) -> tuple:
        await asyncio.sleep(delay_per_host)
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        return (MagicMock(), mock_writer)

    with patch("asyncio.open_connection", side_effect=slow_check):
        hosts = {
            "host1": ("192.168.1.1", 22),
            "host2": ("192.168.1.2", 22),
            "host3": ("192.168.1.3", 22),
        }

        start = time.perf_counter()
        results = await check_hosts_online(hosts)
        elapsed = time.perf_counter() - start

        # Should complete in ~0.1s if concurrent, not 0.3s+ if sequential
        assert elapsed < delay_per_host * 2, f"Expected concurrent execution (<0.2s), got {elapsed:.2f}s"
        assert len(results) == 3
        assert all(results.values())

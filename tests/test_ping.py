"""Tests for host connectivity checking."""

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

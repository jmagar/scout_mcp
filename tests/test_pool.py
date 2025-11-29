"""Tests for SSH connection pool."""

from unittest.mock import AsyncMock, patch

import pytest

from scout_mcp.config import SSHHost
from scout_mcp.pool import ConnectionPool


@pytest.fixture
def mock_ssh_host() -> SSHHost:
    """Create a mock SSH host."""
    return SSHHost(
        name="testhost",
        hostname="192.168.1.100",
        user="testuser",
        port=22,
    )


@pytest.mark.asyncio
async def test_get_connection_creates_new_connection(mock_ssh_host: SSHHost) -> None:
    """First request creates a new SSH connection."""
    pool = ConnectionPool(idle_timeout=60)

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        conn = await pool.get_connection(mock_ssh_host)

        assert conn == mock_conn
        mock_connect.assert_called_once_with(
            mock_ssh_host.hostname,
            port=mock_ssh_host.port,
            username=mock_ssh_host.user,
            known_hosts=None,
            client_keys=None,
        )


@pytest.mark.asyncio
async def test_get_connection_reuses_existing(mock_ssh_host: SSHHost) -> None:
    """Subsequent requests reuse existing connection."""
    pool = ConnectionPool(idle_timeout=60)

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        conn1 = await pool.get_connection(mock_ssh_host)
        conn2 = await pool.get_connection(mock_ssh_host)

        assert conn1 == conn2
        assert mock_connect.call_count == 1


@pytest.mark.asyncio
async def test_get_connection_replaces_closed(mock_ssh_host: SSHHost) -> None:
    """Closed connections are replaced with new ones."""
    pool = ConnectionPool(idle_timeout=60)

    mock_conn1 = AsyncMock()
    mock_conn1.is_closed = True

    mock_conn2 = AsyncMock()
    mock_conn2.is_closed = False

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.side_effect = [mock_conn1, mock_conn2]

        await pool.get_connection(mock_ssh_host)
        conn2 = await pool.get_connection(mock_ssh_host)

        assert conn2 == mock_conn2
        assert mock_connect.call_count == 2


@pytest.mark.asyncio
async def test_close_all_connections(mock_ssh_host: SSHHost) -> None:
    """close_all closes all pooled connections."""
    pool = ConnectionPool(idle_timeout=60)

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        await pool.get_connection(mock_ssh_host)
        await pool.close_all()

        mock_conn.close.assert_called_once()


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


@pytest.mark.asyncio
async def test_remove_connection_existing(mock_ssh_host: SSHHost) -> None:
    """remove_connection removes connection from pool."""
    pool = ConnectionPool(idle_timeout=60)

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        await pool.get_connection(mock_ssh_host)
        assert mock_ssh_host.name in pool._connections

        await pool.remove_connection(mock_ssh_host.name)
        assert mock_ssh_host.name not in pool._connections
        mock_conn.close.assert_called_once()


@pytest.mark.asyncio
async def test_remove_connection_nonexistent(mock_ssh_host: SSHHost) -> None:
    """remove_connection handles non-existent connection gracefully."""
    pool = ConnectionPool(idle_timeout=60)

    # Should not raise an error
    await pool.remove_connection("nonexistent_host")

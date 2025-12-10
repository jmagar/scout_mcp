"""Tests for SSH connection pool."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scout_mcp.models import SSHHost
from scout_mcp.services.pool import ConnectionPool


@pytest.mark.asyncio
async def test_pool_connects_to_localhost_override():
    """Pool should use 127.0.0.1:22 for localhost hosts."""
    from scout_mcp.services import ConnectionPool

    pool = ConnectionPool(idle_timeout=60, max_size=10)

    # Create host marked as localhost
    host = SSHHost(
        name="tootie",
        hostname="tootie.example.com",
        user="root",
        port=29229,
        is_localhost=True,
    )

    # This should attempt connection to 127.0.0.1:22 instead of tootie.example.com:29229
    try:
        conn = await pool.get_connection(host)
        # If we get here, connection succeeded to localhost
        assert conn.host.connection_hostname == "127.0.0.1"
        assert conn.host.connection_port == 22
        await pool.close_all()
    except Exception as e:
        # Expected if localhost SSH not available
        # But we can verify the connection attempt used correct host/port
        assert "127.0.0.1" in str(e) or "localhost" in str(e).lower()


@pytest.mark.asyncio
async def test_connection_pool_lru_eviction() -> None:
    """Pool evicts least recently used connection when full.

    This test verifies that when the connection pool reaches its maximum size,
    it evicts the least recently used (LRU) connection to make room for new ones.

    Test scenario:
    1. Create pool with capacity of 2
    2. Add two connections (host1, host2)
    3. Access host1 to make it recently used
    4. Add third connection (host3)
    5. Verify host2 (least recently used) was evicted
    6. Verify host1 and host3 remain in pool

    Note: Comprehensive LRU eviction tests exist in tests/test_pool_limits.py
    This test serves as a basic verification in the test_services directory.
    """
    # Create pool with capacity of 2
    pool = ConnectionPool(idle_timeout=60, max_size=2, known_hosts=None)

    # Create mock hosts
    def make_host(name: str) -> MagicMock:
        host = MagicMock()
        host.name = name
        host.hostname = f"{name}.local"
        host.port = 22
        host.user = "test"
        host.identity_file = None
        host.connection_hostname = f"{name}.local"
        host.connection_port = 22
        host.is_localhost = False
        return host

    host1 = make_host("host1")
    host2 = make_host("host2")
    host3 = make_host("host3")

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        # Create mock connections
        mock_conn1 = MagicMock()
        mock_conn1.is_closed = False
        mock_conn1.close = MagicMock()

        mock_conn2 = MagicMock()
        mock_conn2.is_closed = False
        mock_conn2.close = MagicMock()

        mock_conn3 = MagicMock()
        mock_conn3.is_closed = False
        mock_conn3.close = MagicMock()

        mock_connect.side_effect = [mock_conn1, mock_conn2, mock_conn3]

        # Add first two connections
        await pool.get_connection(host1)
        await pool.get_connection(host2)
        assert pool.pool_size == 2
        assert "host1" in pool.active_hosts
        assert "host2" in pool.active_hosts

        # Access host1 to make it recently used (moves to end of LRU order)
        await pool.get_connection(host1)
        assert pool.pool_size == 2

        # Add third connection, should evict host2 (least recently used)
        await pool.get_connection(host3)

        # Verify pool size is still 2 (max_size enforced)
        assert pool.pool_size == 2

        # Verify host2 was closed and evicted (LRU victim)
        mock_conn2.close.assert_called_once()

        # Verify pool contains host1 and host3, not host2
        assert "host1" in pool.active_hosts
        assert "host3" in pool.active_hosts
        assert "host2" not in pool.active_hosts

    # Cleanup
    await pool.close_all()

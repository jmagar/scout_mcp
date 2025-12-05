"""Tests for connection pool size limits."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scout_mcp.services.pool import ConnectionPool


@pytest.fixture(autouse=True)
def mock_known_hosts(monkeypatch):
    """Disable host key verification for all tests."""
    monkeypatch.setenv("SCOUT_KNOWN_HOSTS", "none")


class TestPoolSizeLimits:
    """Test pool size limiting and LRU eviction."""

    @pytest.fixture
    def small_pool(self) -> ConnectionPool:
        """Create a small pool for testing eviction."""
        return ConnectionPool(idle_timeout=60, max_size=2, known_hosts=None)

    def make_host(self, name: str) -> MagicMock:
        """Create a mock SSH host."""
        host = MagicMock()
        host.name = name
        host.hostname = f"{name}.local"
        host.port = 22
        host.user = "test"
        host.identity_file = None
        return host

    @pytest.mark.asyncio
    async def test_evicts_lru_when_full(self, small_pool: ConnectionPool) -> None:
        """Pool evicts LRU connection when at capacity."""
        hosts = [self.make_host(f"host{i}") for i in range(3)]

        with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
            mock_conn = MagicMock()
            mock_conn.is_closed = False
            mock_connect.return_value = mock_conn

            # Fill pool
            await small_pool.get_connection(hosts[0])
            await small_pool.get_connection(hosts[1])
            assert small_pool.pool_size == 2

            # Third should evict first (LRU)
            await small_pool.get_connection(hosts[2])
            assert small_pool.pool_size == 2
            assert "host0" not in small_pool.active_hosts
            assert "host1" in small_pool.active_hosts
            assert "host2" in small_pool.active_hosts

    @pytest.mark.asyncio
    async def test_reuse_updates_lru_order(self, small_pool: ConnectionPool) -> None:
        """Reusing connection updates LRU order."""
        hosts = [self.make_host(f"host{i}") for i in range(3)]

        with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
            mock_conn = MagicMock()
            mock_conn.is_closed = False
            mock_connect.return_value = mock_conn

            # Fill pool
            await small_pool.get_connection(hosts[0])
            await small_pool.get_connection(hosts[1])

            # Reuse host0 (moves to end)
            await small_pool.get_connection(hosts[0])

            # Third should evict host1 (now LRU)
            await small_pool.get_connection(hosts[2])
            assert "host0" in small_pool.active_hosts
            assert "host1" not in small_pool.active_hosts
            assert "host2" in small_pool.active_hosts

    @pytest.mark.asyncio
    async def test_pool_never_exceeds_max_size(
        self, small_pool: ConnectionPool
    ) -> None:
        """Pool size never exceeds max_size."""
        hosts = [self.make_host(f"host{i}") for i in range(10)]

        with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
            mock_conn = MagicMock()
            mock_conn.is_closed = False
            mock_connect.return_value = mock_conn

            for host in hosts:
                await small_pool.get_connection(host)

            # Should never exceed max_size=2
            assert small_pool.pool_size == 2

    @pytest.mark.asyncio
    async def test_eviction_closes_connection(self, small_pool: ConnectionPool) -> None:
        """Evicted connections are properly closed."""
        hosts = [self.make_host(f"host{i}") for i in range(3)]

        with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
            mock_conns = [MagicMock(is_closed=False) for _ in range(3)]
            mock_connect.side_effect = mock_conns

            # Fill pool
            await small_pool.get_connection(hosts[0])
            await small_pool.get_connection(hosts[1])

            # Third connection should evict first
            await small_pool.get_connection(hosts[2])

            # Verify first connection was closed
            mock_conns[0].close.assert_called_once()

    @pytest.mark.asyncio
    async def test_max_size_with_default_value(self) -> None:
        """Pool respects default max_size."""
        pool = ConnectionPool(idle_timeout=60, known_hosts=None)
        assert pool.max_size == 100

    @pytest.mark.asyncio
    async def test_max_size_with_custom_value(self) -> None:
        """Pool respects custom max_size."""
        pool = ConnectionPool(idle_timeout=60, max_size=50, known_hosts=None)
        assert pool.max_size == 50

    @pytest.mark.asyncio
    async def test_lru_order_maintained_across_multiple_reuses(
        self, small_pool: ConnectionPool
    ) -> None:
        """LRU order correctly maintained with complex access patterns."""
        hosts = [self.make_host(f"host{i}") for i in range(3)]

        with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
            mock_conn = MagicMock()
            mock_conn.is_closed = False
            mock_connect.return_value = mock_conn

            # Fill pool: host0, host1
            await small_pool.get_connection(hosts[0])
            await small_pool.get_connection(hosts[1])

            # Reuse host0 (order: host1, host0)
            await small_pool.get_connection(hosts[0])

            # Reuse host1 (order: host0, host1)
            await small_pool.get_connection(hosts[1])

            # Add host2, should evict host0 (LRU)
            await small_pool.get_connection(hosts[2])

            assert "host0" not in small_pool.active_hosts
            assert "host1" in small_pool.active_hosts
            assert "host2" in small_pool.active_hosts

    @pytest.mark.asyncio
    async def test_eviction_with_stale_connection(
        self, small_pool: ConnectionPool
    ) -> None:
        """Eviction works when replacing stale connection."""
        hosts = [self.make_host(f"host{i}") for i in range(3)]

        with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
            # Need 4 connections: host0, host1, host0 (replacement), host2
            mock_conns = [MagicMock(is_closed=False) for _ in range(4)]
            mock_connect.side_effect = mock_conns

            # Fill pool
            await small_pool.get_connection(hosts[0])
            await small_pool.get_connection(hosts[1])

            # Mark first connection as stale
            mock_conns[0].is_closed = True

            # Try to reuse stale connection, then add new
            await small_pool.get_connection(hosts[0])
            await small_pool.get_connection(hosts[2])

            # Should have evicted the LRU (host1)
            assert "host0" in small_pool.active_hosts
            assert "host1" not in small_pool.active_hosts
            assert "host2" in small_pool.active_hosts

    def test_max_size_zero_raises_error(self) -> None:
        """Pool rejects max_size=0."""
        with pytest.raises(ValueError, match="max_size must be > 0"):
            ConnectionPool(idle_timeout=60, max_size=0, known_hosts=None)

    def test_max_size_negative_raises_error(self) -> None:
        """Pool rejects negative max_size."""
        with pytest.raises(ValueError, match="max_size must be > 0"):
            ConnectionPool(idle_timeout=60, max_size=-1, known_hosts=None)

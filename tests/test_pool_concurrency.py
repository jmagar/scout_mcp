"""Concurrency tests for connection pool."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scout_mcp.models import SSHHost
from scout_mcp.services.pool import ConnectionPool


@pytest.fixture(autouse=True)
def mock_known_hosts(monkeypatch):
    """Disable host key verification for all tests."""
    monkeypatch.setenv("SCOUT_KNOWN_HOSTS", "none")


class TestPoolConcurrency:
    """Test concurrent access to connection pool."""

    @pytest.fixture
    def mock_asyncssh(self):
        """Mock asyncssh with simulated connection delay."""
        with patch("scout_mcp.services.pool.asyncssh") as mock:
            # Simulate connection delay
            async def slow_connect(*args, **kwargs):
                await asyncio.sleep(0.1)
                conn = MagicMock()
                conn.is_closed = False
                return conn

            mock.connect = slow_connect
            yield mock

    @pytest.fixture
    def pool(self, monkeypatch):
        """Create a connection pool for testing."""
        monkeypatch.setenv("SCOUT_KNOWN_HOSTS", "none")
        return ConnectionPool(idle_timeout=60, known_hosts=None)

    @pytest.mark.asyncio
    async def test_concurrent_different_hosts(self, mock_asyncssh, pool):
        """Concurrent connections to different hosts should not block."""
        host1 = SSHHost(name="host1", hostname="h1", user="u", port=22)
        host2 = SSHHost(name="host2", hostname="h2", user="u", port=22)

        # Both should complete in ~0.1s, not ~0.2s
        start = asyncio.get_event_loop().time()
        await asyncio.gather(
            pool.get_connection(host1),
            pool.get_connection(host2),
        )
        elapsed = asyncio.get_event_loop().time() - start

        # Should be close to 0.1s (parallel), not 0.2s (serial)
        assert elapsed < 0.15, f"Expected parallel execution (~0.1s), got {elapsed:.3f}s"
        assert pool.pool_size == 2

    @pytest.mark.asyncio
    async def test_concurrent_same_host_serializes(self, mock_asyncssh, pool):
        """Concurrent connections to same host should serialize."""
        host = SSHHost(name="host1", hostname="h1", user="u", port=22)

        # First creates, second reuses (but must wait for first)
        results = await asyncio.gather(
            pool.get_connection(host),
            pool.get_connection(host),
        )

        # Should only create one connection
        assert pool.pool_size == 1
        # Both should get the same connection
        assert results[0] == results[1]

    @pytest.mark.asyncio
    async def test_concurrent_three_hosts(self, mock_asyncssh, pool):
        """Concurrent connections to three different hosts should all run in parallel."""
        host1 = SSHHost(name="host1", hostname="h1", user="u", port=22)
        host2 = SSHHost(name="host2", hostname="h2", user="u", port=22)
        host3 = SSHHost(name="host3", hostname="h3", user="u", port=22)

        # All three should complete in ~0.1s, not ~0.3s
        start = asyncio.get_event_loop().time()
        await asyncio.gather(
            pool.get_connection(host1),
            pool.get_connection(host2),
            pool.get_connection(host3),
        )
        elapsed = asyncio.get_event_loop().time() - start

        # Should be close to 0.1s (parallel), not 0.3s (serial)
        assert elapsed < 0.15, f"Expected parallel execution (~0.1s), got {elapsed:.3f}s"
        assert pool.pool_size == 3

    @pytest.mark.asyncio
    async def test_mixed_concurrent_hosts(self, mock_asyncssh, pool):
        """Mixed pattern: some same host, some different hosts."""
        host1 = SSHHost(name="host1", hostname="h1", user="u", port=22)
        host2 = SSHHost(name="host2", hostname="h2", user="u", port=22)

        # Two to host1, one to host2 - should complete in ~0.1s
        start = asyncio.get_event_loop().time()
        results = await asyncio.gather(
            pool.get_connection(host1),
            pool.get_connection(host1),
            pool.get_connection(host2),
        )
        elapsed = asyncio.get_event_loop().time() - start

        # Should be close to 0.1s (parallel for different hosts)
        assert elapsed < 0.15, f"Expected parallel execution (~0.1s), got {elapsed:.3f}s"
        assert pool.pool_size == 2
        # Two requests to host1 should get same connection
        assert results[0] == results[1]
        # host2 should be different
        assert results[2] != results[0]

    @pytest.mark.asyncio
    async def test_sequential_then_concurrent(self, mock_asyncssh, pool):
        """Sequential connection followed by concurrent reuse."""
        host1 = SSHHost(name="host1", hostname="h1", user="u", port=22)
        host2 = SSHHost(name="host2", hostname="h2", user="u", port=22)

        # First, create connection to host1
        conn1 = await pool.get_connection(host1)
        assert pool.pool_size == 1

        # Now do concurrent access to both hosts
        start = asyncio.get_event_loop().time()
        results = await asyncio.gather(
            pool.get_connection(host1),  # Reuse existing
            pool.get_connection(host2),  # Create new
        )
        elapsed = asyncio.get_event_loop().time() - start

        # Reuse should be instant, new connection takes ~0.1s
        # But they should run in parallel, so total ~0.1s not ~0.2s
        assert elapsed < 0.15, f"Expected parallel execution (~0.1s), got {elapsed:.3f}s"
        assert pool.pool_size == 2
        assert results[0] == conn1  # Reused connection

    @pytest.mark.asyncio
    async def test_cleanup_with_concurrent_access(self, mock_asyncssh, pool):
        """Cleanup should not interfere with concurrent connection access."""
        host1 = SSHHost(name="host1", hostname="h1", user="u", port=22)
        host2 = SSHHost(name="host2", hostname="h2", user="u", port=22)

        # Create connections
        await pool.get_connection(host1)
        await pool.get_connection(host2)

        # Run cleanup concurrently with new connection requests
        await asyncio.gather(
            pool._cleanup_idle(),  # Should not block
            pool.get_connection(host1),  # Reuse
            pool.get_connection(host2),  # Reuse
        )

        assert pool.pool_size == 2

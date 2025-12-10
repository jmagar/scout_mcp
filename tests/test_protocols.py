"""Tests for protocol interfaces.

Verifies that concrete implementations satisfy protocol contracts.
"""


import pytest


def test_connection_pool_implements_protocol():
    """Verify ConnectionPool implements SSHConnectionPool protocol."""
    from scout_mcp.protocols import SSHConnectionPool
    from scout_mcp.services.pool import ConnectionPool

    # Should not raise if ConnectionPool implements protocol
    pool = ConnectionPool()
    assert isinstance(pool, SSHConnectionPool)


def test_protocol_runtime_checkable():
    """Verify protocols are decorated with @runtime_checkable."""
    from typing import Protocol

    from scout_mcp.protocols import SSHConnectionPool

    # Verify it's a Protocol
    assert issubclass(SSHConnectionPool, Protocol)


def test_connection_pool_has_required_methods():
    """Verify ConnectionPool has all required protocol methods."""
    from scout_mcp.services.pool import ConnectionPool

    pool = ConnectionPool()

    # Check methods exist
    assert hasattr(pool, "get_connection")
    assert hasattr(pool, "remove_connection")
    assert hasattr(pool, "close_all")

    # Check methods are callable
    assert callable(pool.get_connection)
    assert callable(pool.remove_connection)
    assert callable(pool.close_all)


@pytest.mark.asyncio
async def test_protocol_allows_mocking():
    """Verify protocols enable easy mocking for tests."""
    from unittest.mock import MagicMock

    from scout_mcp.models import SSHHost
    from scout_mcp.protocols import SSHConnectionPool

    # Create mock pool that implements protocol
    class MockPool:
        async def get_connection(self, host: SSHHost):
            mock_conn = MagicMock()
            return mock_conn

        async def remove_connection(self, host_name: str) -> None:
            pass

        async def close_all(self) -> None:
            pass

    mock_pool = MockPool()

    # Should work with protocol type hint
    assert isinstance(mock_pool, SSHConnectionPool)

    # Should be usable like real pool
    host = SSHHost(name="test", hostname="test.example.com", user="root")
    conn = await mock_pool.get_connection(host)
    assert conn is not None


def test_file_operations_protocol_exists():
    """Verify FileOperations protocol is defined."""
    from scout_mcp.protocols import FileOperations

    # Should not raise ImportError
    assert FileOperations is not None


def test_command_executor_protocol_exists():
    """Verify CommandExecutor protocol is defined."""
    from scout_mcp.protocols import CommandExecutor

    # Should not raise ImportError
    assert CommandExecutor is not None


def test_file_reader_protocol_exists():
    """Verify FileReader protocol is defined."""
    from scout_mcp.protocols import FileReader

    # Should not raise ImportError
    assert FileReader is not None

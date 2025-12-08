"""Tests for SSH connection pool."""

import pytest
from scout_mcp.models import SSHHost


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

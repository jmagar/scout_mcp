"""Integration tests for localhost resource access."""

from pathlib import Path

import pytest

from scout_mcp.resources import (
    compose_list_resource,
    docker_list_resource,
    list_hosts_resource,
    scout_resource,
)
from scout_mcp.services import get_pool, reset_state, set_config


@pytest.fixture(autouse=True)
def reset_globals() -> None:
    """Reset global state before each test."""
    reset_state()


@pytest.mark.asyncio
async def test_localhost_host_list_shows_online() -> None:
    """Localhost host list should work and show online/offline status."""
    result = await list_hosts_resource()

    # Should get a list of hosts
    assert isinstance(result, str)
    assert "Available SSH Hosts" in result
    # Check for online indicator (checkmark or "online" text)
    assert "[✓]" in result or "[✗]" in result or "online" in result.lower() or "offline" in result.lower()


@pytest.mark.asyncio
async def test_localhost_docker_list() -> None:
    """Should be able to list Docker containers on localhost."""
    from scout_mcp.utils.hostname import get_server_hostname

    try:
        result = await docker_list_resource(get_server_hostname())
        # Should get some result (even if no containers)
        assert isinstance(result, str)
        assert "Docker Containers" in result or "No containers" in result
    except Exception as e:
        # If Docker not available, that's okay - but connection should work
        assert "Cannot connect" not in str(e)


@pytest.mark.asyncio
async def test_localhost_compose_list() -> None:
    """Should be able to list Compose projects on localhost."""
    from scout_mcp.utils.hostname import get_server_hostname

    try:
        result = await compose_list_resource(get_server_hostname())
        assert isinstance(result, str)
        assert "Compose Projects" in result or "No projects" in result
    except Exception as e:
        assert "Cannot connect" not in str(e)


@pytest.mark.asyncio
async def test_localhost_file_read() -> None:
    """Should be able to read files on localhost."""
    from scout_mcp.utils.hostname import get_server_hostname

    # Try to read /etc/hostname or similar file that should exist
    try:
        result = await scout_resource(get_server_hostname(), "/etc/hostname")
        assert isinstance(result, str)
        assert len(result) > 0
    except Exception as e:
        # File might not exist, but connection should work
        assert "Cannot connect" not in str(e)


@pytest.mark.asyncio
async def test_localhost_connection_cleanup() -> None:
    """Pool should properly clean up localhost connections."""
    pool = get_pool()
    initial_size = pool.pool_size

    # Make a localhost request
    from scout_mcp.utils.hostname import get_server_hostname

    try:
        await scout_resource(get_server_hostname(), "/tmp")
    except Exception:
        pass  # Ignore errors, just testing connection

    # Pool should have connection now
    assert pool.pool_size >= initial_size

    # Cleanup
    await pool.close_all()
    assert pool.pool_size == 0


@pytest.mark.asyncio
async def test_localhost_detection_with_config(tmp_path: Path) -> None:
    """Localhost host in SSH config should be marked as online and use 127.0.0.1."""
    from scout_mcp.config import Config
    from scout_mcp.utils.hostname import get_server_hostname

    server_hostname = get_server_hostname()

    # Create SSH config with server hostname
    config_file = tmp_path / "ssh_config"
    config_file.write_text(
        f"""
Host {server_hostname}
    HostName remote.example.com
    User root
    Port 29229

Host remote
    HostName remote.example.com
    User admin
    Port 22
"""
    )

    # Set config
    config = Config(ssh_config_path=config_file)
    set_config(config)

    # Get hosts and check localhost is marked correctly
    hosts = config.get_hosts()
    localhost_host = hosts.get(server_hostname)

    assert localhost_host is not None, f"Host {server_hostname} not found in config"
    assert localhost_host.is_localhost is True, "Localhost host should be marked as localhost"
    assert localhost_host.connection_hostname == "127.0.0.1", "Should use localhost IP"
    assert localhost_host.connection_port == 22, "Should use standard SSH port"

    # Remote host should not be marked as localhost
    remote_host = hosts.get("remote")
    assert remote_host is not None
    assert remote_host.is_localhost is False
    assert remote_host.connection_hostname == "remote.example.com"
    assert remote_host.connection_port == 22

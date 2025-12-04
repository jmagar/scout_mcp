"""Tests for Docker resource handlers."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp.exceptions import ResourceError

from scout_mcp.config import Config


@pytest.fixture
def mock_ssh_config(tmp_path: Path) -> Path:
    """Create a temporary SSH config."""
    config_file = tmp_path / "ssh_config"
    config_file.write_text("""
Host tootie
    HostName 192.168.1.10
    User admin
""")
    return config_file


@pytest.mark.asyncio
async def test_docker_logs_resource_returns_logs(mock_ssh_config: Path) -> None:
    """docker_logs_resource returns formatted container logs."""
    from scout_mcp.resources.docker import docker_logs_resource

    config = Config(ssh_config_path=mock_ssh_config)

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()

    with patch(
        "scout_mcp.resources.docker.get_config", return_value=config
    ), patch(
        "scout_mcp.services.state.get_pool", return_value=mock_pool
    ), patch(
        "scout_mcp.resources.docker.docker_logs",
        return_value=("2024-01-01T00:00:00Z Test log line", True),
    ):

        result = await docker_logs_resource("tootie", "plex")

        assert "Container Logs: plex@tootie" in result
        assert "Test log line" in result


@pytest.mark.asyncio
async def test_docker_logs_resource_unknown_host(mock_ssh_config: Path) -> None:
    """docker_logs_resource raises ResourceError for unknown host."""
    from scout_mcp.resources.docker import docker_logs_resource

    config = Config(ssh_config_path=mock_ssh_config)

    with patch(
        "scout_mcp.resources.docker.get_config", return_value=config
    ), pytest.raises(ResourceError, match="Unknown host 'unknown'"):
        await docker_logs_resource("unknown", "plex")


@pytest.mark.asyncio
async def test_docker_logs_resource_container_not_found(mock_ssh_config: Path) -> None:
    """docker_logs_resource raises ResourceError for missing container."""
    from scout_mcp.resources.docker import docker_logs_resource

    config = Config(ssh_config_path=mock_ssh_config)

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()

    with patch(
        "scout_mcp.resources.docker.get_config", return_value=config
    ), patch(
        "scout_mcp.services.state.get_pool", return_value=mock_pool
    ), patch(
        "scout_mcp.resources.docker.docker_logs",
        return_value=("", False),
    ), pytest.raises(ResourceError, match="not found"):
        await docker_logs_resource("tootie", "missing")


@pytest.mark.asyncio
async def test_docker_list_resource_returns_containers(mock_ssh_config: Path) -> None:
    """docker_list_resource returns formatted container list."""
    from scout_mcp.resources.docker import docker_list_resource

    config = Config(ssh_config_path=mock_ssh_config)

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()

    containers = [
        {"name": "plex", "status": "Up 2 days", "image": "plexinc/pms-docker"},
        {"name": "nginx", "status": "Exited (0)", "image": "nginx:latest"},
    ]

    with patch(
        "scout_mcp.resources.docker.get_config", return_value=config
    ), patch(
        "scout_mcp.services.state.get_pool", return_value=mock_pool
    ), patch(
        "scout_mcp.resources.docker.docker_ps",
        return_value=containers,
    ):

        result = await docker_list_resource("tootie")

        assert "Docker Containers on tootie" in result
        assert "plex" in result
        assert "nginx" in result
        assert "tootie://docker/plex/logs" in result


@pytest.mark.asyncio
async def test_docker_list_resource_no_containers(mock_ssh_config: Path) -> None:
    """docker_list_resource handles no containers gracefully."""
    from scout_mcp.resources.docker import docker_list_resource

    config = Config(ssh_config_path=mock_ssh_config)

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()

    with patch(
        "scout_mcp.resources.docker.get_config", return_value=config
    ), patch(
        "scout_mcp.services.state.get_pool", return_value=mock_pool
    ), patch(
        "scout_mcp.resources.docker.docker_ps",
        return_value=[],
    ):

        result = await docker_list_resource("tootie")

        assert "Docker Containers on tootie" in result
        assert "No containers found" in result

"""Tests for Docker resource handlers."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp.exceptions import ResourceError

from scout_mcp.config import Config
from scout_mcp.dependencies import Dependencies


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


@pytest.fixture
def deps(mock_ssh_config: Path) -> Dependencies:
    """Create Dependencies with mock config and pool."""
    config = Config(ssh_config_path=mock_ssh_config)
    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()
    return Dependencies(config=config, pool=mock_pool)


@pytest.mark.asyncio
async def test_docker_logs_resource_returns_logs(deps: Dependencies) -> None:
    """docker_logs_resource returns HTML with formatted container logs."""
    from scout_mcp.resources.docker import docker_logs_resource

    with patch(
        "scout_mcp.resources.docker.docker_logs",
        return_value=("2024-01-01T00:00:00Z Test log line", True),
    ):
        result = await docker_logs_resource("tootie", "plex", deps)

        # Should return HTML string
        assert isinstance(result, str)
        assert "<!DOCTYPE html>" in result
        assert "Test log line" in result
        assert "tootie" in result


@pytest.mark.asyncio
async def test_docker_logs_resource_unknown_host(deps: Dependencies) -> None:
    """docker_logs_resource raises ResourceError for unknown host."""
    from scout_mcp.resources.docker import docker_logs_resource

    with pytest.raises(ResourceError, match="Unknown host 'unknown'"):
        await docker_logs_resource("unknown", "plex", deps)


@pytest.mark.asyncio
async def test_docker_logs_resource_container_not_found(deps: Dependencies) -> None:
    """docker_logs_resource raises ResourceError for missing container."""
    from scout_mcp.resources.docker import docker_logs_resource

    with (
        patch(
            "scout_mcp.resources.docker.docker_logs",
            return_value=("", False),
        ),
        pytest.raises(ResourceError, match="not found"),
    ):
        await docker_logs_resource("tootie", "missing", deps)


@pytest.mark.asyncio
async def test_docker_list_resource_returns_containers(deps: Dependencies) -> None:
    """docker_list_resource returns formatted container list."""
    from scout_mcp.resources.docker import docker_list_resource

    with patch(
        "scout_mcp.resources.docker.docker_ps",
        return_value=[
            {
                "name": "plex",
                "status": "Up 5 days",
                "image": "plexinc/pms-docker:latest",
            },
        ],
    ):
        result = await docker_list_resource("tootie", deps)

        assert "# Docker Containers on tootie" in result
        assert "plex" in result
        assert "Up 5 days" in result


@pytest.mark.asyncio
async def test_docker_list_resource_no_containers(deps: Dependencies) -> None:
    """docker_list_resource returns message when no containers found."""
    from scout_mcp.resources.docker import docker_list_resource

    with patch(
        "scout_mcp.resources.docker.docker_ps",
        return_value=[],
    ):
        result = await docker_list_resource("tootie", deps)

        assert "No containers found" in result

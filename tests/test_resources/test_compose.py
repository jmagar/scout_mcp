"""Tests for Docker Compose resource handlers."""

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
async def test_compose_list_resource_returns_projects(deps: Dependencies) -> None:
    """compose_list_resource returns formatted project list."""
    from scout_mcp.resources.compose import compose_list_resource

    projects = [
        {
            "name": "plex",
            "status": "running(1)",
            "config_file": "/compose/plex/docker-compose.yaml",
        },
        {
            "name": "nginx",
            "status": "exited(0)",
            "config_file": "/compose/nginx/docker-compose.yaml",
        },
    ]

    with patch(
        "scout_mcp.resources.compose.compose_ls",
        return_value=projects,
    ):
        result = await compose_list_resource("tootie", deps)

        assert "Docker Compose Projects on tootie" in result
        assert "plex" in result
        assert "nginx" in result
        assert "tootie://compose/plex" in result


@pytest.mark.asyncio
async def test_compose_file_resource_returns_config(deps: Dependencies) -> None:
    """compose_file_resource returns compose file contents."""
    from scout_mcp.resources.compose import compose_file_resource

    with patch(
        "scout_mcp.resources.compose.compose_config",
        return_value=(
            "services:\n  plex:\n    image: plex",
            "/compose/plex/docker-compose.yaml",
        ),
    ):
        result = await compose_file_resource("tootie", "plex", deps)

        assert "plex@tootie" in result
        assert "services:" in result


@pytest.mark.asyncio
async def test_compose_file_resource_project_not_found(deps: Dependencies) -> None:
    """compose_file_resource raises ResourceError for missing project."""
    from scout_mcp.resources.compose import compose_file_resource

    with (
        patch(
            "scout_mcp.resources.compose.compose_config",
            return_value=("", None),
        ),
        pytest.raises(ResourceError, match="not found"),
    ):
        await compose_file_resource("tootie", "missing", deps)


@pytest.mark.asyncio
async def test_compose_logs_resource_returns_logs(deps: Dependencies) -> None:
    """compose_logs_resource returns HTML with formatted logs."""
    from scout_mcp.resources.compose import compose_logs_resource

    with patch(
        "scout_mcp.resources.compose.compose_logs",
        return_value=("plex  | Starting server", True),
    ):
        result = await compose_logs_resource("tootie", "plex", deps)

        # Should return HTML string
        assert isinstance(result, str)
        assert "<!DOCTYPE html>" in result
        assert "Starting server" in result

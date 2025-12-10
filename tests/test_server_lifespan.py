"""Tests for server lifespan and dynamic resource registration."""

from pathlib import Path
from unittest.mock import patch

import pytest

from scout_mcp.config import Config


@pytest.fixture
def mock_ssh_config(tmp_path: Path) -> Path:
    """Create a temporary SSH config with multiple hosts."""
    config_file = tmp_path / "ssh_config"
    config_file.write_text("""
Host tootie
    HostName 192.168.1.10
    User admin

Host squirts
    HostName 192.168.1.20
    User root
""")
    return config_file


@pytest.mark.asyncio
async def test_lifespan_registers_host_templates(mock_ssh_config: Path) -> None:
    """Lifespan registers a resource template for each SSH host."""
    from scout_mcp.server import app_lifespan, create_server

    config = Config.from_ssh_config(ssh_config_path=mock_ssh_config)

    with patch("scout_mcp.server.get_config", return_value=config):
        mcp = create_server()

        # Manually trigger lifespan to register templates
        async with app_lifespan(mcp) as result:
            # Check that resource templates are registered
            # FastMCP stores templates, we need to verify they're added
            # The lifespan should register tootie://{path*} and squirts://{path*}
            # We verify by checking if the templates attribute has our patterns
            templates = [
                t.uri_template for t in mcp._resource_manager._templates.values()
            ]

            assert any("tootie://" in t for t in templates), (
                f"Expected tootie:// template in {templates}"
            )
            assert any("squirts://" in t for t in templates), (
                f"Expected squirts:// template in {templates}"
            )

            # Also verify the hosts are in the result
            assert "hosts" in result
            assert "tootie" in result["hosts"]
            assert "squirts" in result["hosts"]


@pytest.mark.asyncio
async def test_read_host_path_reads_file(mock_ssh_config: Path) -> None:
    """_read_host_path reads file contents via SSH."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from scout_mcp.config import Config
    from scout_mcp.server import _read_host_path

    config = Config.from_ssh_config(ssh_config_path=mock_ssh_config)

    # Mock the SSH connection and pool
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        side_effect=[
            MagicMock(stdout="regular file", returncode=0),  # stat call
            MagicMock(stdout="file contents here", returncode=0),  # cat call
        ]
    )

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock(return_value=mock_conn)
    mock_pool.remove_connection = AsyncMock()

    with (
        patch("scout_mcp.server.get_config", return_value=config),
        patch("scout_mcp.resources.scout.get_config", return_value=config),
        patch("scout_mcp.services.state.get_pool", return_value=mock_pool),
    ):
        result = await _read_host_path("tootie", "etc/hosts")

        # Should return file contents without directory header
        assert "file contents here" in result
        assert "Directory:" not in result

        # Verify the connection was acquired
        mock_pool.get_connection.assert_called_once()


@pytest.mark.asyncio
async def test_read_host_path_lists_directory(mock_ssh_config: Path) -> None:
    """_read_host_path lists directory contents."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from scout_mcp.config import Config
    from scout_mcp.server import _read_host_path

    config = Config.from_ssh_config(ssh_config_path=mock_ssh_config)

    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        side_effect=[
            MagicMock(stdout="directory", returncode=0),  # stat call
            MagicMock(
                stdout="total 4\ndrwxr-xr-x 2 root root 4096 Jan 1 00:00 .",
                returncode=0,
            ),  # ls call
        ]
    )

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock(return_value=mock_conn)
    mock_pool.remove_connection = AsyncMock()

    with (
        patch("scout_mcp.server.get_config", return_value=config),
        patch("scout_mcp.resources.scout.get_config", return_value=config),
        patch("scout_mcp.services.state.get_pool", return_value=mock_pool),
    ):
        result = await _read_host_path("tootie", "etc")

        # Should return directory listing with header and ls output
        assert "Directory:" in result
        assert "tootie:/etc" in result
        assert "drwx" in result

        # Verify the connection was acquired
        mock_pool.get_connection.assert_called_once()


@pytest.mark.asyncio
async def test_read_host_path_unknown_host_raises_error(mock_ssh_config: Path) -> None:
    """_read_host_path raises ResourceError for unknown host."""
    from unittest.mock import patch

    from fastmcp.exceptions import ResourceError

    from scout_mcp.config import Config
    from scout_mcp.server import _read_host_path

    config = Config.from_ssh_config(ssh_config_path=mock_ssh_config)

    with (
        patch("scout_mcp.server.get_config", return_value=config),
        patch("scout_mcp.resources.scout.get_config", return_value=config),
        pytest.raises(ResourceError, match="Unknown host 'unknown'"),
    ):
        await _read_host_path("unknown", "etc/hosts")


@pytest.mark.asyncio
async def test_dynamic_resource_integration(mock_ssh_config: Path) -> None:
    """Dynamic host resources work end-to-end through lifespan."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from scout_mcp.config import Config
    from scout_mcp.server import _read_host_path, app_lifespan, create_server

    config = Config.from_ssh_config(ssh_config_path=mock_ssh_config)

    # Mock the SSH connection and pool
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        side_effect=[
            MagicMock(stdout="regular file", returncode=0),  # stat call
            MagicMock(stdout="test file contents", returncode=0),  # cat call
        ]
    )

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock(return_value=mock_conn)
    mock_pool.remove_connection = AsyncMock()

    with (
        patch("scout_mcp.server.get_config", return_value=config),
        patch("scout_mcp.resources.scout.get_config", return_value=config),
        patch("scout_mcp.services.state.get_pool", return_value=mock_pool),
    ):
        mcp = create_server()

        # Trigger lifespan to register dynamic resources
        async with app_lifespan(mcp):
            # Verify the template was registered
            templates = [
                t.uri_template for t in mcp._resource_manager._templates.values()
            ]
            assert any("tootie://" in t for t in templates)

            # Verify the filesystem template has correct metadata
            tootie_template = None
            for template in mcp._resource_manager._templates.values():
                uri = template.uri_template
                if "tootie://" in uri and "path" in uri:
                    tootie_template = template
                    break

            assert tootie_template is not None, "tootie://{{path*}} template not found"
            assert tootie_template.name == "tootie filesystem"
            assert "tootie" in tootie_template.description

            # Verify we can read through the helper function
            result = await _read_host_path("tootie", "etc/hosts")
            assert "test file contents" in result
            assert mock_pool.get_connection.called


@pytest.mark.asyncio
async def test_lifespan_registers_docker_templates(mock_ssh_config: Path) -> None:
    """Lifespan registers Docker resource templates for each host."""
    from scout_mcp.server import app_lifespan, create_server

    config = Config.from_ssh_config(ssh_config_path=mock_ssh_config)

    with patch("scout_mcp.server.get_config", return_value=config):
        mcp = create_server()

        async with app_lifespan(mcp):
            templates = [
                t.uri_template for t in mcp._resource_manager._templates.values()
            ]

            # Non-template resources (no placeholders)
            resources = [str(r.uri) for r in mcp._resource_manager._resources.values()]

            # Should have docker logs templates
            assert any("tootie://docker/" in t and "/logs" in t for t in templates), (
                f"Expected tootie://docker/*/logs template in {templates}"
            )
            assert any("squirts://docker/" in t and "/logs" in t for t in templates), (
                f"Expected squirts://docker/*/logs template in {templates}"
            )

            # Should have docker list resources (no template params)
            assert any("tootie://docker" in r for r in resources), (
                f"Expected tootie://docker resource in {resources}"
            )

            # Should still have filesystem templates
            assert any("tootie://" in t and "docker" not in t for t in templates), (
                f"Expected tootie://path template in {templates}"
            )


@pytest.mark.asyncio
async def test_lifespan_registers_compose_templates(mock_ssh_config: Path) -> None:
    """Lifespan registers Compose resource templates for each host."""
    from scout_mcp.server import app_lifespan, create_server

    config = Config.from_ssh_config(ssh_config_path=mock_ssh_config)

    with patch("scout_mcp.server.get_config", return_value=config):
        mcp = create_server()

        async with app_lifespan(mcp):
            templates = [
                t.uri_template for t in mcp._resource_manager._templates.values()
            ]

            resources = [str(r.uri) for r in mcp._resource_manager._resources.values()]

            # Should have compose file templates
            has_compose_project = any(
                "tootie://compose/" in t and "project" in t for t in templates
            )
            assert has_compose_project, (
                f"Expected tootie://compose/{{project}} template in {templates}"
            )

            # Should have compose logs templates
            has_compose_logs = any(
                "tootie://compose/" in t and "/logs" in t for t in templates
            )
            assert has_compose_logs, (
                f"Expected tootie://compose/{{project}}/logs template in {templates}"
            )

            # Should have compose list resources
            has_compose_list = any(
                "tootie://compose" in r and "project" not in r for r in resources
            )
            assert has_compose_list, (
                f"Expected tootie://compose resource in {resources}"
            )


@pytest.mark.asyncio
async def test_lifespan_registers_zfs_templates(mock_ssh_config: Path) -> None:
    """Lifespan registers ZFS resource templates for each host."""
    from scout_mcp.server import app_lifespan, create_server

    config = Config.from_ssh_config(ssh_config_path=mock_ssh_config)

    with patch("scout_mcp.server.get_config", return_value=config):
        mcp = create_server()

        async with app_lifespan(mcp):
            templates = [
                t.uri_template for t in mcp._resource_manager._templates.values()
            ]

            resources = [str(r.uri) for r in mcp._resource_manager._resources.values()]

            # Should have zfs pool templates
            assert any("tootie://zfs/" in t and "pool" in t for t in templates), (
                f"Expected tootie://zfs/{{pool}} template in {templates}"
            )

            # Should have zfs datasets templates
            assert any("tootie://zfs/" in t and "/datasets" in t for t in templates), (
                f"Expected tootie://zfs/{{pool}}/datasets template in {templates}"
            )

            # Should have zfs overview resources
            assert any("tootie://zfs" in r and "pool" not in r for r in resources), (
                f"Expected tootie://zfs resource in {resources}"
            )

            # Should have zfs snapshots resources
            assert any("tootie://zfs/snapshots" in r for r in resources), (
                f"Expected tootie://zfs/snapshots resource in {resources}"
            )


@pytest.mark.asyncio
async def test_lifespan_registers_syslog_resources(mock_ssh_config: Path) -> None:
    """Lifespan registers syslog resources for each host."""
    from scout_mcp.server import app_lifespan, create_server

    config = Config.from_ssh_config(ssh_config_path=mock_ssh_config)

    with patch("scout_mcp.server.get_config", return_value=config):
        mcp = create_server()

        async with app_lifespan(mcp):
            resources = [str(r.uri) for r in mcp._resource_manager._resources.values()]

            # Should have syslog resources
            assert any("tootie://syslog" in r for r in resources), (
                f"Expected tootie://syslog resource in {resources}"
            )
            assert any("squirts://syslog" in r for r in resources), (
                f"Expected squirts://syslog resource in {resources}"
            )

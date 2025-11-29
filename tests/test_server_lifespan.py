"""Tests for server lifespan and dynamic resource registration."""

import pytest
from pathlib import Path
from unittest.mock import patch

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
    from scout_mcp.server import create_server, app_lifespan

    config = Config(ssh_config_path=mock_ssh_config)

    with patch("scout_mcp.server.get_config", return_value=config):
        mcp = create_server()

        # Manually trigger lifespan to register templates
        async with app_lifespan(mcp) as result:
            # Check that resource templates are registered
            # FastMCP stores templates, we need to verify they're added
            # The lifespan should register tootie://{path*} and squirts://{path*}
            # We verify by checking if the templates attribute has our patterns
            templates = [t.uri_template for t in mcp._resource_manager._templates.values()]

            assert any("tootie://" in t for t in templates), f"Expected tootie:// template in {templates}"
            assert any("squirts://" in t for t in templates), f"Expected squirts:// template in {templates}"

            # Also verify the hosts are in the result
            assert "hosts" in result
            assert "tootie" in result["hosts"]
            assert "squirts" in result["hosts"]

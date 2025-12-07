"""Tests for hosts resource."""

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
async def test_hosts_resource_shows_dynamic_schemes(mock_ssh_config: Path) -> None:
    """hosts://list shows host-specific URI schemes."""
    from scout_mcp.resources.hosts import list_hosts_resource

    config = Config(ssh_config_path=mock_ssh_config)

    # Mock ping to return all hosts online
    async def mock_check_hosts(
        hosts: dict[str, tuple[str, int]], timeout: float
    ) -> dict[str, bool]:
        return {name: True for name in hosts}

    with (
        patch("scout_mcp.resources.hosts.get_config", return_value=config),
        patch(
            "scout_mcp.resources.hosts.check_hosts_online",
            side_effect=mock_check_hosts,
        ),
    ):
        result = await list_hosts_resource()

        # Should show host-specific schemes
        assert "tootie://" in result, f"Expected tootie:// in output: {result}"
        assert "squirts://" in result, f"Expected squirts:// in output: {result}"

        # Should also show fallback generic scheme
        assert "scout://" in result, f"Expected scout:// fallback in output: {result}"


@pytest.mark.asyncio
async def test_hosts_resource_shows_examples(mock_ssh_config: Path) -> None:
    """hosts://list shows example URIs for each host."""
    from scout_mcp.resources.hosts import list_hosts_resource

    config = Config(ssh_config_path=mock_ssh_config)

    async def mock_check_hosts(
        hosts: dict[str, tuple[str, int]], timeout: float
    ) -> dict[str, bool]:
        return {name: True for name in hosts}

    with (
        patch("scout_mcp.resources.hosts.get_config", return_value=config),
        patch(
            "scout_mcp.resources.hosts.check_hosts_online",
            side_effect=mock_check_hosts,
        ),
    ):
        result = await list_hosts_resource()

        # Should show practical examples
        assert "etc/hosts" in result or "/etc" in result, "Should show path examples"

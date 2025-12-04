"""Tests for syslog resource handler."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

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
async def test_syslog_resource_returns_logs(mock_ssh_config: Path) -> None:
    """syslog_resource returns formatted log output."""
    from scout_mcp.resources.syslog import syslog_resource

    config = Config(ssh_config_path=mock_ssh_config)

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()

    log_content = (
        "Nov 29 12:00:00 tootie sshd[123]: Connection accepted\n"
        "Nov 29 12:00:01 tootie kernel: eth0: link up"
    )

    with patch(
        "scout_mcp.resources.syslog.get_config", return_value=config
    ), patch(
        "scout_mcp.services.state.get_pool", return_value=mock_pool
    ), patch(
        "scout_mcp.resources.syslog.syslog_read",
        return_value=(log_content, "journalctl"),
    ):
        result = await syslog_resource("tootie")

        assert "System Logs: tootie" in result
        assert "journalctl" in result
        assert "sshd" in result
        assert "kernel" in result


@pytest.mark.asyncio
async def test_syslog_resource_no_logs_available(mock_ssh_config: Path) -> None:
    """syslog_resource shows message when no logs available."""
    from scout_mcp.resources.syslog import syslog_resource

    config = Config(ssh_config_path=mock_ssh_config)

    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()

    with patch(
        "scout_mcp.resources.syslog.get_config", return_value=config
    ), patch(
        "scout_mcp.services.state.get_pool", return_value=mock_pool
    ), patch(
        "scout_mcp.resources.syslog.syslog_read",
        return_value=("", "none"),
    ):
        result = await syslog_resource("tootie")

        assert "not available" in result.lower()

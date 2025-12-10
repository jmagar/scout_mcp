"""Tests for syslog resource handler."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

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
    config = Config.from_ssh_config(ssh_config_path=mock_ssh_config)
    mock_pool = AsyncMock()
    mock_pool.get_connection = AsyncMock()
    mock_pool.remove_connection = AsyncMock()
    return Dependencies(config=config, pool=mock_pool)


@pytest.mark.asyncio
async def test_syslog_resource_returns_logs(deps: Dependencies) -> None:
    """syslog_resource returns HTML with formatted log output."""
    from scout_mcp.resources.syslog import syslog_resource

    log_content = (
        "Nov 29 12:00:00 tootie sshd[123]: Connection accepted\n"
        "Nov 29 12:00:01 tootie kernel: eth0: link up"
    )

    with patch(
        "scout_mcp.resources.syslog.syslog_read",
        return_value=(log_content, "journalctl"),
    ):
        result = await syslog_resource("tootie", deps)

        # Should return HTML string
        assert isinstance(result, str)
        assert "<!DOCTYPE html>" in result
        assert "sshd" in result
        assert "kernel" in result


@pytest.mark.asyncio
async def test_syslog_resource_no_logs_available(deps: Dependencies) -> None:
    """syslog_resource shows HTML message when no logs available."""
    from scout_mcp.resources.syslog import syslog_resource

    with patch(
        "scout_mcp.resources.syslog.syslog_read",
        return_value=("", "none"),
    ):
        result = await syslog_resource("tootie", deps)

        # Should return HTML string with error message
        assert isinstance(result, str)
        assert "not available" in result.lower()

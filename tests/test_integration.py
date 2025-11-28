"""Integration tests for MCP-Cat server."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import mcp_cat.server as server_module
import pytest

# Access the actual function from the FunctionTool wrapper
scout_fn = server_module.scout.fn


@pytest.fixture(autouse=True)
def reset_globals() -> None:
    """Reset global state before each test."""
    server_module._config = None
    server_module._pool = None


@pytest.fixture
def mock_ssh_config(tmp_path: Path) -> Path:
    """Create a temporary SSH config."""
    config_file = tmp_path / "ssh_config"
    config_file.write_text("""
Host testhost
    HostName 192.168.1.100
    User testuser
    Port 22
""")
    return config_file


@pytest.mark.asyncio
async def test_scout_hosts_lists_available(mock_ssh_config: Path) -> None:
    """scout('hosts') lists available SSH hosts."""
    with patch.object(server_module, "_config", None):
        from mcp_cat.config import Config

        server_module._config = Config(ssh_config_path=mock_ssh_config)

        result = await scout_fn("hosts")

        assert "testhost" in result
        assert "testuser@192.168.1.100" in result


@pytest.mark.asyncio
async def test_scout_unknown_host_returns_error() -> None:
    """scout with unknown host returns helpful error."""
    from mcp_cat.config import Config

    server_module._config = Config(ssh_config_path=Path("/nonexistent"))

    result = await scout_fn("unknownhost:/path")

    assert "Error" in result
    assert "Unknown host" in result


@pytest.mark.asyncio
async def test_scout_invalid_target_returns_error() -> None:
    """scout with invalid target returns error."""
    result = await scout_fn("invalid-no-colon")

    assert "Error" in result
    assert "Invalid target" in result


@pytest.mark.asyncio
async def test_scout_cat_file(mock_ssh_config: Path) -> None:
    """scout with file path cats the file."""
    from mcp_cat.config import Config

    server_module._config = Config(ssh_config_path=mock_ssh_config)

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    # stat returns file
    mock_conn.run.side_effect = [
        MagicMock(stdout="regular file", returncode=0),  # stat
        MagicMock(stdout="file contents here", returncode=0),  # cat
    ]

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        result = await scout_fn("testhost:/etc/hosts")

        assert result == "file contents here"


@pytest.mark.asyncio
async def test_scout_ls_directory(mock_ssh_config: Path) -> None:
    """scout with directory path lists contents."""
    from mcp_cat.config import Config

    server_module._config = Config(ssh_config_path=mock_ssh_config)

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    # stat returns directory
    mock_conn.run.side_effect = [
        MagicMock(stdout="directory", returncode=0),  # stat
        MagicMock(stdout="file1.txt\nfile2.txt", returncode=0),  # ls
    ]

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        result = await scout_fn("testhost:/var/log")

        assert "file1.txt" in result
        assert "file2.txt" in result


@pytest.mark.asyncio
async def test_scout_run_command(mock_ssh_config: Path) -> None:
    """scout with query runs the command."""
    from mcp_cat.config import Config

    server_module._config = Config(ssh_config_path=mock_ssh_config)

    mock_conn = AsyncMock()
    mock_conn.is_closed = False
    mock_conn.run.return_value = MagicMock(
        stdout="TODO: fix this", stderr="", returncode=0
    )

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        result = await scout_fn("testhost:~/code", "rg 'TODO'")

        assert "TODO: fix this" in result

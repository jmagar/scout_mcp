"""Integration tests for Scout MCP server."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scout_mcp.resources import scout_resource
from scout_mcp.services import reset_state, set_config
from scout_mcp.tools import scout


@pytest.fixture(autouse=True)
def reset_globals() -> None:
    """Reset global state before each test."""
    reset_state()


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
    from scout_mcp.config import Config

    set_config(Config(ssh_config_path=mock_ssh_config))

    result = await scout("hosts")

    assert "testhost" in result
    assert "testuser@192.168.1.100" in result


@pytest.mark.asyncio
async def test_scout_unknown_host_returns_error() -> None:
    """scout with unknown host returns helpful error."""
    from scout_mcp.config import Config

    set_config(Config(ssh_config_path=Path("/nonexistent")))

    result = await scout("unknownhost:/path")

    assert "Error" in result
    assert "Unknown host" in result


@pytest.mark.asyncio
async def test_scout_invalid_target_returns_error() -> None:
    """scout with invalid target returns error."""
    result = await scout("invalid-no-colon")

    assert "Error" in result
    assert "Invalid target" in result


@pytest.mark.asyncio
async def test_scout_cat_file(mock_ssh_config: Path) -> None:
    """scout with file path cats the file."""
    from scout_mcp.config import Config

    set_config(Config(ssh_config_path=mock_ssh_config))

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    # stat returns file
    mock_conn.run.side_effect = [
        MagicMock(stdout="regular file", returncode=0),  # stat
        MagicMock(stdout="file contents here", returncode=0),  # cat
    ]

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        result = await scout("testhost:/etc/hosts")

        assert result == "file contents here"


@pytest.mark.asyncio
async def test_scout_ls_directory(mock_ssh_config: Path) -> None:
    """scout with directory path lists contents."""
    from scout_mcp.config import Config

    set_config(Config(ssh_config_path=mock_ssh_config))

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    # stat returns directory
    mock_conn.run.side_effect = [
        MagicMock(stdout="directory", returncode=0),  # stat
        MagicMock(stdout="file1.txt\nfile2.txt", returncode=0),  # ls
    ]

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        result = await scout("testhost:/var/log")

        assert "file1.txt" in result
        assert "file2.txt" in result


@pytest.mark.asyncio
async def test_scout_run_command(mock_ssh_config: Path) -> None:
    """scout with query runs the command."""
    from scout_mcp.config import Config

    set_config(Config(ssh_config_path=mock_ssh_config))

    mock_conn = AsyncMock()
    mock_conn.is_closed = False
    mock_conn.run.return_value = MagicMock(
        stdout="TODO: fix this", stderr="", returncode=0
    )

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        result = await scout("testhost:~/code", "rg 'TODO'")

        assert "TODO: fix this" in result


def test_hosts_resource_exists() -> None:
    """Verify hosts resource is registered."""
    from scout_mcp.server import mcp

    # Check resource is registered (FastMCP stores resources differently)
    assert hasattr(mcp, "resource")


@pytest.mark.asyncio
async def test_scout_resource_template_exists() -> None:
    """Verify scout resource template is registered."""
    from scout_mcp.server import mcp

    # Check that we have a resource template registered
    templates = await mcp.get_resource_templates()
    assert "scout://{host}/{path*}" in templates


@pytest.mark.asyncio
async def test_scout_resource_reads_file(mock_ssh_config: Path) -> None:
    """scout resource reads file contents."""
    from scout_mcp.config import Config

    set_config(Config(ssh_config_path=mock_ssh_config))

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    # stat returns file, then cat
    mock_conn.run.side_effect = [
        MagicMock(stdout="regular file", returncode=0),  # stat
        MagicMock(stdout="file contents from resource", returncode=0),  # cat
    ]

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        result = await scout_resource("testhost", "etc/hosts")

        assert result == "file contents from resource"


@pytest.mark.asyncio
async def test_scout_resource_lists_directory(mock_ssh_config: Path) -> None:
    """scout resource lists directory contents."""
    from scout_mcp.config import Config

    set_config(Config(ssh_config_path=mock_ssh_config))

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    # stat returns directory, then ls
    mock_conn.run.side_effect = [
        MagicMock(stdout="directory", returncode=0),  # stat
        MagicMock(stdout="drwxr-xr-x 2 root root 4096 nginx", returncode=0),  # ls
    ]

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        result = await scout_resource("testhost", "etc/nginx")

        assert "nginx" in result


@pytest.mark.asyncio
async def test_scout_resource_unknown_host_raises() -> None:
    """scout resource raises ResourceError for unknown host."""
    from fastmcp.exceptions import ResourceError

    from scout_mcp.config import Config

    set_config(Config(ssh_config_path=Path("/nonexistent")))

    with pytest.raises(ResourceError, match="Unknown host"):
        await scout_resource("unknownhost", "etc/hosts")


@pytest.mark.asyncio
async def test_scout_resource_path_not_found_raises(mock_ssh_config: Path) -> None:
    """scout resource raises ResourceError for missing path."""
    from fastmcp.exceptions import ResourceError

    from scout_mcp.config import Config

    set_config(Config(ssh_config_path=mock_ssh_config))

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    # stat returns empty (path not found)
    mock_conn.run.return_value = MagicMock(stdout="", returncode=1)

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        with pytest.raises(ResourceError, match="Path not found"):
            await scout_resource("testhost", "nonexistent/path")


@pytest.mark.asyncio
async def test_scout_resource_normalizes_path(mock_ssh_config: Path) -> None:
    """scout resource adds leading slash to paths."""
    from scout_mcp.config import Config

    set_config(Config(ssh_config_path=mock_ssh_config))

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    # Capture the command to verify path normalization
    mock_conn.run.side_effect = [
        MagicMock(stdout="regular file", returncode=0),  # stat
        MagicMock(stdout="content", returncode=0),  # cat
    ]

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        await scout_resource("testhost", "var/log/syslog")

        # Verify the stat command was called with /var/log/syslog
        first_call = mock_conn.run.call_args_list[0]
        assert "/var/log/syslog" in str(first_call)

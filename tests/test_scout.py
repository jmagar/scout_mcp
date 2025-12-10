"""Tests for scout URI parsing and intent detection."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scout_mcp.tools.scout import scout
from scout_mcp.utils.parser import parse_target


def test_parse_target_file_uri() -> None:
    """Parse host:/path/to/file URI."""
    result = parse_target("dookie:/var/log/app.log")

    assert result.host == "dookie"
    assert result.path == "/var/log/app.log"


def test_parse_target_dir_uri() -> None:
    """Parse host:/path/to/dir URI."""
    result = parse_target("tootie:/etc/nginx")

    assert result.host == "tootie"
    assert result.path == "/etc/nginx"


def test_parse_target_home_expansion() -> None:
    """Parse URI with ~ home directory."""
    result = parse_target("squirts:~/code/project")

    assert result.host == "squirts"
    assert result.path == "~/code/project"


def test_parse_target_hosts_command() -> None:
    """Parse 'hosts' as special command."""
    result = parse_target("hosts")

    assert result.host is None
    assert result.is_hosts_command is True


def test_parse_target_invalid_raises() -> None:
    """Invalid URI raises ValueError."""
    with pytest.raises(ValueError, match="Invalid target"):
        parse_target("invalid-no-colon")


def test_parse_target_empty_path_raises() -> None:
    """Empty path raises ValueError."""
    with pytest.raises(ValueError, match="Path cannot be empty"):
        parse_target("dookie:")


def test_parse_target_empty_host_raises() -> None:
    """Empty host raises ValueError."""
    with pytest.raises(ValueError, match="Host cannot be empty"):
        parse_target(":/var/log")


# Beam (file transfer) tests


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
async def test_scout_beam_upload(mock_ssh_config: Path) -> None:
    """Test beam parameter for uploading files."""
    from scout_mcp.config import Config
    from scout_mcp.services import reset_state, set_config

    reset_state()
    set_config(Config.from_ssh_config(ssh_config_path=mock_ssh_config))

    # Create temp local file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("test data\n")
        local_path = f.name

    try:
        # Mock SSH connection and SFTP
        mock_conn = AsyncMock()
        mock_conn.is_closed = False

        # Mock SFTP client as async context manager
        mock_sftp = AsyncMock()
        mock_sftp.put = AsyncMock()

        # Mock the start_sftp_client() to return a proper async context manager
        mock_sftp_ctx = AsyncMock()
        mock_sftp_ctx.__aenter__ = AsyncMock(return_value=mock_sftp)
        mock_sftp_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.start_sftp_client = MagicMock(return_value=mock_sftp_ctx)

        with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_conn

            result = await scout(target="testhost:/tmp/remote.txt", beam=local_path)

            assert "uploaded" in result.lower() or "success" in result.lower()
            assert "error" not in result.lower()
            mock_sftp.put.assert_called_once()

    finally:
        Path(local_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_scout_beam_download(mock_ssh_config: Path) -> None:
    """Test beam parameter for downloading files."""
    from scout_mcp.config import Config
    from scout_mcp.services import reset_state, set_config

    reset_state()
    set_config(Config.from_ssh_config(ssh_config_path=mock_ssh_config))

    with tempfile.TemporaryDirectory() as tmpdir:
        local_path = f"{tmpdir}/downloaded.txt"

        # Mock SSH connection and SFTP
        mock_conn = AsyncMock()
        mock_conn.is_closed = False

        # Mock SFTP client as async context manager
        mock_sftp = AsyncMock()

        # Mock get() to create the file so the handler can stat it
        async def mock_get(src: str, dst: str) -> None:
            Path(dst).write_text("mock content\n")

        mock_sftp.get = AsyncMock(side_effect=mock_get)

        # Mock the start_sftp_client() to return a proper async context manager
        mock_sftp_ctx = AsyncMock()
        mock_sftp_ctx.__aenter__ = AsyncMock(return_value=mock_sftp)
        mock_sftp_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.start_sftp_client = MagicMock(return_value=mock_sftp_ctx)

        with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_conn

            result = await scout(target="testhost:/etc/hostname", beam=local_path)

            assert "downloaded" in result.lower() or "success" in result.lower()
            assert "error" not in result.lower()
            mock_sftp.get.assert_called_once()


@pytest.mark.asyncio
async def test_scout_beam_requires_valid_target(mock_ssh_config: Path) -> None:
    """Test that beam requires a valid target path."""
    from scout_mcp.config import Config
    from scout_mcp.services import reset_state, set_config

    reset_state()
    set_config(Config.from_ssh_config(ssh_config_path=mock_ssh_config))

    result = await scout(target="hosts", beam="/tmp/file.txt")

    assert "error" in result.lower()
    assert "beam" in result.lower() or "target" in result.lower()


@pytest.mark.asyncio
async def test_scout_beam_source_and_target_remote_to_remote():
    """Test remote-to-remote transfer with beam_source and beam_target."""
    with (
        patch("scout_mcp.tools.scout.get_config") as mock_config,
        patch("scout_mcp.tools.scout.get_pool"),
        patch(
            "scout_mcp.tools.handlers.handle_beam_transfer_remote_to_remote"
        ) as mock_handler,
    ):

        # Mock config
        config = AsyncMock()
        config.get_host.side_effect = lambda name: AsyncMock(name=name)
        mock_config.return_value = config

        # Mock handler
        mock_handler.return_value = "✓ Transferred remote1:/src → remote2:/dst"

        result = await scout(
            target="",  # Not used for remote-to-remote
            beam_source="remote1:/src/file.txt",
            beam_target="remote2:/dst/file.txt",
        )

        assert "Transferred" in result
        mock_handler.assert_called_once()


@pytest.mark.asyncio
async def test_scout_beam_source_without_target_error():
    """Test error when beam_source provided without beam_target."""
    result = await scout(
        target="",
        beam_source="remote1:/file.txt",
    )

    assert "Error" in result
    assert "beam_target" in result


@pytest.mark.asyncio
async def test_scout_beam_target_without_source_error():
    """Test error when beam_target provided without beam_source."""
    result = await scout(
        target="",
        beam_target="remote2:/file.txt",
    )

    assert "Error" in result
    assert "beam_source" in result


@pytest.mark.asyncio
async def test_scout_beam_with_beam_source_error():
    """Test error when both beam and beam_source provided."""
    result = await scout(
        target="remote1:/file.txt",
        beam="/local/file.txt",
        beam_source="remote2:/file.txt",
    )

    assert "Error" in result
    assert "cannot use both" in result.lower()

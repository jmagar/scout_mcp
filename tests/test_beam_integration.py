"""Integration tests for beam (file transfer) functionality."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scout_mcp.tools.scout import scout


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
async def test_beam_roundtrip(mock_ssh_config: Path) -> None:
    """Test uploading and downloading a file."""
    from scout_mcp.config import Config
    from scout_mcp.services import reset_state, set_config

    reset_state()
    set_config(Config.from_ssh_config(ssh_config_path=mock_ssh_config))

    # Create temp file with known content
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        original_content = "test beam content\nline 2\n"
        f.write(original_content)
        local_source = f.name

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            remote_path = "/tmp/beam_test_remote.txt"
            local_dest = f"{tmpdir}/downloaded.txt"

            # Mock SSH connection and SFTP
            mock_conn = AsyncMock()
            mock_conn.is_closed = False

            # Mock SFTP client as async context manager
            mock_sftp = AsyncMock()
            mock_sftp.put = AsyncMock()

            # Mock get() to create the file so the handler can stat it
            async def mock_get(src: str, dst: str) -> None:
                Path(dst).write_text(original_content)

            mock_sftp.get = AsyncMock(side_effect=mock_get)

            # Mock the start_sftp_client() to return a proper async context manager
            mock_sftp_ctx = AsyncMock()
            mock_sftp_ctx.__aenter__ = AsyncMock(return_value=mock_sftp)
            mock_sftp_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_conn.start_sftp_client = MagicMock(return_value=mock_sftp_ctx)

            with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
                mock_connect.return_value = mock_conn

                # Upload
                upload_result = await scout(
                    target=f"testhost:{remote_path}", beam=local_source
                )

                assert "uploaded" in upload_result.lower()
                assert "error" not in upload_result.lower()

                # Download
                download_result = await scout(
                    target=f"testhost:{remote_path}", beam=local_dest
                )

                assert "downloaded" in download_result.lower()
                assert "error" not in download_result.lower()

        finally:
            Path(local_source).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_beam_with_nonexistent_remote(mock_ssh_config: Path) -> None:
    """Test beam handles nonexistent remote files gracefully."""
    from scout_mcp.config import Config
    from scout_mcp.services import reset_state, set_config

    reset_state()
    set_config(Config.from_ssh_config(ssh_config_path=mock_ssh_config))

    # Mock SSH connection and SFTP
    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    # Mock SFTP client as async context manager
    mock_sftp = AsyncMock()
    # Mock SFTP to raise error for nonexistent file
    mock_sftp.get = AsyncMock(side_effect=FileNotFoundError("No such file"))

    # Mock the start_sftp_client() to return a proper async context manager
    mock_sftp_ctx = AsyncMock()
    mock_sftp_ctx.__aenter__ = AsyncMock(return_value=mock_sftp)
    mock_sftp_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.start_sftp_client = MagicMock(return_value=mock_sftp_ctx)

    with (
        tempfile.TemporaryDirectory() as tmpdir,
        patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect,
    ):
        mock_connect.return_value = mock_conn

        result = await scout(
            target="testhost:/nonexistent/file.txt", beam=f"{tmpdir}/output.txt"
        )

        assert "error" in result.lower() or "failed" in result.lower()

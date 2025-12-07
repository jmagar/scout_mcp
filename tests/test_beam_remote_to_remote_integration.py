"""Integration tests for remote-to-remote beam transfers."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from scout_mcp.tools.scout import scout


@pytest.mark.asyncio
async def test_remote_to_remote_full_flow(tmp_path):
    """Test complete remote-to-remote transfer flow."""
    with patch("scout_mcp.tools.scout.get_config") as mock_config, \
         patch("scout_mcp.tools.scout.get_pool") as mock_pool, \
         patch("scout_mcp.services.get_connection_with_retry") as mock_conn, \
         patch("scout_mcp.utils.hostname.get_local_hostname") as mock_hostname:

        # Setup mocks
        config = AsyncMock()
        source_host = AsyncMock(name="remote1")
        target_host = AsyncMock(name="remote2")

        config.get_host.side_effect = lambda name: source_host if name == "remote1" else target_host
        mock_config.return_value = config

        mock_hostname.return_value = "localhost"

        # Mock SSH connections
        source_conn = AsyncMock()
        target_conn = AsyncMock()
        mock_conn.side_effect = [source_conn, target_conn]

        # Mock SFTP
        source_sftp = AsyncMock()
        target_sftp = AsyncMock()

        source_conn.start_sftp_client.return_value.__aenter__.return_value = source_sftp
        target_conn.start_sftp_client.return_value.__aenter__.return_value = target_sftp

        # Execute transfer
        result = await scout(
            beam_source="remote1:/src/file.txt",
            beam_target="remote2:/dst/file.txt",
        )

        # Verify success
        assert "✓" in result or "Transferred" in result

        # Verify SFTP operations were called
        source_sftp.get.assert_called_once()
        target_sftp.put.assert_called_once()


@pytest.mark.asyncio
async def test_optimization_when_server_is_source(tmp_path):
    """Test optimization when MCP server is the source host."""
    with patch("scout_mcp.tools.scout.get_config") as mock_config, \
         patch("scout_mcp.services.get_connection_with_retry") as mock_conn, \
         patch("scout_mcp.utils.hostname.get_local_hostname") as mock_hostname:

        # Setup: MCP server is "tootie"
        config = AsyncMock()
        target_host = AsyncMock(name="remote1")

        config.get_host.return_value = target_host
        mock_config.return_value = config

        mock_hostname.return_value = "tootie"

        # Mock connection (only to target)
        target_conn = AsyncMock()
        mock_conn.return_value = target_conn

        # Mock SFTP
        target_sftp = AsyncMock()
        target_conn.start_sftp_client.return_value.__aenter__.return_value = target_sftp

        # Create local source file
        source_file = tmp_path / "source.txt"
        source_file.write_text("test content")

        # Execute transfer
        with patch("scout_mcp.tools.handlers.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.stat.return_value.st_size = 12

            result = await scout(
                beam_source=f"tootie:{source_file}",
                beam_target="remote1:/dst/file.txt",
            )

        # Should be optimized to direct upload (no download)
        assert "✓" in result or "Uploaded" in result
        target_sftp.put.assert_called_once()

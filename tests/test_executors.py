"""Tests for SSH command executors."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp_cat.executors import cat_file, ls_dir, run_command, stat_path


@pytest.fixture
def mock_connection() -> AsyncMock:
    """Create a mock SSH connection."""
    conn = AsyncMock()
    return conn


@pytest.mark.asyncio
async def test_stat_path_returns_file(mock_connection: AsyncMock) -> None:
    """stat_path returns 'file' for regular files."""
    mock_connection.run.return_value = MagicMock(
        stdout="regular file",
        returncode=0
    )

    result = await stat_path(mock_connection, "/var/log/app.log")

    assert result == "file"
    mock_connection.run.assert_called_once()


@pytest.mark.asyncio
async def test_stat_path_returns_directory(mock_connection: AsyncMock) -> None:
    """stat_path returns 'directory' for directories."""
    mock_connection.run.return_value = MagicMock(
        stdout="directory",
        returncode=0
    )

    result = await stat_path(mock_connection, "/var/log")

    assert result == "directory"


@pytest.mark.asyncio
async def test_stat_path_returns_none_for_missing(mock_connection: AsyncMock) -> None:
    """stat_path returns None for non-existent paths."""
    mock_connection.run.return_value = MagicMock(
        stdout="",
        returncode=1
    )

    result = await stat_path(mock_connection, "/nonexistent")

    assert result is None


@pytest.mark.asyncio
async def test_cat_file_returns_contents(mock_connection: AsyncMock) -> None:
    """cat_file returns file contents."""
    mock_connection.run.return_value = MagicMock(
        stdout="file contents here",
        returncode=0
    )

    result = await cat_file(mock_connection, "/etc/hosts", max_size=1024)

    assert result == "file contents here"


@pytest.mark.asyncio
async def test_cat_file_respects_max_size(mock_connection: AsyncMock) -> None:
    """cat_file uses head to limit file size."""
    mock_connection.run.return_value = MagicMock(
        stdout="truncated",
        returncode=0
    )

    await cat_file(mock_connection, "/var/log/huge.log", max_size=1024)

    # Should use head -c to limit bytes
    call_args = mock_connection.run.call_args[0][0]
    assert "head -c 1024" in call_args


@pytest.mark.asyncio
async def test_ls_dir_returns_listing(mock_connection: AsyncMock) -> None:
    """ls_dir returns directory listing."""
    mock_connection.run.return_value = MagicMock(
        stdout="file1.txt\nfile2.txt\nsubdir/",
        returncode=0
    )

    result = await ls_dir(mock_connection, "/home/user")

    assert "file1.txt" in result


@pytest.mark.asyncio
async def test_run_command_returns_output(mock_connection: AsyncMock) -> None:
    """run_command executes arbitrary command."""
    mock_connection.run.return_value = MagicMock(
        stdout="search results",
        stderr="",
        returncode=0
    )

    result = await run_command(
        mock_connection,
        "/home/user",
        "rg 'TODO'",
        timeout=30
    )

    assert result.output == "search results"
    assert result.returncode == 0


@pytest.mark.asyncio
async def test_run_command_includes_stderr(mock_connection: AsyncMock) -> None:
    """run_command includes stderr in result."""
    mock_connection.run.return_value = MagicMock(
        stdout="",
        stderr="error message",
        returncode=1
    )

    result = await run_command(
        mock_connection,
        "/home/user",
        "failing-command",
        timeout=30
    )

    assert result.error == "error message"
    assert result.returncode == 1

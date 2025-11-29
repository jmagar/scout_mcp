"""Tests for SSH command executors."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from scout_mcp.services.executors import cat_file, ls_dir, run_command, stat_path


@pytest.fixture
def mock_connection() -> AsyncMock:
    """Create a mock SSH connection."""
    conn = AsyncMock()
    return conn


@pytest.mark.asyncio
async def test_stat_path_returns_file(mock_connection: AsyncMock) -> None:
    """stat_path returns 'file' for regular files."""
    mock_connection.run.return_value = MagicMock(stdout="regular file", returncode=0)

    result = await stat_path(mock_connection, "/var/log/app.log")

    assert result == "file"
    mock_connection.run.assert_called_once()


@pytest.mark.asyncio
async def test_stat_path_returns_directory(mock_connection: AsyncMock) -> None:
    """stat_path returns 'directory' for directories."""
    mock_connection.run.return_value = MagicMock(stdout="directory", returncode=0)

    result = await stat_path(mock_connection, "/var/log")

    assert result == "directory"


@pytest.mark.asyncio
async def test_stat_path_returns_none_for_missing(mock_connection: AsyncMock) -> None:
    """stat_path returns None for non-existent paths."""
    mock_connection.run.return_value = MagicMock(stdout="", returncode=1)

    result = await stat_path(mock_connection, "/nonexistent")

    assert result is None


@pytest.mark.asyncio
async def test_cat_file_returns_contents(mock_connection: AsyncMock) -> None:
    """cat_file returns file contents and truncation status."""
    mock_connection.run.return_value = MagicMock(
        stdout="file contents here", returncode=0
    )

    content, was_truncated = await cat_file(
        mock_connection, "/etc/hosts", max_size=1024
    )

    assert content == "file contents here"
    assert was_truncated is False


@pytest.mark.asyncio
async def test_cat_file_respects_max_size(mock_connection: AsyncMock) -> None:
    """cat_file uses head to limit file size."""
    mock_connection.run.return_value = MagicMock(stdout="truncated", returncode=0)

    content, was_truncated = await cat_file(
        mock_connection, "/var/log/huge.log", max_size=1024
    )

    # Should use head -c to limit bytes
    call_args = mock_connection.run.call_args[0][0]
    assert "head -c 1024" in call_args


@pytest.mark.asyncio
async def test_cat_file_detects_truncation(mock_connection: AsyncMock) -> None:
    """cat_file detects when file was truncated at max_size."""
    # Create content that equals max_size (10 bytes)
    max_size = 10
    full_content = "x" * max_size

    mock_connection.run.return_value = MagicMock(stdout=full_content, returncode=0)

    content, was_truncated = await cat_file(
        mock_connection, "/var/log/huge.log", max_size=max_size
    )

    assert content == full_content
    assert was_truncated is True


@pytest.mark.asyncio
async def test_cat_file_no_truncation_when_smaller(mock_connection: AsyncMock) -> None:
    """cat_file returns False when file is smaller than max_size."""
    max_size = 100
    small_content = "small file"

    mock_connection.run.return_value = MagicMock(stdout=small_content, returncode=0)

    content, was_truncated = await cat_file(
        mock_connection, "/etc/hosts", max_size=max_size
    )

    assert content == small_content
    assert was_truncated is False


@pytest.mark.asyncio
async def test_ls_dir_returns_listing(mock_connection: AsyncMock) -> None:
    """ls_dir returns directory listing."""
    mock_connection.run.return_value = MagicMock(
        stdout="file1.txt\nfile2.txt\nsubdir/", returncode=0
    )

    result = await ls_dir(mock_connection, "/home/user")

    assert "file1.txt" in result


@pytest.mark.asyncio
async def test_run_command_returns_output(mock_connection: AsyncMock) -> None:
    """run_command executes arbitrary command."""
    mock_connection.run.return_value = MagicMock(
        stdout="search results", stderr="", returncode=0
    )

    result = await run_command(mock_connection, "/home/user", "rg 'TODO'", timeout=30)

    assert result.output == "search results"
    assert result.returncode == 0


@pytest.mark.asyncio
async def test_run_command_includes_stderr(mock_connection: AsyncMock) -> None:
    """run_command includes stderr in result."""
    mock_connection.run.return_value = MagicMock(
        stdout="", stderr="error message", returncode=1
    )

    result = await run_command(
        mock_connection, "/home/user", "failing-command", timeout=30
    )

    assert result.error == "error message"
    assert result.returncode == 1


@pytest.mark.asyncio
async def test_tree_dir_returns_tree_output(mock_connection: AsyncMock) -> None:
    """tree_dir returns tree output when available."""
    from scout_mcp.services.executors import tree_dir

    mock_connection.run.return_value = MagicMock(
        stdout=".\n├── file1.txt\n└── subdir/", returncode=0
    )

    result = await tree_dir(mock_connection, "/home/user", max_depth=2)

    assert "file1.txt" in result
    assert "subdir" in result


@pytest.mark.asyncio
async def test_tree_dir_falls_back_to_find(mock_connection: AsyncMock) -> None:
    """tree_dir falls back to find when tree unavailable."""
    from scout_mcp.services.executors import tree_dir

    # First call (tree) fails, second call (find) succeeds
    mock_connection.run.side_effect = [
        MagicMock(stdout="", returncode=127),  # tree not found
        MagicMock(stdout="./file1.txt\n./subdir/file2.txt", returncode=0),
    ]

    result = await tree_dir(mock_connection, "/home/user", max_depth=2)

    assert "file1.txt" in result
    assert "file2.txt" in result

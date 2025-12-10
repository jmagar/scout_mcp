"""Tests for SSH command executors."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from scout_mcp.services.executors import (
    broadcast_command,
    broadcast_read,
    cat_file,
    ls_dir,
    run_command,
    stat_path,
)


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
        mock_connection, "/home/user", "grep pattern", timeout=30
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


@pytest.mark.asyncio
async def test_find_files_returns_matches(mock_connection: AsyncMock) -> None:
    """find_files returns matching file paths."""
    from scout_mcp.services.executors import find_files

    mock_connection.run.return_value = MagicMock(
        stdout="/path/file1.py\n/path/subdir/file2.py", returncode=0
    )

    result = await find_files(mock_connection, "/path", "*.py")

    assert "file1.py" in result
    assert "file2.py" in result


@pytest.mark.asyncio
async def test_find_files_respects_depth(mock_connection: AsyncMock) -> None:
    """find_files limits search depth."""
    from scout_mcp.services.executors import find_files

    mock_connection.run.return_value = MagicMock(stdout="", returncode=0)

    await find_files(mock_connection, "/path", "*.py", max_depth=2)

    call_args = mock_connection.run.call_args[0][0]
    assert "-maxdepth 2" in call_args


@pytest.mark.asyncio
async def test_find_files_empty_results(mock_connection: AsyncMock) -> None:
    """find_files returns empty string when no matches."""
    from scout_mcp.services.executors import find_files

    mock_connection.run.return_value = MagicMock(stdout="", returncode=0)

    result = await find_files(mock_connection, "/path", "*.nonexistent")

    assert result == ""


@pytest.mark.asyncio
async def test_find_files_with_file_type_filter(mock_connection: AsyncMock) -> None:
    """find_files filters by file type when specified."""
    from scout_mcp.services.executors import find_files

    mock_connection.run.return_value = MagicMock(
        stdout="/path/dir1\n/path/dir2", returncode=0
    )

    result = await find_files(mock_connection, "/path", "*", file_type="d")

    call_args = mock_connection.run.call_args[0][0]
    assert "-type" in call_args
    assert result == "/path/dir1\n/path/dir2"


@pytest.mark.asyncio
async def test_find_files_respects_max_results(mock_connection: AsyncMock) -> None:
    """find_files limits number of results returned."""
    from scout_mcp.services.executors import find_files

    mock_connection.run.return_value = MagicMock(stdout="results", returncode=0)

    await find_files(mock_connection, "/path", "*.py", max_results=50)

    call_args = mock_connection.run.call_args[0][0]
    assert "head -50" in call_args


@pytest.mark.asyncio
async def test_diff_files_identical(mock_connection: AsyncMock) -> None:
    """diff_files returns empty diff for identical files."""
    from scout_mcp.services.executors import diff_files

    mock_connection.run.return_value = MagicMock(stdout="same content", returncode=0)

    diff_output, identical = await diff_files(
        mock_connection,
        "/path1",
        mock_connection,
        "/path2",
    )

    assert identical is True
    assert diff_output == ""


@pytest.mark.asyncio
async def test_diff_files_different() -> None:
    """diff_files returns unified diff for different files."""
    from scout_mcp.services.executors import diff_files

    conn1, conn2 = AsyncMock(), AsyncMock()
    conn1.run.return_value = MagicMock(stdout="line1\nline2", returncode=0)
    conn2.run.return_value = MagicMock(stdout="line1\nline3", returncode=0)

    diff_output, identical = await diff_files(
        conn1,
        "/path1",
        conn2,
        "/path2",
    )

    assert identical is False
    assert "-line2" in diff_output
    assert "+line3" in diff_output
    assert "---" in diff_output  # Check for diff header
    assert "+++" in diff_output  # Check for diff header


@pytest.mark.asyncio
async def test_diff_with_content_matches(mock_connection: AsyncMock) -> None:
    """diff_with_content detects matching content."""
    from scout_mcp.services.executors import diff_with_content

    mock_connection.run.return_value = MagicMock(stdout="expected", returncode=0)

    diff_output, identical = await diff_with_content(
        mock_connection, "/path", "expected"
    )

    assert identical is True
    assert diff_output == ""


@pytest.mark.asyncio
async def test_diff_with_content_not_matching(mock_connection: AsyncMock) -> None:
    """diff_with_content returns diff when content doesn't match."""
    from scout_mcp.services.executors import diff_with_content

    mock_connection.run.return_value = MagicMock(stdout="actual content", returncode=0)

    diff_output, identical = await diff_with_content(
        mock_connection, "/path", "expected content"
    )

    assert identical is False
    assert diff_output != ""
    assert "-expected content" in diff_output
    assert "+actual content" in diff_output


@pytest.mark.asyncio
async def test_broadcast_read_multiple_hosts() -> None:
    """broadcast_read fetches from multiple hosts concurrently."""
    # Setup mock pool and config
    mock_pool = AsyncMock()
    mock_config = MagicMock()

    # Mock connections for two hosts
    conn1, conn2 = AsyncMock(), AsyncMock()

    # Host 1: file
    conn1.run.side_effect = [
        MagicMock(stdout="regular file", returncode=0),  # stat_path
        MagicMock(stdout="content1", returncode=0),  # cat_file
    ]

    # Host 2: directory
    conn2.run.side_effect = [
        MagicMock(stdout="directory", returncode=0),  # stat_path
        MagicMock(stdout="drwxr-xr-x 2 root root", returncode=0),  # ls_dir
    ]

    mock_pool.get_connection.side_effect = [conn1, conn2]
    mock_config.get_host.return_value = MagicMock()

    results = await broadcast_read(
        mock_pool,
        mock_config,
        [("host1", "/path1"), ("host2", "/path2")],
        max_file_size=1024,
    )

    assert len(results) == 2
    assert results[0].success
    assert results[0].host == "host1"
    assert results[0].path == "/path1"
    assert "content1" in results[0].output

    assert results[1].success
    assert results[1].host == "host2"
    assert results[1].path == "/path2"
    assert "drwxr-xr-x" in results[1].output


@pytest.mark.asyncio
async def test_broadcast_read_handles_partial_failure() -> None:
    """broadcast_read returns results even when some hosts fail."""
    mock_pool = AsyncMock()
    mock_config = MagicMock()

    # First host succeeds
    conn1 = AsyncMock()
    conn1.run.side_effect = [
        MagicMock(stdout="regular file", returncode=0),  # stat_path
        MagicMock(stdout="content", returncode=0),  # cat_file
    ]

    # Second host fails - use an async mock that raises
    async def get_connection_side_effect(ssh_host):
        if ssh_host == mock_config.get_host.return_value:
            # First call returns conn1
            if not hasattr(get_connection_side_effect, "called"):
                get_connection_side_effect.called = True
                return conn1
            # Second call raises
            raise ConnectionError("Connection failed")

    mock_pool.get_connection.side_effect = get_connection_side_effect
    mock_config.get_host.return_value = MagicMock()

    results = await broadcast_read(
        mock_pool,
        mock_config,
        [("host1", "/path1"), ("host2", "/path2")],
        max_file_size=1024,
    )

    assert len(results) == 2
    assert results[0].success
    assert results[0].output == "content"

    assert not results[1].success
    assert "Connection failed" in results[1].error


@pytest.mark.asyncio
async def test_broadcast_read_unknown_host() -> None:
    """broadcast_read handles unknown hosts gracefully."""
    mock_pool = AsyncMock()
    mock_config = MagicMock()

    # Host lookup returns None (unknown host)
    mock_config.get_host.return_value = None

    results = await broadcast_read(
        mock_pool,
        mock_config,
        [("unknown_host", "/path")],
        max_file_size=1024,
    )

    assert len(results) == 1
    assert not results[0].success
    assert "Unknown host: unknown_host" in results[0].error


@pytest.mark.asyncio
async def test_broadcast_command_multiple_hosts() -> None:
    """broadcast_command executes on multiple hosts concurrently."""
    mock_pool = AsyncMock()
    mock_config = MagicMock()

    # Mock connections for two hosts
    conn1, conn2 = AsyncMock(), AsyncMock()

    # Host 1: successful command
    conn1.run.return_value = MagicMock(stdout="output1", stderr="", returncode=0)

    # Host 2: successful command with stderr
    conn2.run.return_value = MagicMock(stdout="output2", stderr="warning", returncode=0)

    mock_pool.get_connection.side_effect = [conn1, conn2]
    mock_config.get_host.return_value = MagicMock()

    results = await broadcast_command(
        mock_pool,
        mock_config,
        [("host1", "/path1"), ("host2", "/path2")],
        command="ls -la",
        timeout=30,
    )

    assert len(results) == 2

    assert results[0].success
    assert results[0].host == "host1"
    assert "output1" in results[0].output

    assert results[1].success
    assert results[1].host == "host2"
    assert "output2" in results[1].output
    assert "warning" in results[1].output


@pytest.mark.asyncio
async def test_broadcast_command_handles_failures() -> None:
    """broadcast_command handles command failures gracefully."""
    mock_pool = AsyncMock()
    mock_config = MagicMock()

    # Mock connection with failed command
    conn = AsyncMock()
    conn.run.return_value = MagicMock(
        stdout="", stderr="command not found", returncode=127
    )

    mock_pool.get_connection.return_value = conn
    mock_config.get_host.return_value = MagicMock()

    results = await broadcast_command(
        mock_pool,
        mock_config,
        [("host1", "/path")],
        command="grep pattern",
        timeout=30,
    )

    assert len(results) == 1
    assert not results[0].success
    assert "127" in results[0].error
    assert "command not found" in results[0].output


@pytest.mark.asyncio
async def test_broadcast_command_connection_error() -> None:
    """broadcast_command handles connection errors."""
    mock_pool = AsyncMock()
    mock_config = MagicMock()

    # Connection fails
    async def raise_error(*args, **kwargs):
        raise ConnectionError("SSH connection failed")

    mock_pool.get_connection.side_effect = raise_error
    mock_config.get_host.return_value = MagicMock()

    results = await broadcast_command(
        mock_pool,
        mock_config,
        [("host1", "/path")],
        command="ls",
        timeout=30,
    )

    assert len(results) == 1
    assert not results[0].success
    assert "SSH connection failed" in results[0].error


@pytest.mark.asyncio
async def test_beam_transfer_local_to_remote(mock_connection: AsyncMock) -> None:
    """Test transferring file from local to remote."""
    import tempfile
    from pathlib import Path
    from unittest.mock import MagicMock

    from scout_mcp.services.executors import beam_transfer

    # Create temp local file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("test content\n")
        local_path = f.name

    try:
        remote_path = "/tmp/test_beam_target.txt"

        # Mock SFTP client - use MagicMock for sync context manager protocol
        mock_sftp = MagicMock()
        mock_sftp.put = AsyncMock()

        # Mock start_sftp_client to return an async context manager
        # Use MagicMock instead of AsyncMock so it's not a coroutine
        mock_sftp_context = MagicMock()
        mock_sftp_context.__aenter__ = AsyncMock(return_value=mock_sftp)
        mock_sftp_context.__aexit__ = AsyncMock(return_value=None)
        mock_connection.start_sftp_client = MagicMock(return_value=mock_sftp_context)

        result = await beam_transfer(
            mock_connection,
            source=local_path,
            destination=remote_path,
            direction="upload",
        )

        assert result.success is True
        assert "uploaded" in result.message.lower()
        mock_sftp.put.assert_called_once()
    finally:
        Path(local_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_beam_transfer_remote_to_local(mock_connection: AsyncMock) -> None:
    """Test transferring file from remote to local."""
    import tempfile
    from pathlib import Path
    from unittest.mock import MagicMock

    from scout_mcp.services.executors import beam_transfer

    with tempfile.TemporaryDirectory() as tmpdir:
        remote_path = "/etc/hostname"
        local_path = f"{tmpdir}/hostname"

        # Mock SFTP client - use MagicMock for sync context manager protocol
        mock_sftp = MagicMock()

        # Mock the get method to actually create the file
        async def mock_get(source, dest):
            Path(dest).write_text("test hostname\n")

        mock_sftp.get = AsyncMock(side_effect=mock_get)

        # Mock start_sftp_client to return an async context manager
        # Use MagicMock instead of AsyncMock so it's not a coroutine
        mock_sftp_context = MagicMock()
        mock_sftp_context.__aenter__ = AsyncMock(return_value=mock_sftp)
        mock_sftp_context.__aexit__ = AsyncMock(return_value=None)
        mock_connection.start_sftp_client = MagicMock(return_value=mock_sftp_context)

        result = await beam_transfer(
            mock_connection,
            source=remote_path,
            destination=local_path,
            direction="download",
        )

        assert result.success is True
        assert "downloaded" in result.message.lower()
        mock_sftp.get.assert_called_once()


@pytest.mark.asyncio
async def test_beam_transfer_invalid_direction(mock_connection: AsyncMock) -> None:
    """Test that invalid direction raises error."""
    from scout_mcp.services.executors import beam_transfer

    with pytest.raises(ValueError, match="direction must be"):
        await beam_transfer(
            mock_connection,
            source="/tmp/source",
            destination="/tmp/dest",
            direction="invalid",
        )


@pytest.mark.asyncio
async def test_beam_transfer_remote_to_remote_success(tmp_path):
    """Test successful remote-to-remote transfer with streaming."""
    from scout_mcp.services.executors import beam_transfer_remote_to_remote

    source_conn = AsyncMock()
    target_conn = AsyncMock()

    # Mock SFTP clients
    source_sftp = AsyncMock()
    target_sftp = AsyncMock()

    source_conn.start_sftp_client.return_value.__aenter__.return_value = source_sftp
    target_conn.start_sftp_client.return_value.__aenter__.return_value = target_sftp

    # Mock file attributes
    mock_attrs = AsyncMock()
    mock_attrs.size = 1024
    source_sftp.stat.return_value = mock_attrs

    # Mock file handles for streaming
    source_file = AsyncMock()
    target_file = AsyncMock()

    # Simulate reading chunks
    chunk_data = b"test data chunk"
    source_file.read.side_effect = [chunk_data, b""]  # First chunk, then EOF

    source_sftp.open.return_value.__aenter__.return_value = source_file
    target_sftp.open.return_value.__aenter__.return_value = target_file

    # Execute transfer
    result = await beam_transfer_remote_to_remote(
        source_conn,
        target_conn,
        "/remote/source.txt",
        "/remote/target.txt",
    )

    # Verify success
    assert result.success is True
    assert "Streamed" in result.message
    assert result.bytes_transferred == len(chunk_data)

    # Verify streaming calls
    source_sftp.stat.assert_called_once_with("/remote/source.txt")
    source_sftp.open.assert_called_once_with("/remote/source.txt", 'rb')
    target_sftp.open.assert_called_once_with("/remote/target.txt", 'wb')

    # Verify data was written
    assert target_file.write.call_count == 1
    target_file.write.assert_called_with(chunk_data)


@pytest.mark.asyncio
async def test_beam_transfer_remote_to_remote_source_not_found():
    """Test remote-to-remote transfer with source file not found."""
    from scout_mcp.services.executors import beam_transfer_remote_to_remote

    source_conn = AsyncMock()
    target_conn = AsyncMock()

    source_sftp = AsyncMock()
    target_sftp = AsyncMock()

    source_conn.start_sftp_client.return_value.__aenter__.return_value = source_sftp
    target_conn.start_sftp_client.return_value.__aenter__.return_value = target_sftp

    # Simulate source file not found
    source_sftp.stat.side_effect = Exception("No such file")

    result = await beam_transfer_remote_to_remote(
        source_conn,
        target_conn,
        "/remote/missing.txt",
        "/remote/target.txt",
    )

    assert result.success is False
    assert "Source file not found" in result.message
    assert result.bytes_transferred == 0


@pytest.mark.asyncio
async def test_beam_transfer_remote_to_remote_upload_fails(tmp_path):
    """Test remote-to-remote transfer with write failure."""
    from scout_mcp.services.executors import beam_transfer_remote_to_remote

    source_conn = AsyncMock()
    target_conn = AsyncMock()

    source_sftp = AsyncMock()
    target_sftp = AsyncMock()

    source_conn.start_sftp_client.return_value.__aenter__.return_value = source_sftp
    target_conn.start_sftp_client.return_value.__aenter__.return_value = target_sftp

    # Mock file attributes
    mock_attrs = AsyncMock()
    mock_attrs.size = 1024
    source_sftp.stat.return_value = mock_attrs

    # Mock file handles
    source_file = AsyncMock()
    target_file = AsyncMock()

    chunk_data = b"test data"
    source_file.read.side_effect = [chunk_data, b""]

    # Simulate write failure
    target_file.write.side_effect = Exception("Permission denied")

    source_sftp.open.return_value.__aenter__.return_value = source_file
    target_sftp.open.return_value.__aenter__.return_value = target_file

    result = await beam_transfer_remote_to_remote(
        source_conn,
        target_conn,
        "/remote/source.txt",
        "/remote/target.txt",
    )

    assert result.success is False
    assert "Transfer failed" in result.message

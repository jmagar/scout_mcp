"""End-to-end integration tests for Scout MCP workflows."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from scout_mcp.tools import scout
from scout_mcp.services import reset_state, set_config
from scout_mcp.config import Config


@pytest.fixture(autouse=True)
def reset_globals() -> None:
    """Reset global state before each test."""
    reset_state()


@pytest.fixture
def mock_ssh_config(tmp_path: Path) -> Path:
    """Create a temporary SSH config with test hosts."""
    config_file = tmp_path / "ssh_config"
    config_file.write_text("""
Host testhost
    HostName 192.168.1.100
    User testuser
    Port 22

Host remotehost
    HostName 192.168.1.200
    User remoteuser
    Port 22
""")
    return config_file


@pytest.mark.asyncio
async def test_full_scout_workflow_list_hosts_to_read_file(
    mock_ssh_config: Path,
) -> None:
    """Complete workflow: list hosts -> read file from host.

    Tests the full user journey:
    1. User calls scout('hosts') to see available hosts
    2. User calls scout('testhost:/etc/hostname') to read a file
    3. Both operations succeed without errors
    """
    set_config(Config(ssh_config_path=mock_ssh_config))

    # Step 1: List hosts
    hosts_result = await scout("hosts")
    assert "testhost" in hosts_result
    assert "remotehost" in hosts_result

    # Step 2: Mock SSH connection for file read
    mock_conn = AsyncMock()
    mock_conn.is_closed = False
    mock_conn.run.side_effect = [
        MagicMock(stdout="regular file", returncode=0),  # stat
        MagicMock(stdout="test-hostname\n", returncode=0),  # cat
    ]

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        # Step 3: Read file from host
        file_result = await scout("testhost:/etc/hostname")
        assert "test-hostname" in file_result

        # Verify connection was made
        assert mock_conn.run.call_count == 2  # stat + cat


@pytest.mark.asyncio
async def test_full_scout_workflow_with_command_execution(
    mock_ssh_config: Path,
) -> None:
    """Complete workflow: list hosts -> execute command on host.

    Tests the full user journey:
    1. User calls scout('hosts') to see available hosts
    2. User calls scout('testhost:/var/log', 'grep ERROR') to run command
    3. Command executes and returns results
    """
    set_config(Config(ssh_config_path=mock_ssh_config))

    # Step 1: List hosts
    hosts_result = await scout("hosts")
    assert "testhost" in hosts_result

    # Step 2: Mock SSH connection for command execution
    mock_conn = AsyncMock()
    mock_conn.is_closed = False
    mock_conn.run.return_value = MagicMock(
        stdout="ERROR: Connection failed\nERROR: Timeout\n",
        stderr="",
        returncode=0,
    )

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        # Step 3: Execute command
        cmd_result = await scout("testhost:/var/log", "grep ERROR")
        assert "ERROR: Connection failed" in cmd_result
        assert "ERROR: Timeout" in cmd_result


@pytest.mark.asyncio
async def test_error_recovery_workflow(mock_ssh_config: Path) -> None:
    """Workflow handles errors gracefully and recovers.

    Tests error handling:
    1. First request fails with connection error
    2. Second request succeeds (connection retry)
    """
    set_config(Config(ssh_config_path=mock_ssh_config))

    # Step 1: Mock connection failure
    with patch(
        "asyncssh.connect",
        new_callable=AsyncMock,
        side_effect=ConnectionError("Connection refused"),
    ):
        error_result = await scout("testhost:/etc/hostname")
        assert "error" in error_result.lower() or "failed" in error_result.lower()

    # Step 2: Mock successful retry
    mock_conn = AsyncMock()
    mock_conn.is_closed = False
    mock_conn.run.side_effect = [
        MagicMock(stdout="regular file", returncode=0),  # stat
        MagicMock(stdout="test-hostname\n", returncode=0),  # cat
    ]

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        success_result = await scout("testhost:/etc/hostname")
        assert "test-hostname" in success_result


@pytest.mark.asyncio
async def test_workflow_list_directory_then_read_file(
    mock_ssh_config: Path,
) -> None:
    """Complete workflow: list directory -> read specific file.

    Tests the full user journey:
    1. User lists directory to see available files
    2. User reads a specific file from that directory
    """
    from scout_mcp.services import get_pool

    set_config(Config(ssh_config_path=mock_ssh_config))

    # Step 1: List directory
    mock_conn = AsyncMock()
    mock_conn.is_closed = False
    mock_conn.run.side_effect = [
        MagicMock(stdout="directory", returncode=0),  # stat
        MagicMock(stdout="-rw-r--r-- 1 root root 100 hostname\n-rw-r--r-- 1 root root 200 hosts", returncode=0),  # ls
    ]

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        dir_result = await scout("testhost:/etc")
        assert "hostname" in dir_result
        assert "hosts" in dir_result

    # Clear pool before second operation
    pool = get_pool()
    await pool.remove_connection("testhost")

    # Step 2: Read specific file from directory
    mock_conn2 = AsyncMock()
    mock_conn2.is_closed = False
    mock_conn2.run.side_effect = [
        MagicMock(stdout="regular file", returncode=0),  # stat
        MagicMock(stdout="127.0.0.1 localhost\n", returncode=0),  # cat
    ]

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn2

        file_result = await scout("testhost:/etc/hosts")
        assert "127.0.0.1" in file_result
        assert "localhost" in file_result


@pytest.mark.asyncio
async def test_workflow_find_files_then_read(mock_ssh_config: Path) -> None:
    """Complete workflow: find files -> read found file.

    Tests the full user journey:
    1. User searches for files matching pattern
    2. User reads one of the found files
    """
    from scout_mcp.services import get_pool

    set_config(Config(ssh_config_path=mock_ssh_config))

    # Step 1: Find files
    mock_conn = AsyncMock()
    mock_conn.is_closed = False
    mock_conn.run.return_value = MagicMock(
        stdout="/var/log/syslog\n/var/log/auth.log\n",
        returncode=0,
    )

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        find_result = await scout("testhost:/var/log", find="*.log")
        assert "syslog" in find_result
        assert "auth.log" in find_result

    # Clear pool before second operation
    pool = get_pool()
    await pool.remove_connection("testhost")

    # Step 2: Read one of the found files
    mock_conn2 = AsyncMock()
    mock_conn2.is_closed = False
    mock_conn2.run.side_effect = [
        MagicMock(stdout="regular file", returncode=0),  # stat
        MagicMock(stdout="Dec 10 10:00:00 host syslog: message\n", returncode=0),  # cat
    ]

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn2

        file_result = await scout("testhost:/var/log/syslog")
        assert "syslog: message" in file_result


@pytest.mark.asyncio
async def test_workflow_multiple_hosts(mock_ssh_config: Path) -> None:
    """Complete workflow: operations on multiple hosts.

    Tests the full user journey:
    1. List hosts to see available servers
    2. Read file from first host
    3. Read file from second host
    """
    set_config(Config(ssh_config_path=mock_ssh_config))

    # Step 1: List hosts
    hosts_result = await scout("hosts")
    assert "testhost" in hosts_result
    assert "remotehost" in hosts_result

    # Step 2: Read from first host
    mock_conn1 = AsyncMock()
    mock_conn1.is_closed = False
    mock_conn1.run.side_effect = [
        MagicMock(stdout="regular file", returncode=0),  # stat
        MagicMock(stdout="testhost-data\n", returncode=0),  # cat
    ]

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn1

        result1 = await scout("testhost:/data/file.txt")
        assert "testhost-data" in result1

    # Step 3: Read from second host
    mock_conn2 = AsyncMock()
    mock_conn2.is_closed = False
    mock_conn2.run.side_effect = [
        MagicMock(stdout="regular file", returncode=0),  # stat
        MagicMock(stdout="remotehost-data\n", returncode=0),  # cat
    ]

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn2

        result2 = await scout("remotehost:/data/file.txt")
        assert "remotehost-data" in result2


@pytest.mark.asyncio
async def test_workflow_tree_view_then_navigate(mock_ssh_config: Path) -> None:
    """Complete workflow: tree view -> navigate to subdirectory.

    Tests the full user journey:
    1. View directory tree structure
    2. Navigate to specific subdirectory
    """
    from scout_mcp.services import get_pool

    set_config(Config(ssh_config_path=mock_ssh_config))

    # Step 1: View tree structure
    mock_conn = AsyncMock()
    mock_conn.is_closed = False
    mock_conn.run.return_value = MagicMock(
        stdout="/etc\n/etc/nginx\n/etc/nginx/sites-available\n",
        returncode=0,
    )

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        tree_result = await scout("testhost:/etc", tree=True)
        assert "nginx" in tree_result
        assert "sites-available" in tree_result

    # Clear pool before second operation
    pool = get_pool()
    await pool.remove_connection("testhost")

    # Step 2: Navigate to subdirectory
    mock_conn2 = AsyncMock()
    mock_conn2.is_closed = False
    mock_conn2.run.side_effect = [
        MagicMock(stdout="directory", returncode=0),  # stat
        MagicMock(stdout="-rw-r--r-- 1 root root 100 default\n", returncode=0),  # ls
    ]

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn2

        subdir_result = await scout("testhost:/etc/nginx/sites-available")
        assert "default" in subdir_result


@pytest.mark.asyncio
async def test_workflow_invalid_operations_with_recovery(
    mock_ssh_config: Path,
) -> None:
    """Workflow handles invalid operations and recovers.

    Tests error handling:
    1. Invalid target format (no colon)
    2. Unknown host
    3. Valid operation after errors
    """
    set_config(Config(ssh_config_path=mock_ssh_config))

    # Step 1: Invalid target format
    result1 = await scout("invalid-target")
    assert "error" in result1.lower() or "invalid" in result1.lower()

    # Step 2: Unknown host
    result2 = await scout("unknownhost:/path")
    assert "error" in result2.lower() or "unknown" in result2.lower()

    # Step 3: Valid operation after errors
    hosts_result = await scout("hosts")
    assert "testhost" in hosts_result
    assert "remotehost" in hosts_result


@pytest.mark.asyncio
async def test_workflow_command_with_different_args(mock_ssh_config: Path) -> None:
    """Complete workflow: execute different commands on same path.

    Tests the full user journey:
    1. Run grep command on logs
    2. Run tail command on same logs
    3. Run wc command on same logs
    """
    from scout_mcp.services import get_pool

    set_config(Config(ssh_config_path=mock_ssh_config))

    # Step 1: grep command
    mock_conn = AsyncMock()
    mock_conn.is_closed = False
    mock_conn.run.return_value = MagicMock(
        stdout="ERROR: test error\n",
        stderr="",
        returncode=0,
    )

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        grep_result = await scout("testhost:/var/log", "grep ERROR")
        assert "ERROR" in grep_result

    # Clear pool before second operation
    pool = get_pool()
    await pool.remove_connection("testhost")

    # Step 2: tail command
    mock_conn2 = AsyncMock()
    mock_conn2.is_closed = False
    mock_conn2.run.return_value = MagicMock(
        stdout="Last line of log\n",
        stderr="",
        returncode=0,
    )

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn2

        tail_result = await scout("testhost:/var/log", "tail -n 1")
        assert "Last line" in tail_result

    # Clear pool before third operation
    await pool.remove_connection("testhost")

    # Step 3: wc command
    mock_conn3 = AsyncMock()
    mock_conn3.is_closed = False
    mock_conn3.run.return_value = MagicMock(
        stdout="100 500 5000\n",
        stderr="",
        returncode=0,
    )

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn3

        wc_result = await scout("testhost:/var/log", "wc")
        assert "100" in wc_result

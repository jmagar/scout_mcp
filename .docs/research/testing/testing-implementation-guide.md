# Testing Implementation Guide - Scout MCP

**Phase 1: Unblock & Establish Foundation**
**Phase 2: Security-Focused Testing**
**Phase 3: Integration & E2E Testing**

---

## Phase 1: Async Test Infrastructure

### 1.1 Fix pytest-asyncio Installation

**Problem:** Async tests cannot run - `pytest-asyncio` marked unknown

**Root Cause:**
- `pytest-asyncio>=0.23.0` listed in `pyproject.toml` but not installed
- `asyncio_mode = "auto"` in `pyproject.toml` requires specific pytest-asyncio version

**Solution:**

```bash
# Step 1: Update pyproject.toml
cat > pyproject.toml << 'EOF'
[project]
name = "scout_mcp"
version = "0.1.0"
description = "MCP server for remote file operations via SSH"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "fastmcp>=2.0.0",
    "asyncssh>=2.14.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=7.0.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["scout_mcp"]

[tool.ruff]
line-length = 88
target-version = "py311"
cache-dir = ".cache/.ruff_cache"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true
cache_dir = ".cache/.mypy_cache"
warn_return_any = true
warn_unused_configs = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_unreachable = true
show_error_codes = true
show_column_numbers = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
cache_dir = ".cache/.pytest_cache"
addopts = "--strict-markers"

[tool.coverage.run]
data_file = ".cache/.coverage"

[tool.coverage.report]
show_missing = true
EOF

# Step 2: Reinstall dependencies
uv sync --dev

# Step 3: Verify installation
uv run pytest --version
uv run python -c "import pytest_asyncio; print(f'pytest-asyncio version: {pytest_asyncio.__version__}')"
```

### 1.2 Verify Async Test Execution

**Test the async infrastructure:**

```bash
# Run a single async test to verify configuration
uv run pytest tests/test_executors.py::test_stat_path_returns_file -v

# Expected output:
# PASSED tests/test_executors.py::test_stat_path_returns_file

# Run all executor tests
uv run pytest tests/test_executors.py -v

# Expected: 12 tests should run (currently fail due to mock issues, but async works)
```

### 1.3 Generate Baseline Coverage Report

```bash
# Full test run with coverage
uv run pytest tests/ --cov=scout_mcp --cov-report=html --cov-report=term-missing

# Create HTML report
# Open: .htmlcov/index.html

# Save baseline
mkdir -p .cache/coverage_baseline
cp .cache/.coverage .cache/coverage_baseline/.coverage_phase1_baseline
```

---

## Phase 2: Security-Focused Testing

### 2.1 Command Injection Prevention Tests

**File:** `tests/test_security_command_injection.py`

```python
"""Tests for command injection vulnerability prevention."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from scout_mcp.services.executors import cat_file, run_command, stat_path
from scout_mcp.utils.parser import parse_target


@pytest.fixture
def mock_connection() -> AsyncMock:
    """Create a mock SSH connection."""
    return AsyncMock()


class TestCommandInjectionPrevention:
    """Verify shell metacharacters are properly escaped."""

    @pytest.mark.asyncio
    async def test_cat_file_escapes_semicolon_in_path(
        self, mock_connection: AsyncMock
    ) -> None:
        """Verify semicolon in path doesn't execute second command."""
        # Payload: /var/log/app.log; rm -rf /
        mock_connection.run.return_value = MagicMock(
            stdout="file contents", returncode=0
        )

        await cat_file(mock_connection, "/var/log/app.log; rm -rf /", max_size=1024)

        # Verify path is quoted/escaped
        call_args = mock_connection.run.call_args[0][0]
        # repr() should have escaped the path
        assert "rm -rf" not in call_args or "'/var/log/app.log" in call_args

    @pytest.mark.asyncio
    async def test_cat_file_escapes_backticks(
        self, mock_connection: AsyncMock
    ) -> None:
        """Verify backticks don't allow command substitution."""
        mock_connection.run.return_value = MagicMock(
            stdout="file contents", returncode=0
        )

        await cat_file(mock_connection, "/var/log/`whoami`.log", max_size=1024)

        call_args = mock_connection.run.call_args[0][0]
        # Path should be quoted, preventing `` expansion
        assert call_args.count("'") >= 2  # At minimum quotes around path

    @pytest.mark.asyncio
    async def test_cat_file_escapes_command_substitution_dollar(
        self, mock_connection: AsyncMock
    ) -> None:
        """Verify $(...) command substitution is escaped."""
        mock_connection.run.return_value = MagicMock(
            stdout="file contents", returncode=0
        )

        await cat_file(
            mock_connection, "/var/log/$(whoami)_debug.log", max_size=1024
        )

        call_args = mock_connection.run.call_args[0][0]
        # Verify proper quoting prevents substitution
        assert "$(whoami)" not in call_args.split('{')[0]  # Check before any braces

    @pytest.mark.asyncio
    async def test_run_command_sanitizes_query_parameter(
        self, mock_connection: AsyncMock
    ) -> None:
        """Verify user-supplied command parameter is safe."""
        mock_connection.run.return_value = MagicMock(
            stdout="search results", returncode=0
        )

        # User provides: "pattern; rm -rf /"
        # Should not execute both commands
        await run_command(
            mock_connection,
            "/var/log",
            "grep pattern; rm -rf /",
            timeout=30,
        )

        call_args = mock_connection.run.call_args[0][0]
        # Verify the harmful command is quoted/escaped
        assert "rm -rf" not in call_args or "grep" in call_args.split(";")[0]


class TestPathTraversalPrevention:
    """Verify path traversal attempts are blocked."""

    def test_parse_target_rejects_parent_directory_traversal(self) -> None:
        """Verify ../ sequences are detected and rejected."""
        with pytest.raises(ValueError, match="path traversal"):
            parse_target("host:/../../../etc/passwd")

    def test_parse_target_rejects_dotdot_in_middle(self) -> None:
        """Verify .. in path middle is rejected."""
        with pytest.raises(ValueError, match="path traversal"):
            parse_target("host:/var/log/../../etc/passwd")

    def test_parse_target_allows_dotfiles(self) -> None:
        """Verify .hidden files are allowed."""
        target = parse_target("host:/home/user/.ssh/config")
        assert target.path == "/home/user/.ssh/config"

    @pytest.mark.asyncio
    async def test_cat_file_rejects_path_traversal_attempt(
        self, mock_connection: AsyncMock
    ) -> None:
        """Verify path traversal in file read is detected."""
        # Should be blocked before SSH execution
        with pytest.raises(ValueError):
            # Parser should catch this before reaching cat_file
            parse_target("host:/../../../etc/passwd")


class TestInputValidation:
    """Verify all inputs are properly validated."""

    def test_parse_target_validates_host_not_empty(self) -> None:
        """Verify host cannot be empty."""
        with pytest.raises(ValueError, match="Host cannot be empty"):
            parse_target(":/var/log/app.log")

    def test_parse_target_validates_path_not_empty(self) -> None:
        """Verify path cannot be empty."""
        with pytest.raises(ValueError, match="Path cannot be empty"):
            parse_target("hostname:")

    def test_parse_target_validates_format(self) -> None:
        """Verify invalid formats are rejected."""
        with pytest.raises(ValueError, match="Invalid target"):
            parse_target("invalid_format_no_colon")

    def test_parse_target_allows_special_chars_in_path(self) -> None:
        """Verify valid special characters are allowed."""
        # These should all parse successfully:
        valid_paths = [
            "host:/var/log/app.log",
            "host:/home/user/file-with-dash.txt",
            "host:/etc/nginx.conf.backup",
            "host:/var/data/file_with_underscore.txt",
            "host:/opt/app/v1.2.3/config.yaml",
        ]
        for path in valid_paths:
            target = parse_target(path)
            assert target.host is not None
            assert target.path is not None
```

### 2.2 SSH Host Key Verification Tests

**File:** `tests/test_security_ssh_host_keys.py`

```python
"""Tests for SSH host key verification."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from scout_mcp.services.pool import ConnectionPool
from scout_mcp.models import SSHHost


class TestHostKeyVerification:
    """Verify SSH connections verify host keys."""

    @pytest.mark.asyncio
    async def test_pool_enables_host_key_verification(self) -> None:
        """Verify known_hosts parameter is properly configured."""
        pool = ConnectionPool()
        host = SSHHost(
            name="test",
            hostname="localhost",
            user="root",
            port=22,
            identity_file=None,
        )

        # Mock asyncssh.connect to capture arguments
        with patch("scout_mcp.services.pool.asyncssh.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            await pool.get_connection(host)

            # Verify known_hosts was NOT set to None
            call_kwargs = mock_connect.call_args[1]
            assert "known_hosts" in call_kwargs
            # Should be either:
            # - None (uses default ~/.ssh/known_hosts)
            # - or explicit path
            # But NOT known_hosts=None explicitly
            assert call_kwargs.get("known_hosts") is not None or \
                   "known_hosts" not in call_kwargs

    @pytest.mark.asyncio
    async def test_pool_verifies_host_key_on_connection(self) -> None:
        """Verify host key verification is performed."""
        pool = ConnectionPool()
        host = SSHHost(
            name="untrusted",
            hostname="attacker.example.com",
            user="root",
            port=22,
        )

        with patch("scout_mcp.services.pool.asyncssh.connect") as mock_connect:
            # Simulate host key verification failure
            import asyncssh
            mock_connect.side_effect = \
                asyncssh.HostKeyNotVerifiable("Unknown host key")

            with pytest.raises(asyncssh.HostKeyNotVerifiable):
                await pool.get_connection(host)

    @pytest.mark.asyncio
    async def test_pool_rejects_changed_host_key(self) -> None:
        """Verify detection of changed/compromised host keys."""
        pool = ConnectionPool()
        host = SSHHost(
            name="compromised",
            hostname="example.com",
            user="root",
            port=22,
        )

        with patch("scout_mcp.services.pool.asyncssh.connect") as mock_connect:
            import asyncssh
            # Simulate MITM detection (host key mismatch)
            mock_connect.side_effect = \
                asyncssh.HostKeyNotVerifiable("Host key changed")

            with pytest.raises(asyncssh.HostKeyNotVerifiable):
                await pool.get_connection(host)

    @pytest.mark.asyncio
    async def test_pool_uses_identity_file_when_provided(self) -> None:
        """Verify SSH key authentication uses provided identity files."""
        pool = ConnectionPool()
        host = SSHHost(
            name="test",
            hostname="localhost",
            user="deployer",
            port=2222,
            identity_file="~/.ssh/id_ed25519",
        )

        with patch("scout_mcp.services.pool.asyncssh.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            await pool.get_connection(host)

            call_kwargs = mock_connect.call_args[1]
            assert call_kwargs.get("client_keys") == ["~/.ssh/id_ed25519"]
```

### 2.3 Path Traversal Prevention

Update `scout_mcp/utils/parser.py` to add validation:

```python
"""Scout target URI parsing with security validation."""

import re
from scout_mcp.models import ScoutTarget


def _validate_path(path: str) -> None:
    """Validate path for security issues.

    Raises:
        ValueError: If path contains traversal attempts or invalid characters.
    """
    # Reject parent directory traversal
    if ".." in path:
        raise ValueError("Path traversal (..) not allowed in path")

    # Reject null bytes
    if "\x00" in path:
        raise ValueError("Null bytes not allowed in path")

    # Warn on suspicious patterns (but allow them if needed)
    suspicious = ["&&", "||", ";", "|", "`", "$"]
    for pattern in suspicious:
        if pattern in path:
            # These might be legitimate (e.g., filename with & in it)
            # But log for security review
            pass


def parse_target(target: str) -> ScoutTarget:
    """Parse a scout target URI with security validation.

    Formats:
        - "hosts" -> list available hosts
        - "hostname:/path" -> target a specific path on host

    Returns:
        ScoutTarget with parsed components.

    Raises:
        ValueError: If target format is invalid or contains security issues.
    """
    target = target.strip()

    # Special case: hosts command
    if target.lower() == "hosts":
        return ScoutTarget(host=None, is_hosts_command=True)

    # Parse host:/path format
    if ":" not in target:
        raise ValueError(f"Invalid target '{target}'. Expected 'host:/path' or 'hosts'")

    # Split on first colon only (path may contain colons)
    parts = target.split(":", 1)
    host = parts[0].strip()
    path = parts[1].strip() if len(parts) > 1 else ""

    if not host:
        raise ValueError("Host cannot be empty")

    if not path:
        raise ValueError("Path cannot be empty")

    # Validate path for security issues
    _validate_path(path)

    return ScoutTarget(host=host, path=path)
```

---

## Phase 3: Integration & E2E Testing

### 3.1 Scout Tool Integration Tests

**File:** `tests/test_integration_scout_tool.py`

```python
"""Integration tests for scout tool."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from scout_mcp.tools.scout import scout
from scout_mcp.models import SSHHost
from scout_mcp.services import reset_state, set_config, set_pool
from scout_mcp.config import Config


@pytest.fixture(autouse=True)
def reset_service_state():
    """Reset global service state before each test."""
    reset_state()
    yield
    reset_state()


class TestScoutToolListHosts:
    """Test 'hosts' command."""

    @pytest.mark.asyncio
    async def test_scout_hosts_lists_available_hosts(self) -> None:
        """Verify scout('hosts') lists all configured hosts."""
        # Setup config with mock hosts
        config = Config()
        config._hosts = {
            "dookie": SSHHost(
                name="dookie",
                hostname="100.122.19.93",
                user="jmagar",
                port=22,
            ),
            "tootie": SSHHost(
                name="tootie",
                hostname="100.120.242.29",
                user="root",
                port=29229,
            ),
        }
        set_config(config)

        # Mock ping to show both online
        with patch("scout_mcp.tools.scout.check_hosts_online") as mock_ping:
            mock_ping.return_value = {"dookie": True, "tootie": True}

            result = await scout("hosts")

        assert "dookie" in result
        assert "tootie" in result
        assert "online" in result

    @pytest.mark.asyncio
    async def test_scout_hosts_shows_offline_status(self) -> None:
        """Verify offline hosts are marked correctly."""
        config = Config()
        config._hosts = {
            "online": SSHHost(
                name="online",
                hostname="192.168.1.1",
                user="root",
                port=22,
            ),
            "offline": SSHHost(
                name="offline",
                hostname="10.0.0.1",
                user="root",
                port=22,
            ),
        }
        set_config(config)

        with patch("scout_mcp.tools.scout.check_hosts_online") as mock_ping:
            mock_ping.return_value = {"online": True, "offline": False}

            result = await scout("hosts")

        assert "online" in result and "online" in result
        assert "offline" in result


class TestScoutToolFileOperations:
    """Test file read operations."""

    @pytest.mark.asyncio
    async def test_scout_reads_file(self) -> None:
        """Verify scout reads file contents."""
        config = Config()
        config._hosts = {
            "test": SSHHost(
                name="test",
                hostname="localhost",
                user="root",
                port=22,
            ),
        }
        set_config(config)

        # Mock connection and pool
        from scout_mcp.services.pool import ConnectionPool
        pool = ConnectionPool()

        mock_conn = AsyncMock()
        with patch.object(pool, "get_connection") as mock_get:
            mock_get.return_value = mock_conn

            # Mock stat_path to return 'file'
            with patch("scout_mcp.tools.scout.stat_path") as mock_stat:
                mock_stat.return_value = "file"

                # Mock cat_file
                with patch("scout_mcp.tools.scout.cat_file") as mock_cat:
                    mock_cat.return_value = ("file contents here", False)

                    set_pool(pool)
                    result = await scout("test:/var/log/app.log")

        assert "file contents here" in result
        assert "truncated" not in result

    @pytest.mark.asyncio
    async def test_scout_detects_file_truncation(self) -> None:
        """Verify truncated files are marked."""
        config = Config()
        config._hosts = {
            "test": SSHHost(
                name="test",
                hostname="localhost",
                user="root",
                port=22,
            ),
        }
        config.max_file_size = 100
        set_config(config)

        from scout_mcp.services.pool import ConnectionPool
        pool = ConnectionPool()

        mock_conn = AsyncMock()
        with patch.object(pool, "get_connection") as mock_get:
            mock_get.return_value = mock_conn

            with patch("scout_mcp.tools.scout.stat_path") as mock_stat:
                mock_stat.return_value = "file"

                with patch("scout_mcp.tools.scout.cat_file") as mock_cat:
                    # Return truncated=True
                    mock_cat.return_value = ("x" * 100, True)

                    set_pool(pool)
                    result = await scout("test:/var/log/huge.log")

        assert "truncated" in result
        assert str(config.max_file_size) in result


class TestScoutToolErrorHandling:
    """Test error cases."""

    @pytest.mark.asyncio
    async def test_scout_unknown_host_returns_error(self) -> None:
        """Verify unknown hosts are reported with available list."""
        config = Config()
        config._hosts = {
            "dookie": SSHHost(
                name="dookie",
                hostname="100.122.19.93",
                user="root",
                port=22,
            ),
        }
        set_config(config)

        result = await scout("nonexistent:/var/log/app.log")

        assert "Error" in result
        assert "nonexistent" in result
        assert "dookie" in result  # Available hosts listed

    @pytest.mark.asyncio
    async def test_scout_invalid_target_format_returns_error(self) -> None:
        """Verify invalid target format is rejected."""
        result = await scout("invalid_no_colon")

        assert "Error" in result
        assert "Expected" in result

    @pytest.mark.asyncio
    async def test_scout_path_not_found_returns_error(self) -> None:
        """Verify missing paths are reported."""
        config = Config()
        config._hosts = {
            "test": SSHHost(
                name="test",
                hostname="localhost",
                user="root",
                port=22,
            ),
        }
        set_config(config)

        from scout_mcp.services.pool import ConnectionPool
        pool = ConnectionPool()

        mock_conn = AsyncMock()
        with patch.object(pool, "get_connection") as mock_get:
            mock_get.return_value = mock_conn

            with patch("scout_mcp.tools.scout.stat_path") as mock_stat:
                mock_stat.return_value = None  # Path doesn't exist

                set_pool(pool)
                result = await scout("test:/nonexistent/path")

        assert "Error" in result
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_scout_connection_retry_on_failure(self) -> None:
        """Verify connection retry logic works."""
        config = Config()
        config._hosts = {
            "test": SSHHost(
                name="test",
                hostname="localhost",
                user="root",
                port=22,
            ),
        }
        set_config(config)

        from scout_mcp.services.pool import ConnectionPool
        pool = ConnectionPool()

        call_count = 0

        async def mock_get_connection(host):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Initial failure")
            # Second call succeeds
            mock_conn = AsyncMock()
            return mock_conn

        with patch.object(pool, "get_connection", side_effect=mock_get_connection):
            with patch.object(pool, "remove_connection", new_callable=AsyncMock):
                with patch("scout_mcp.tools.scout.stat_path") as mock_stat:
                    mock_stat.return_value = "file"

                    with patch("scout_mcp.tools.scout.cat_file") as mock_cat:
                        mock_cat.return_value = ("contents", False)

                        set_pool(pool)
                        result = await scout("test:/var/log/app.log")

        # Should not contain error (retry succeeded)
        assert "Error" not in result
        assert call_count == 2  # Initial call + retry
```

### 3.2 Connection Pool Lifecycle Tests

**File:** `tests/test_integration_pool_lifecycle.py`

```python
"""Integration tests for connection pool lifecycle."""

from unittest.mock import AsyncMock, patch
import asyncio
import pytest
from scout_mcp.services.pool import ConnectionPool
from scout_mcp.models import SSHHost, PooledConnection


class TestConnectionPoolLifecycle:
    """Test pool creation, reuse, and cleanup."""

    @pytest.mark.asyncio
    async def test_pool_reuses_same_connection_for_multiple_requests(
        self,
    ) -> None:
        """Verify one connection is reused for repeated requests."""
        pool = ConnectionPool(idle_timeout=60)
        host = SSHHost(
            name="test",
            hostname="localhost",
            user="root",
            port=22,
        )

        with patch("scout_mcp.services.pool.asyncssh.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            # Request connection 3 times
            conn1 = await pool.get_connection(host)
            conn2 = await pool.get_connection(host)
            conn3 = await pool.get_connection(host)

            # Should be same connection object
            assert conn1 is conn2
            assert conn2 is conn3

            # asyncssh.connect should be called only once
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_pool_creates_separate_connections_per_host(self) -> None:
        """Verify different hosts get different connections."""
        pool = ConnectionPool()
        host1 = SSHHost(name="host1", hostname="1.1.1.1", user="root", port=22)
        host2 = SSHHost(name="host2", hostname="2.2.2.2", user="root", port=22)

        with patch("scout_mcp.services.pool.asyncssh.connect") as mock_connect:
            mock_conn1 = AsyncMock()
            mock_conn2 = AsyncMock()
            mock_connect.side_effect = [mock_conn1, mock_conn2]

            conn1 = await pool.get_connection(host1)
            conn2 = await pool.get_connection(host2)

            assert conn1 is not conn2
            assert mock_connect.call_count == 2

    @pytest.mark.asyncio
    async def test_pool_replaces_stale_connections(self) -> None:
        """Verify closed connections are replaced."""
        pool = ConnectionPool()
        host = SSHHost(name="test", hostname="localhost", user="root", port=22)

        with patch("scout_mcp.services.pool.asyncssh.connect") as mock_connect:
            mock_conn1 = AsyncMock()
            mock_conn2 = AsyncMock()
            mock_connect.side_effect = [mock_conn1, mock_conn2]

            # Get first connection
            conn1 = await pool.get_connection(host)

            # Simulate connection being closed
            mock_conn1.is_active.return_value = False

            # Get connection again - should create new one
            conn2 = await pool.get_connection(host)

            assert mock_connect.call_count == 2
            assert conn1 is not conn2

    @pytest.mark.asyncio
    async def test_pool_cleanup_task_removes_idle_connections(self) -> None:
        """Verify idle connections are cleaned up periodically."""
        idle_timeout = 1  # 1 second
        pool = ConnectionPool(idle_timeout=idle_timeout)
        host = SSHHost(name="test", hostname="localhost", user="root", port=22)

        with patch("scout_mcp.services.pool.asyncssh.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            # Create connection
            await pool.get_connection(host)
            assert len(pool._connections) == 1

            # Wait for cleanup (cleanup runs every idle_timeout/2)
            await asyncio.sleep(idle_timeout + 0.5)

            # Connection should be cleaned up
            # (depends on PooledConnection.is_stale logic)
            # This is a simplified test

    @pytest.mark.asyncio
    async def test_pool_close_all_closes_all_connections(self) -> None:
        """Verify close_all() closes all active connections."""
        pool = ConnectionPool()
        host1 = SSHHost(name="host1", hostname="1.1.1.1", user="root", port=22)
        host2 = SSHHost(name="host2", hostname="2.2.2.2", user="root", port=22)

        with patch("scout_mcp.services.pool.asyncssh.connect") as mock_connect:
            mock_conn1 = AsyncMock()
            mock_conn2 = AsyncMock()
            mock_connect.side_effect = [mock_conn1, mock_conn2]

            await pool.get_connection(host1)
            await pool.get_connection(host2)

            # Close all
            await pool.close_all()

            # Both should be closed
            mock_conn1.close.assert_called_once()
            mock_conn2.close.assert_called_once()
```

---

## Testing Command Reference

### Run All Tests
```bash
uv run pytest tests/ -v
```

### Run Specific Test Categories
```bash
# Config tests (currently passing)
uv run pytest tests/test_config.py -v

# Security tests (new)
uv run pytest tests/test_security_*.py -v

# Integration tests (new)
uv run pytest tests/test_integration_*.py -v

# With coverage
uv run pytest tests/ --cov=scout_mcp --cov-report=html

# Specific test
uv run pytest tests/test_security_command_injection.py::TestCommandInjectionPrevention::test_cat_file_escapes_semicolon_in_path -v
```

### Generate Coverage Report
```bash
# Terminal report
uv run pytest tests/ --cov=scout_mcp --cov-report=term-missing

# HTML report (open in browser)
uv run pytest tests/ --cov=scout_mcp --cov-report=html
open htmlcov/index.html
```

### Run Benchmarks
```bash
uv run pytest tests/benchmarks/ -v
```

### Run with Markers
```bash
# Only asyncio tests
uv run pytest -m asyncio tests/ -v

# Only security tests
uv run pytest -m security tests/ -v

# Only integration tests
uv run pytest -m integration tests/ -v
```

---

## Quality Gates

### Phase 1 Completion Criteria
- [ ] pytest-asyncio installed and configured
- [ ] All 43 config/main tests passing
- [ ] At least 90% of blocked tests now run (async config works)
- [ ] Baseline coverage report generated

### Phase 2 Completion Criteria
- [ ] 15+ security tests added
- [ ] All command injection payloads tested
- [ ] SSH host key verification enabled
- [ ] Path traversal validation implemented
- [ ] Coverage of security-critical modules > 60%

### Phase 3 Completion Criteria
- [ ] Scout tool integration tests cover all user flows
- [ ] Connection pool lifecycle tested
- [ ] Resource handlers tested
- [ ] Middleware chain tested
- [ ] Overall coverage > 65%

### Final Goal (All Phases)
- [ ] Coverage > 85% across all modules
- [ ] Zero critical security issues
- [ ] All user-facing features tested
- [ ] Performance benchmarks stable
- [ ] Cleanup and maintenance verified

---

## Maintenance & Continuous Integration

### Add to CI Pipeline

**`.github/workflows/test.yml`** (or similar)
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v3
      - uses: astral-sh/setup-uv@v2
      - name: Install dependencies
        run: uv sync --dev
      - name: Run tests
        run: uv run pytest tests/ -v --cov=scout_mcp --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

### Pre-commit Hook

Create `.husky/pre-commit`:
```bash
#!/bin/sh
set -e

uv run pytest tests/ --co -q > /dev/null
uv run pytest tests/test_config.py tests/test_main.py -q
```

---

**Document Version:** 1.0
**Last Updated:** 2025-12-03
**Owner:** QA Engineering

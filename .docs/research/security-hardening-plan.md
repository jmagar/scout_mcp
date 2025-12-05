# Scout MCP Security Hardening & Refactoring Plan

## Overview

This plan addresses 12 P1 issues for scout_mcp, organized into parallelizable batches for efficient execution using multiple agents.

**Total Estimated Effort:** 40-50 hours
**Execution Strategy:** 4 parallel batches with dependency-aware sequencing

---

## MANDATORY: Test-Driven Development (TDD) Protocol

**ALL implementation tasks MUST follow strict TDD discipline. No exceptions.**

### Red-Green-Refactor Cycle

Every code change follows this exact sequence:

```
┌─────────────────────────────────────────────────────────────┐
│  1. RED: Write a failing test FIRST                         │
│     - Test must fail for the RIGHT reason                   │
│     - Verify test actually runs and fails                   │
│     - Commit: "test: add failing test for X"                │
├─────────────────────────────────────────────────────────────┤
│  2. GREEN: Write MINIMAL code to pass the test              │
│     - Only enough code to make the test pass                │
│     - No extra features, no "while I'm here" changes        │
│     - Commit: "feat: implement X to pass test"              │
├─────────────────────────────────────────────────────────────┤
│  3. REFACTOR: Improve code while keeping tests green        │
│     - Clean up, extract helpers, improve naming             │
│     - Run tests after EVERY change                          │
│     - Commit: "refactor: clean up X implementation"         │
└─────────────────────────────────────────────────────────────┘
```

### TDD Rules for This Plan

1. **No production code without a failing test first**
   - Write the test, see it fail, then implement

2. **Tests define the specification**
   - Each acceptance criterion becomes a test case
   - Edge cases get their own tests

3. **Small cycles**
   - One test at a time
   - Commit after each green state

4. **Verification commands after each step:**
   ```bash
   # After RED (should fail)
   uv run pytest tests/test_<feature>.py -v --tb=short

   # After GREEN (should pass)
   uv run pytest tests/test_<feature>.py -v
   uv run pytest tests/ -v  # Full suite still passes

   # After REFACTOR (still passes)
   uv run pytest tests/ -v
   uv run mypy scout_mcp/
   uv run ruff check scout_mcp/ tests/
   ```

5. **Each agent task includes TDD steps**
   - Step 1: Write failing tests
   - Step 2: Implement to pass tests
   - Step 3: Refactor and verify

### Test Categories Required

| Category | Purpose | Location |
|----------|---------|----------|
| **Unit Tests** | Test individual functions in isolation | `tests/test_<module>.py` |
| **Security Tests** | Verify security controls work | `tests/test_security.py` |
| **Integration Tests** | Test component interactions | `tests/test_integration.py` |
| **Edge Case Tests** | Boundary conditions, error paths | Within relevant test files |

---

## Issue Summary

| ID | Type | Title | Batch | Dependencies |
|----|------|-------|-------|--------------|
| scout_mcp-vn7 | bug | Update asyncssh to fix known CVEs | 1 | None |
| scout_mcp-zge | bug | Fix Command Injection Vulnerability | 1 | None |
| scout_mcp-7di | bug | Enable SSH Host Key Verification | 1 | None |
| scout_mcp-2rf | task | Extract Connection Retry Helper | 2 | None |
| scout_mcp-pya | feature | Add Path Traversal Protection | 2 | None |
| scout_mcp-ydy | task | Split scout() Function into Handlers | 2 | scout_mcp-2rf |
| scout_mcp-y6f | task | Unblock Async Tests (pytest-asyncio) | 2 | None |
| scout_mcp-0wx | feature | Implement API Key Authentication | 3 | None |
| scout_mcp-drx | feature | Add Rate Limiting Middleware | 3 | None |
| scout_mcp-6ce | task | Add Security Warnings to README | 3 | scout_mcp-0wx, scout_mcp-7di |
| scout_mcp-kvk | bug | Fix Global Lock Performance Issue | 4 | scout_mcp-2rf |
| scout_mcp-82l | feature | Add Connection Pool Size Limits | 4 | scout_mcp-kvk |

---

## Batch 1: Critical Security Fixes (Parallel - 3 Agents)

These three issues have NO dependencies and can be executed simultaneously.

### Agent 1: scout_mcp-vn7 - Update asyncssh Version

**File:** `pyproject.toml`
**Effort:** 15 minutes

#### Current State
```python
# pyproject.toml:9
"asyncssh>=2.14.0",  # Allows vulnerable versions
```

#### Implementation

1. **Update dependency constraint:**
```toml
# pyproject.toml
dependencies = [
    "fastmcp>=2.0.0",
    "asyncssh>=2.14.2,<3.0.0",  # Fixed CVEs, bounded upper
]
```

2. **Run dependency update:**
```bash
uv lock --upgrade-package asyncssh
uv sync
```

3. **Verify version:**
```bash
uv run python -c "import asyncssh; print(asyncssh.__version__)"
```

#### Acceptance Criteria
- [ ] asyncssh version is 2.14.2+
- [ ] All existing tests pass
- [ ] uv.lock updated with new version

---

### Agent 2: scout_mcp-zge - Fix Command Injection

**Files:** `scout_mcp/services/executors.py`, `scout_mcp/utils/shell.py` (NEW)
**Effort:** 2 hours

#### Current State (VULNERABLE)
```python
# executors.py:161
full_command = f"cd {working_dir!r} && timeout {timeout} {command}"

# Also at lines: 17, 53, 87, 124, 137, 214, 281, 368, 403, 487, 518, 567
```

The `!r` format spec uses `repr()` which is NOT safe for shell escaping.

---

#### TDD Implementation Steps

##### STEP 1: RED - Write Failing Tests First

Create `tests/test_shell_quoting.py` with tests that will fail (module doesn't exist yet):

```python
# tests/test_shell_quoting.py
"""TDD: Security tests for shell quoting - written BEFORE implementation."""

import pytest
import shlex


class TestQuotePath:
    """Test quote_path function - these tests define the specification."""

    def test_simple_path(self):
        """Simple paths should be quoted."""
        from scout_mcp.utils.shell import quote_path
        result = quote_path("/var/log")
        assert result == "'/var/log'"

    def test_path_with_spaces(self):
        """Paths with spaces must be safely quoted."""
        from scout_mcp.utils.shell import quote_path
        result = quote_path("/var/log/my file.txt")
        assert result == "'/var/log/my file.txt'"

    def test_injection_semicolon(self):
        """Semicolon injection attempts must be neutralized."""
        from scout_mcp.utils.shell import quote_path
        malicious = "/tmp'; rm -rf / #"
        result = quote_path(malicious)
        # Result should be a single quoted string that can't break out
        assert result.startswith("'")
        assert result.endswith("'")
        # When parsed by shell, should be a single argument
        parsed = shlex.split(f"cat {result}")
        assert len(parsed) == 2  # ['cat', '/tmp\'; rm -rf / #']

    def test_injection_backticks(self):
        """Backtick command substitution must be neutralized."""
        from scout_mcp.utils.shell import quote_path
        malicious = "/tmp/`whoami`.txt"
        result = quote_path(malicious)
        assert "`" in result  # Character preserved but quoted
        assert result.startswith("'")

    def test_injection_dollar(self):
        """Dollar sign variable expansion must be neutralized."""
        from scout_mcp.utils.shell import quote_path
        malicious = "/tmp/$HOME/file"
        result = quote_path(malicious)
        assert "$" in result  # Character preserved but quoted
        assert result.startswith("'")

    def test_injection_newline(self):
        """Newline injection must be neutralized."""
        from scout_mcp.utils.shell import quote_path
        malicious = "/tmp/file\nrm -rf /"
        result = quote_path(malicious)
        # shlex.quote handles this with $'...' syntax or escaping
        parsed = shlex.split(f"cat {result}")
        assert len(parsed) == 2  # Still single argument


class TestQuoteArg:
    """Test quote_arg function."""

    def test_simple_arg(self):
        """Simple arguments should be quoted."""
        from scout_mcp.utils.shell import quote_arg
        result = quote_arg("hello")
        assert result == "hello" or result == "'hello'"  # shlex may not quote simple strings

    def test_arg_with_spaces(self):
        """Arguments with spaces must be quoted."""
        from scout_mcp.utils.shell import quote_arg
        result = quote_arg("hello world")
        assert "'" in result or '"' in result

    def test_arg_injection(self):
        """Injection attempts in arguments must be neutralized."""
        from scout_mcp.utils.shell import quote_arg
        malicious = "arg; rm -rf /"
        result = quote_arg(malicious)
        parsed = shlex.split(result)
        assert len(parsed) == 1  # Single argument, not command chain
```

**Run and verify RED:**
```bash
uv run pytest tests/test_shell_quoting.py -v
# Expected: ModuleNotFoundError or ImportError - tests FAIL
```

##### STEP 2: GREEN - Implement Minimal Code to Pass

Create `scout_mcp/utils/shell.py`:
```python
# scout_mcp/utils/shell.py (NEW FILE)
"""Shell command safety utilities."""

import shlex


def quote_path(path: str) -> str:
    """Safely quote a path for shell commands.

    Args:
        path: File system path to quote

    Returns:
        Shell-safe quoted path
    """
    return shlex.quote(path)


def quote_arg(arg: str) -> str:
    """Safely quote a shell argument.

    Args:
        arg: Argument to quote

    Returns:
        Shell-safe quoted argument
    """
    return shlex.quote(arg)
```

**Run and verify GREEN:**
```bash
uv run pytest tests/test_shell_quoting.py -v
# Expected: All tests PASS
```

##### STEP 3: Write Integration Tests (RED again)

Now add tests for the actual executors using shlex.quote:

```python
# tests/test_executors_security.py
"""TDD: Security tests for executors - verify shlex.quote is used."""

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestExecutorsSecurity:
    """Verify executors use safe shell quoting."""

    @pytest.fixture
    def mock_conn(self):
        conn = MagicMock()
        conn.run = AsyncMock(return_value=MagicMock(
            returncode=0,
            stdout="output",
            stderr=""
        ))
        return conn

    async def test_stat_path_quotes_path(self, mock_conn):
        """stat_path should use shlex.quote for path."""
        from scout_mcp.services.executors import stat_path

        # Malicious path that would break out of quotes with repr()
        malicious_path = "/tmp'; rm -rf / #"
        await stat_path(mock_conn, malicious_path)

        # Verify the command was called
        mock_conn.run.assert_called_once()
        cmd = mock_conn.run.call_args[0][0]

        # The path should be properly quoted - not using repr()
        assert "!r" not in cmd  # No repr format spec in final command
        assert "'/tmp'\"'\"'; rm -rf / #'" in cmd or "'/tmp'\\'''; rm -rf / #'" in cmd

    async def test_cat_file_quotes_path(self, mock_conn):
        """cat_file should use shlex.quote for path."""
        from scout_mcp.services.executors import cat_file

        malicious_path = "/tmp/$(whoami).txt"
        await cat_file(mock_conn, malicious_path, 1024)

        cmd = mock_conn.run.call_args[0][0]
        # $ should be inside quotes, not interpreted
        assert "'$" in cmd or "\\$" in cmd

    async def test_run_command_quotes_working_dir(self, mock_conn):
        """run_command should quote working_dir but NOT the command itself."""
        from scout_mcp.services.executors import run_command

        malicious_dir = "/tmp'; rm -rf / #"
        await run_command(mock_conn, malicious_dir, "ls -la", timeout=30)

        cmd = mock_conn.run.call_args[0][0]
        # Working dir should be quoted
        assert "cd '" in cmd
        # But 'ls -la' should NOT be quoted (it's meant to be interpreted)
        assert "ls -la" in cmd
```

**Run and verify RED:**
```bash
uv run pytest tests/test_executors_security.py -v
# Expected: Tests FAIL because executors still use repr()
```

##### STEP 4: GREEN - Update executors.py

**Replace ALL instances of `!r` with `shlex.quote()`:**

```python
# scout_mcp/services/executors.py
import shlex

# Line 17: stat_path
result = await conn.run(f'stat -c "%F" {shlex.quote(path)} 2>/dev/null', check=False)

# Line 53: cat_file
result = await conn.run(f"head -c {max_size} {shlex.quote(path)}", check=False)

# Line 87: ls_dir
result = await conn.run(f"ls -la {shlex.quote(path)}", check=False)

# Line 124: tree_dir
result = await conn.run(
    f"tree -L {max_depth} --noreport {shlex.quote(path)} 2>/dev/null", check=False
)

# Line 137: tree_dir find fallback
find_cmd = (
    f"find {shlex.quote(path)} -maxdepth {max_depth} -type f -o -type d "
    f"2>/dev/null | head -100"
)

# Line 161: run_command - CRITICAL
full_command = f"cd {shlex.quote(working_dir)} && timeout {timeout} {command}"
# NOTE: 'command' is intentionally NOT quoted - it's meant to be interpreted

# Line 214: docker_logs
cmd = f"docker logs --tail {tail} {ts_flag} {shlex.quote(container)} 2>&1"

# Line 281: docker_inspect
cmd = f"docker inspect --format '{{{{.Name}}}}' {shlex.quote(container)} 2>/dev/null"

# Line 368: compose_config - cat
read_result = await conn.run(f"cat {shlex.quote(config_file)}", check=False)

# Line 403: compose_logs
cmd = f"docker compose -p {shlex.quote(project)} logs --tail {tail} {ts_flag} 2>&1"

# Line 487: zfs_pool_status
cmd = f"zpool status {shlex.quote(pool)} 2>&1"

# Line 518: zfs_datasets
cmd = f"zfs list -H -r -o name,used,avail,refer,mountpoint {shlex.quote(pool)} 2>/dev/null"

# Line 567: zfs_snapshots
cmd = (
    f"zfs list -H -t snapshot -r -o name,used,creation "
    f"{shlex.quote(dataset)} 2>/dev/null | tail -{limit}"
)
```

3. **Add security tests:**
```python
# tests/test_security.py (NEW FILE)
"""Security tests for command injection prevention."""

import pytest
import shlex

from scout_mcp.utils.shell import quote_path, quote_arg


**Run and verify GREEN:**
```bash
uv run pytest tests/test_executors_security.py -v
# Expected: All tests PASS
```

##### STEP 5: REFACTOR - Clean Up and Verify

1. Run full test suite:
```bash
uv run pytest tests/ -v
```

2. Type check:
```bash
uv run mypy scout_mcp/
```

3. Lint:
```bash
uv run ruff check scout_mcp/ tests/ --fix
```

#### TDD Acceptance Criteria (All must be GREEN)
- [ ] `tests/test_shell_quoting.py` - All unit tests pass
- [ ] `tests/test_executors_security.py` - All security tests pass
- [ ] All `!r` format specs in executors.py replaced with `shlex.quote()`
- [ ] New `scout_mcp/utils/shell.py` with quote functions
- [ ] Full test suite passes: `uv run pytest tests/ -v`
- [ ] Type check passes: `uv run mypy scout_mcp/`
- [ ] Lint passes: `uv run ruff check scout_mcp/ tests/`

---

### Agent 3: scout_mcp-7di - Enable SSH Host Key Verification

**Files:** `scout_mcp/services/pool.py`, `scout_mcp/config.py`
**Effort:** 3 hours

#### Current State (VULNERABLE)
```python
# pool.py:67
conn = await asyncssh.connect(
    host.hostname,
    port=host.port,
    username=host.user,
    known_hosts=None,  # DISABLES ALL VERIFICATION
    client_keys=client_keys,
)
```

---

#### TDD Implementation Steps

##### STEP 1: RED - Write Failing Tests First

```python
# tests/test_host_key_verification.py
"""TDD: Tests for SSH host key verification - written BEFORE implementation."""

import pytest
from unittest.mock import patch, MagicMock
import os


class TestKnownHostsConfig:
    """Test known_hosts configuration."""

    def test_default_uses_ssh_known_hosts(self, tmp_path, monkeypatch):
        """Default should use ~/.ssh/known_hosts if it exists."""
        # Create fake known_hosts
        ssh_dir = tmp_path / ".ssh"
        ssh_dir.mkdir()
        known_hosts = ssh_dir / "known_hosts"
        known_hosts.write_text("example.com ssh-rsa AAAA...")

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("SCOUT_KNOWN_HOSTS", raising=False)

        from scout_mcp.config import Config
        config = Config()

        assert config.known_hosts_path == str(known_hosts)

    def test_explicit_none_disables(self, monkeypatch):
        """SCOUT_KNOWN_HOSTS=none should disable verification."""
        monkeypatch.setenv("SCOUT_KNOWN_HOSTS", "none")

        from scout_mcp.config import Config
        config = Config()

        assert config.known_hosts_path is None

    def test_custom_path_used(self, tmp_path, monkeypatch):
        """Custom path should be used when set."""
        custom_path = tmp_path / "my_known_hosts"
        custom_path.write_text("host key data")
        monkeypatch.setenv("SCOUT_KNOWN_HOSTS", str(custom_path))

        from scout_mcp.config import Config
        config = Config()

        assert config.known_hosts_path == str(custom_path)

    def test_strict_mode_default_true(self, monkeypatch):
        """Strict mode should default to True."""
        monkeypatch.delenv("SCOUT_STRICT_HOST_KEY_CHECKING", raising=False)

        from scout_mcp.config import Config
        config = Config()

        assert config.strict_host_key_checking is True

    def test_strict_mode_can_disable(self, monkeypatch):
        """Strict mode can be disabled via env var."""
        monkeypatch.setenv("SCOUT_STRICT_HOST_KEY_CHECKING", "false")

        from scout_mcp.config import Config
        config = Config()

        assert config.strict_host_key_checking is False


class TestPoolHostKeyVerification:
    """Test connection pool uses host key verification."""

    @pytest.fixture
    def mock_asyncssh(self):
        with patch("scout_mcp.services.pool.asyncssh") as mock:
            mock.connect = MagicMock()
            yield mock

    async def test_pool_passes_known_hosts(self, mock_asyncssh, monkeypatch):
        """Pool should pass known_hosts path to asyncssh.connect."""
        monkeypatch.setenv("SCOUT_KNOWN_HOSTS", "/path/to/known_hosts")

        from scout_mcp.services.pool import ConnectionPool
        from scout_mcp.services.state import reset_state
        reset_state()

        pool = ConnectionPool()
        host = MagicMock(name="test", hostname="example.com", port=22, user="user", identity_file=None)

        await pool.get_connection(host)

        # Verify known_hosts was passed
        call_kwargs = mock_asyncssh.connect.call_args.kwargs
        assert call_kwargs["known_hosts"] == "/path/to/known_hosts"

    async def test_pool_none_when_disabled(self, mock_asyncssh, monkeypatch):
        """Pool should pass None when verification disabled."""
        monkeypatch.setenv("SCOUT_KNOWN_HOSTS", "none")

        from scout_mcp.services.pool import ConnectionPool
        from scout_mcp.services.state import reset_state
        reset_state()

        pool = ConnectionPool()
        host = MagicMock(name="test", hostname="example.com", port=22, user="user", identity_file=None)

        await pool.get_connection(host)

        call_kwargs = mock_asyncssh.connect.call_args.kwargs
        assert call_kwargs["known_hosts"] is None
```

**Run and verify RED:**
```bash
uv run pytest tests/test_host_key_verification.py -v
# Expected: AttributeError - Config has no known_hosts_path
```

##### STEP 2: GREEN - Add Configuration Properties

```python
# scout_mcp/config.py - Add to Config class
from pathlib import Path

@property
def known_hosts_path(self) -> str | None:
    """Path to known_hosts file, or None to disable verification.

    Environment: SCOUT_KNOWN_HOSTS
    Default: ~/.ssh/known_hosts
    Special value: "none" disables verification (NOT RECOMMENDED)
    """
    value = os.getenv("SCOUT_KNOWN_HOSTS", "").strip()
    if value.lower() == "none":
        return None
    if value:
        return os.path.expanduser(value)
    # Default to standard location
    default = Path.home() / ".ssh" / "known_hosts"
    if default.exists():
        return str(default)
    return None  # No known_hosts available

@property
def strict_host_key_checking(self) -> bool:
    """Whether to reject unknown host keys.

    Environment: SCOUT_STRICT_HOST_KEY_CHECKING
    Default: True (reject unknown hosts)
    """
    return os.getenv("SCOUT_STRICT_HOST_KEY_CHECKING", "true").lower() != "false"
```

2. **Update pool.py:**
```python
# scout_mcp/services/pool.py

import logging
from pathlib import Path

from scout_mcp.services import get_config

logger = logging.getLogger(__name__)


class ConnectionPool:
    """SSH connection pool with idle timeout."""

    def __init__(self, idle_timeout: int = 60) -> None:
        self.idle_timeout = idle_timeout
        self._connections: dict[str, PooledConnection] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task[Any] | None = None

        # Cache known_hosts configuration
        config = get_config()
        self._known_hosts = config.known_hosts_path
        self._strict_host_key = config.strict_host_key_checking

        if self._known_hosts is None:
            logger.warning(
                "SSH host key verification DISABLED - vulnerable to MITM attacks. "
                "Set SCOUT_KNOWN_HOSTS to a valid known_hosts file path."
            )
        else:
            logger.info(
                "SSH host key verification enabled (known_hosts=%s, strict=%s)",
                self._known_hosts,
                self._strict_host_key,
            )

    async def get_connection(self, host: "SSHHost") -> asyncssh.SSHClientConnection:
        """Get or create a connection to the host."""
        async with self._lock:
            # ... existing pool check logic ...

            # Create new connection with host key verification
            logger.info(
                "Opening SSH connection to %s (%s@%s:%d)",
                host.name,
                host.user,
                host.hostname,
                host.port,
            )
            client_keys = [host.identity_file] if host.identity_file else None

            # Determine known_hosts setting
            if self._known_hosts is None:
                known_hosts_arg = None  # Disable verification (legacy mode)
            else:
                known_hosts_arg = self._known_hosts

            try:
                conn = await asyncssh.connect(
                    host.hostname,
                    port=host.port,
                    username=host.user,
                    known_hosts=known_hosts_arg,
                    client_keys=client_keys,
                )
            except asyncssh.HostKeyNotVerifiable as e:
                if self._strict_host_key:
                    logger.error(
                        "Host key verification failed for %s: %s. "
                        "Add the host key to %s or set SCOUT_STRICT_HOST_KEY_CHECKING=false",
                        host.name,
                        e,
                        self._known_hosts,
                    )
                    raise
                else:
                    logger.warning(
                        "Host key not verified for %s (strict mode disabled): %s",
                        host.name,
                        e,
                    )
                    # Retry with verification disabled for this host
                    conn = await asyncssh.connect(
                        host.hostname,
                        port=host.port,
                        username=host.user,
                        known_hosts=None,
                        client_keys=client_keys,
                    )

            # ... rest of method unchanged ...
```

3. **Update tests:**
```python
# tests/test_pool.py - Update mock to handle known_hosts

@pytest.fixture
def mock_config(monkeypatch):
    """Mock config with known_hosts disabled for testing."""
    monkeypatch.setenv("SCOUT_KNOWN_HOSTS", "none")
```

4. **Add documentation to CLAUDE.md:**
```markdown
### SSH Host Key Verification

By default, scout_mcp verifies SSH host keys against `~/.ssh/known_hosts`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `SCOUT_KNOWN_HOSTS` | ~/.ssh/known_hosts | Path to known_hosts file |
| `SCOUT_STRICT_HOST_KEY_CHECKING` | true | Reject unknown host keys |

**Security Warning:** Setting `SCOUT_KNOWN_HOSTS=none` disables host key verification,
making connections vulnerable to man-in-the-middle attacks.
```

#### Acceptance Criteria
- [ ] Default behavior uses ~/.ssh/known_hosts
- [ ] `SCOUT_KNOWN_HOSTS=none` explicitly disables (with warning log)
- [ ] `SCOUT_STRICT_HOST_KEY_CHECKING=false` allows unknown hosts (with warning)
- [ ] Host key errors produce clear error messages
- [ ] All tests pass (with mocked config)
- [ ] Documentation updated

---

## Batch 2: Code Quality & Testing (Parallel - 4 Agents)

Execute after Batch 1 completes. All can run in parallel.

### Agent 4: scout_mcp-2rf - Extract Connection Retry Helper

**Files:** `scout_mcp/services/connection.py` (NEW), multiple resource files
**Effort:** 2 hours

#### Current State (Duplicated ~120 lines)
```python
# Pattern repeated in 8+ files:
try:
    conn = await pool.get_connection(ssh_host)
except Exception as first_error:
    logger.warning("Connection to %s failed: %s, retrying", ssh_host.name, first_error)
    try:
        await pool.remove_connection(ssh_host.name)
        conn = await pool.get_connection(ssh_host)
    except Exception as retry_error:
        return f"Error: Cannot connect to {ssh_host.name}: {retry_error}"
```

---

#### TDD Implementation Steps

##### STEP 1: RED - Write Failing Tests First

Create `tests/test_connection_retry.py` with tests that will fail (module doesn't exist yet):

```python
# tests/test_connection_retry.py
"""TDD: Tests for connection retry helper - written BEFORE implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestConnectionError:
    """Test custom ConnectionError exception."""

    def test_error_contains_host_name(self):
        """ConnectionError should include host name."""
        from scout_mcp.services.connection import ConnectionError

        error = ConnectionError("test-host", Exception("network failure"))

        assert error.host_name == "test-host"
        assert "test-host" in str(error)
        assert "network failure" in str(error)

    def test_error_preserves_original(self):
        """ConnectionError should preserve original exception."""
        from scout_mcp.services.connection import ConnectionError

        original = ValueError("original error")
        error = ConnectionError("host", original)

        assert error.original_error is original


class TestGetConnectionWithRetry:
    """Test connection retry helper."""

    @pytest.fixture
    def mock_pool(self):
        with patch("scout_mcp.services.connection.get_pool") as mock:
            yield mock.return_value

    @pytest.fixture
    def mock_host(self):
        host = MagicMock()
        host.name = "test-host"
        return host

    async def test_success_first_try(self, mock_pool, mock_host):
        """Connection succeeds on first attempt - no retry needed."""
        from scout_mcp.services.connection import get_connection_with_retry

        mock_conn = MagicMock()
        mock_pool.get_connection = AsyncMock(return_value=mock_conn)

        result = await get_connection_with_retry(mock_host)

        assert result == mock_conn
        mock_pool.get_connection.assert_called_once_with(mock_host)
        mock_pool.remove_connection.assert_not_called()

    async def test_success_after_retry(self, mock_pool, mock_host):
        """Connection fails first, succeeds on retry."""
        from scout_mcp.services.connection import get_connection_with_retry

        mock_conn = MagicMock()
        mock_pool.get_connection = AsyncMock(
            side_effect=[Exception("First fail"), mock_conn]
        )
        mock_pool.remove_connection = AsyncMock()

        result = await get_connection_with_retry(mock_host)

        assert result == mock_conn
        assert mock_pool.get_connection.call_count == 2
        mock_pool.remove_connection.assert_called_once_with("test-host")

    async def test_failure_after_retry_raises(self, mock_pool, mock_host):
        """Connection fails on both attempts - raises ConnectionError."""
        from scout_mcp.services.connection import (
            ConnectionError,
            get_connection_with_retry,
        )

        mock_pool.get_connection = AsyncMock(
            side_effect=[Exception("First"), Exception("Second")]
        )
        mock_pool.remove_connection = AsyncMock()

        with pytest.raises(ConnectionError) as exc_info:
            await get_connection_with_retry(mock_host)

        assert "test-host" in str(exc_info.value)
        assert exc_info.value.host_name == "test-host"

    async def test_remove_connection_called_on_first_failure(self, mock_pool, mock_host):
        """Pool cleanup happens after first failure before retry."""
        from scout_mcp.services.connection import get_connection_with_retry

        mock_conn = MagicMock()
        call_order = []

        async def track_get(*args):
            call_order.append("get")
            if len(call_order) == 1:
                raise Exception("First fail")
            return mock_conn

        async def track_remove(*args):
            call_order.append("remove")

        mock_pool.get_connection = track_get
        mock_pool.remove_connection = track_remove

        await get_connection_with_retry(mock_host)

        assert call_order == ["get", "remove", "get"]
```

**Run and verify RED:**
```bash
uv run pytest tests/test_connection_retry.py -v
# Expected: ModuleNotFoundError - tests FAIL
```

##### STEP 2: GREEN - Implement Minimal Code to Pass

Create `scout_mcp/services/connection.py`:
```python
# scout_mcp/services/connection.py (NEW FILE)
"""SSH connection helper with automatic retry."""

import logging
from typing import TYPE_CHECKING

from scout_mcp.services import get_pool

if TYPE_CHECKING:
    import asyncssh
    from scout_mcp.models import SSHHost

logger = logging.getLogger(__name__)


class ConnectionError(Exception):
    """Failed to establish SSH connection after retry."""

    def __init__(self, host_name: str, original_error: Exception):
        self.host_name = host_name
        self.original_error = original_error
        super().__init__(f"Cannot connect to {host_name}: {original_error}")


async def get_connection_with_retry(
    ssh_host: "SSHHost",
) -> "asyncssh.SSHClientConnection":
    """Get SSH connection with automatic one-time retry on failure.

    Args:
        ssh_host: SSH host configuration

    Returns:
        Active SSH connection

    Raises:
        ConnectionError: If connection fails after retry
    """
    pool = get_pool()

    try:
        return await pool.get_connection(ssh_host)
    except Exception as first_error:
        logger.warning(
            "Connection to %s failed: %s, retrying after cleanup",
            ssh_host.name,
            first_error,
        )
        try:
            await pool.remove_connection(ssh_host.name)
            conn = await pool.get_connection(ssh_host)
            logger.info("Retry connection to %s succeeded", ssh_host.name)
            return conn
        except Exception as retry_error:
            logger.error(
                "Retry connection to %s failed: %s",
                ssh_host.name,
                retry_error,
            )
            raise ConnectionError(ssh_host.name, retry_error) from retry_error
```

2. **Update services/__init__.py:**
```python
# scout_mcp/services/__init__.py
from scout_mcp.services.connection import (
    ConnectionError,
    get_connection_with_retry,
)
from scout_mcp.services.state import get_config, get_pool, reset_state

__all__ = [
    "ConnectionError",
    "get_config",
    "get_connection_with_retry",
    "get_pool",
    "reset_state",
]
```

3. **Update scout.py to use helper:**
```python
# scout_mcp/tools/scout.py
from scout_mcp.services import get_config, get_pool, get_connection_with_retry, ConnectionError

async def scout(target: str, query: str | None = None, tree: bool = False) -> str:
    # ... existing code until connection ...

    # Get connection (with automatic retry)
    try:
        conn = await get_connection_with_retry(ssh_host)
    except ConnectionError as e:
        return f"Error: {e}"

    # ... rest unchanged ...
```

4. **Update all resource files:**
Files to update (replace retry pattern with helper):
- `scout_mcp/resources/scout.py`
- `scout_mcp/resources/docker.py`
- `scout_mcp/resources/compose.py`
- `scout_mcp/resources/zfs.py`
- `scout_mcp/resources/syslog.py`

Example pattern:
```python
# Before (in each resource file):
try:
    conn = await pool.get_connection(ssh_host)
except Exception as first_error:
    # ... 15 lines of retry logic ...

# After:
from scout_mcp.services import get_connection_with_retry, ConnectionError

try:
    conn = await get_connection_with_retry(ssh_host)
except ConnectionError as e:
    raise ResourceError(str(e)) from e
```

**Run and verify GREEN:**
```bash
uv run pytest tests/test_connection_retry.py -v
# Expected: All tests PASS
```

##### STEP 3: Integrate with Existing Code (RED again)

Write integration tests for scout.py to ensure it uses the new helper:

```python
# tests/test_scout_uses_connection_helper.py
"""TDD: Verify scout uses connection helper."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestScoutUsesConnectionHelper:
    """Verify scout() uses get_connection_with_retry."""

    @pytest.fixture
    def mock_config(self):
        with patch("scout_mcp.tools.scout.get_config") as mock:
            config = MagicMock()
            config.get_host.return_value = MagicMock(name="test-host")
            config.command_timeout = 30
            config.max_file_size = 1024
            mock.return_value = config
            yield mock

    @pytest.fixture
    def mock_parse(self):
        with patch("scout_mcp.tools.scout.parse_target") as mock:
            parsed = MagicMock()
            parsed.is_hosts_command = False
            parsed.host = "test-host"
            parsed.path = "/test/path"
            mock.return_value = parsed
            yield mock

    async def test_scout_uses_get_connection_with_retry(self, mock_config, mock_parse):
        """scout() should use get_connection_with_retry, not pool.get_connection."""
        from scout_mcp.tools.scout import scout

        with patch("scout_mcp.services.get_connection_with_retry") as mock_retry:
            mock_conn = MagicMock()
            mock_retry.return_value = mock_conn

            with patch("scout_mcp.services.executors.stat_path") as mock_stat:
                mock_stat.return_value = "file"
                with patch("scout_mcp.services.executors.cat_file") as mock_cat:
                    mock_cat.return_value = ("content", False)

                    await scout("test-host:/test/path")

                    # Verify retry helper was called
                    mock_retry.assert_called_once()
```

##### STEP 4: GREEN - Update scout.py and resources

Update `scout_mcp/tools/scout.py`:
```python
from scout_mcp.services import get_config, get_connection_with_retry, ConnectionError

# Replace the try/except retry pattern with:
try:
    conn = await get_connection_with_retry(ssh_host)
except ConnectionError as e:
    return f"Error: {e}"
```

Update all resource files similarly.

##### STEP 5: REFACTOR - Clean Up and Verify

1. Run full test suite:
```bash
uv run pytest tests/ -v
```

2. Update `services/__init__.py` exports:
```python
from scout_mcp.services.connection import (
    ConnectionError,
    get_connection_with_retry,
)
```

3. Type check and lint:
```bash
uv run mypy scout_mcp/
uv run ruff check scout_mcp/ tests/
```

#### TDD Acceptance Criteria (All must be GREEN)
- [ ] `tests/test_connection_retry.py` - All unit tests pass (RED→GREEN)
- [ ] `tests/test_scout_uses_connection_helper.py` - Integration tests pass
- [ ] New `scout_mcp/services/connection.py` with `get_connection_with_retry()`
- [ ] All 8+ resource files updated to use helper
- [ ] ~100 lines of duplication removed
- [ ] Full test suite passes: `uv run pytest tests/ -v`
- [ ] Type check passes: `uv run mypy scout_mcp/`

---

### Agent 5: scout_mcp-pya - Add Path Traversal Protection

**Files:** `scout_mcp/utils/parser.py`, `scout_mcp/utils/validation.py` (NEW)
**Effort:** 2 hours

#### Current State (NO VALIDATION)
```python
# parser.py - No path validation at all
path = parts[1].strip() if len(parts) > 1 else ""
return ScoutTarget(host=host, path=path)
```

---

#### TDD Implementation Steps

##### STEP 1: RED - Write Failing Tests First

Create `tests/test_path_validation.py` with tests that will fail:

```python
# tests/test_path_validation.py
"""TDD: Tests for path validation - written BEFORE implementation."""

import pytest


class TestPathTraversalError:
    """Test custom PathTraversalError exception."""

    def test_error_is_value_error(self):
        """PathTraversalError should be a ValueError."""
        from scout_mcp.utils.validation import PathTraversalError

        error = PathTraversalError("test message")
        assert isinstance(error, ValueError)


class TestValidatePath:
    """Test path validation function."""

    def test_simple_absolute_path(self):
        """Simple absolute paths should pass."""
        from scout_mcp.utils.validation import validate_path

        assert validate_path("/var/log") == "/var/log"

    def test_simple_relative_path(self):
        """Simple relative paths should pass."""
        from scout_mcp.utils.validation import validate_path

        assert validate_path("logs/app.log") == "logs/app.log"

    def test_home_directory_tilde(self):
        """Home directory paths with ~ should pass unchanged."""
        from scout_mcp.utils.validation import validate_path

        assert validate_path("~/code") == "~/code"
        assert validate_path("~/.ssh/config") == "~/.ssh/config"

    def test_traversal_dot_dot_slash_rejected(self):
        """../ traversal attempts must be rejected."""
        from scout_mcp.utils.validation import PathTraversalError, validate_path

        with pytest.raises(PathTraversalError):
            validate_path("../etc/passwd")

    def test_traversal_embedded_rejected(self):
        """Embedded ../ traversal must be rejected."""
        from scout_mcp.utils.validation import PathTraversalError, validate_path

        with pytest.raises(PathTraversalError):
            validate_path("/var/log/../../../etc/passwd")

    def test_traversal_normalized_rejected(self):
        """Paths that normalize to escaping root must be rejected."""
        from scout_mcp.utils.validation import PathTraversalError, validate_path

        with pytest.raises(PathTraversalError):
            validate_path("/var/log/../../..")

    def test_null_byte_rejected(self):
        """Null byte injection must be rejected."""
        from scout_mcp.utils.validation import PathTraversalError, validate_path

        with pytest.raises(PathTraversalError):
            validate_path("/var/log/app.log\x00.txt")

    def test_empty_path_rejected(self):
        """Empty paths must be rejected."""
        from scout_mcp.utils.validation import validate_path

        with pytest.raises(ValueError):
            validate_path("")

    def test_absolute_not_allowed_when_disabled(self):
        """Absolute paths rejected when allow_absolute=False."""
        from scout_mcp.utils.validation import validate_path

        with pytest.raises(ValueError):
            validate_path("/etc/passwd", allow_absolute=False)


class TestValidateHost:
    """Test host validation function."""

    def test_simple_host(self):
        """Simple hostnames should pass."""
        from scout_mcp.utils.validation import validate_host

        assert validate_host("myserver") == "myserver"

    def test_host_with_domain(self):
        """Hostnames with domains should pass."""
        from scout_mcp.utils.validation import validate_host

        assert validate_host("server.example.com") == "server.example.com"

    def test_empty_host_rejected(self):
        """Empty hostnames must be rejected."""
        from scout_mcp.utils.validation import validate_host

        with pytest.raises(ValueError):
            validate_host("")

    def test_host_with_slash_rejected(self):
        """Hostnames with slashes must be rejected."""
        from scout_mcp.utils.validation import validate_host

        with pytest.raises(ValueError):
            validate_host("server/path")

    def test_host_with_semicolon_rejected(self):
        """Hostnames with semicolons (command injection) must be rejected."""
        from scout_mcp.utils.validation import validate_host

        with pytest.raises(ValueError):
            validate_host("server;rm -rf /")

    def test_host_with_pipe_rejected(self):
        """Hostnames with pipes (command injection) must be rejected."""
        from scout_mcp.utils.validation import validate_host

        with pytest.raises(ValueError):
            validate_host("server|cat /etc/passwd")

    def test_host_with_backtick_rejected(self):
        """Hostnames with backticks (command substitution) must be rejected."""
        from scout_mcp.utils.validation import validate_host

        with pytest.raises(ValueError):
            validate_host("server`whoami`")

    def test_host_too_long_rejected(self):
        """Hostnames over 253 chars must be rejected."""
        from scout_mcp.utils.validation import validate_host

        with pytest.raises(ValueError):
            validate_host("a" * 254)
```

**Run and verify RED:**
```bash
uv run pytest tests/test_path_validation.py -v
# Expected: ModuleNotFoundError - tests FAIL
```

##### STEP 2: GREEN - Implement Minimal Code to Pass

Create `scout_mcp/utils/validation.py`:
```python
# scout_mcp/utils/validation.py (NEW FILE)
"""Path and input validation utilities."""

import os
import re
from pathlib import PurePosixPath


class PathTraversalError(ValueError):
    """Attempted path traversal detected."""
    pass


def validate_path(path: str, allow_absolute: bool = True) -> str:
    """Validate a remote path for safety.

    Checks for path traversal attempts and suspicious patterns.

    Args:
        path: The path to validate
        allow_absolute: Whether to allow absolute paths (default: True)

    Returns:
        Normalized path

    Raises:
        PathTraversalError: If path contains traversal sequences
        ValueError: If path is invalid
    """
    if not path:
        raise ValueError("Path cannot be empty")

    # Check for null bytes (can bypass validation in some systems)
    if "\x00" in path:
        raise PathTraversalError(f"Path contains null byte: {path!r}")

    # Check for explicit traversal sequences
    traversal_patterns = [
        r"\.\./",           # ../
        r"/\.\.",           # /..
        r"^\.\.$",          # Just ..
        r"^\.\.\\",         # ..\
        r"\\\.\.",          # \..
    ]
    for pattern in traversal_patterns:
        if re.search(pattern, path):
            raise PathTraversalError(f"Path traversal not allowed: {path}")

    # Normalize the path
    try:
        normalized = os.path.normpath(path)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid path: {path}") from e

    # After normalization, check if we escaped the root
    if normalized.startswith(".."):
        raise PathTraversalError(f"Path escapes root after normalization: {path}")

    # Check absolute path policy
    if not allow_absolute and os.path.isabs(normalized):
        raise ValueError(f"Absolute paths not allowed: {path}")

    # Expand ~ to home directory marker (will be expanded on remote)
    if path.startswith("~"):
        return path  # Allow ~ paths as-is for remote expansion

    return normalized


def validate_host(host: str) -> str:
    """Validate a host name.

    Args:
        host: The host name to validate

    Returns:
        Validated host name

    Raises:
        ValueError: If host name is invalid
    """
    if not host:
        raise ValueError("Host cannot be empty")

    # Basic hostname validation
    if len(host) > 253:
        raise ValueError(f"Host name too long: {len(host)} chars")

    # Check for suspicious characters
    if any(c in host for c in ['/', '\\', ':', ';', '&', '|', '$', '`']):
        raise ValueError(f"Host contains invalid characters: {host}")

    return host
```

2. **Update parser.py:**
```python
# scout_mcp/utils/parser.py
"""URI parsing for scout targets."""

from scout_mcp.models import ScoutTarget
from scout_mcp.utils.validation import validate_host, validate_path, PathTraversalError


def parse_target(target: str) -> ScoutTarget:
    """Parse a scout target URI.

    Args:
        target: Either 'hosts' or 'hostname:/path' format

    Returns:
        Parsed ScoutTarget

    Raises:
        ValueError: If target format is invalid
        PathTraversalError: If path contains traversal sequences
    """
    target = target.strip()

    # Special case: hosts command
    if target.lower() == "hosts":
        return ScoutTarget(host=None, is_hosts_command=True)

    # Parse host:/path format
    if ":" not in target:
        raise ValueError(f"Invalid target '{target}'. Expected 'host:/path' or 'hosts'")

    parts = target.split(":", 1)
    host = parts[0].strip()
    path = parts[1].strip() if len(parts) > 1 else ""

    # Validate host
    host = validate_host(host)

    # Validate path
    if not path:
        raise ValueError("Path cannot be empty")
    path = validate_path(path)

    return ScoutTarget(host=host, path=path)
```

**Run and verify GREEN:**
```bash
uv run pytest tests/test_path_validation.py -v
# Expected: All tests PASS
```

##### STEP 3: Integration Tests (RED again)

Write tests for parser.py using the new validation:

```python
# tests/test_parser_validation.py
"""TDD: Verify parser uses validation."""

import pytest
from scout_mcp.utils.parser import parse_target
from scout_mcp.utils.validation import PathTraversalError


class TestParserUsesValidation:
    """Verify parse_target() uses validation functions."""

    def test_traversal_rejected_by_parser(self):
        """parse_target should reject traversal paths."""
        with pytest.raises(PathTraversalError):
            parse_target("host:../etc/passwd")

    def test_malicious_host_rejected_by_parser(self):
        """parse_target should reject malicious hostnames."""
        with pytest.raises(ValueError):
            parse_target("host;rm -rf /:/path")

    def test_valid_target_passes(self):
        """Valid targets should pass validation."""
        result = parse_target("myhost:/var/log")
        assert result.host == "myhost"
        assert result.path == "/var/log"
```

##### STEP 4: GREEN - Update parser.py

```python
# scout_mcp/utils/parser.py
from scout_mcp.utils.validation import validate_host, validate_path

def parse_target(target: str) -> ScoutTarget:
    # ... existing parsing ...
    host = validate_host(host)
    path = validate_path(path)
    return ScoutTarget(host=host, path=path)
```

##### STEP 5: REFACTOR - Clean Up and Verify

```bash
uv run pytest tests/ -v
uv run mypy scout_mcp/
uv run ruff check scout_mcp/ tests/
```

#### TDD Acceptance Criteria (All must be GREEN)
- [ ] `tests/test_path_validation.py` - All unit tests pass (RED→GREEN)
- [ ] `tests/test_parser_validation.py` - Integration tests pass
- [ ] New `scout_mcp/utils/validation.py` with `validate_path()` and `validate_host()`
- [ ] `parser.py` updated to use validation
- [ ] Path traversal attempts rejected with clear error
- [ ] Null byte injection blocked
- [ ] Full test suite passes: `uv run pytest tests/ -v`
- [ ] Type check passes: `uv run mypy scout_mcp/`

---

### Agent 6: scout_mcp-ydy - Split scout() Function

**Files:** `scout_mcp/tools/scout.py`, `scout_mcp/tools/handlers.py` (NEW)
**Effort:** 4 hours
**Depends on:** scout_mcp-2rf (uses `get_connection_with_retry`)

#### Current State (128 lines, 5+ responsibilities)
```python
async def scout(target: str, query: str | None = None, tree: bool = False) -> str:
    # Lines 19-147: Handles hosts, files, directories, commands
```

---

#### TDD Implementation Steps

##### STEP 1: RED - Write Failing Tests First

Create `tests/test_handlers.py` with tests for each handler:

```python
# tests/test_handlers.py
"""TDD: Tests for scout tool handlers - written BEFORE implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestHandleHostsList:
    """Test hosts list handler."""

    async def test_returns_no_hosts_message_when_empty(self):
        """Should return helpful message when no hosts configured."""
        from scout_mcp.tools.handlers import handle_hosts_list

        with patch("scout_mcp.tools.handlers.get_config") as mock_config:
            mock_config.return_value.get_hosts.return_value = {}

            result = await handle_hosts_list()

            assert "No SSH hosts configured" in result

    async def test_lists_hosts_with_status(self):
        """Should list hosts with online/offline status."""
        from scout_mcp.tools.handlers import handle_hosts_list

        with patch("scout_mcp.tools.handlers.get_config") as mock_config:
            mock_config.return_value.get_hosts.return_value = {
                "host1": MagicMock(hostname="h1", port=22, user="u"),
            }
            with patch("scout_mcp.tools.handlers.check_hosts_online") as mock_ping:
                mock_ping.return_value = {"host1": True}

                result = await handle_hosts_list()

                assert "host1" in result
                assert "online" in result


class TestHandleCommandExecution:
    """Test command execution handler."""

    async def test_returns_command_output(self):
        """Should return command output."""
        from scout_mcp.tools.handlers import handle_command_execution

        mock_host = MagicMock()
        with patch("scout_mcp.tools.handlers.get_connection_with_retry") as mock_conn:
            mock_conn.return_value = MagicMock()
            with patch("scout_mcp.tools.handlers.run_command") as mock_run:
                mock_run.return_value = MagicMock(
                    output="hello world",
                    error="",
                    returncode=0,
                )
                with patch("scout_mcp.tools.handlers.get_config") as mock_cfg:
                    mock_cfg.return_value.command_timeout = 30

                    result = await handle_command_execution(mock_host, "/tmp", "echo hello")

                    assert "hello world" in result

    async def test_includes_stderr_when_present(self):
        """Should include stderr in output."""
        from scout_mcp.tools.handlers import handle_command_execution

        mock_host = MagicMock()
        with patch("scout_mcp.tools.handlers.get_connection_with_retry") as mock_conn:
            mock_conn.return_value = MagicMock()
            with patch("scout_mcp.tools.handlers.run_command") as mock_run:
                mock_run.return_value = MagicMock(
                    output="",
                    error="permission denied",
                    returncode=1,
                )
                with patch("scout_mcp.tools.handlers.get_config") as mock_cfg:
                    mock_cfg.return_value.command_timeout = 30

                    result = await handle_command_execution(mock_host, "/tmp", "cat /root/secret")

                    assert "stderr" in result
                    assert "permission denied" in result


class TestHandleFileRead:
    """Test file read handler."""

    async def test_returns_file_contents(self):
        """Should return file contents."""
        from scout_mcp.tools.handlers import handle_file_read

        mock_host = MagicMock()
        with patch("scout_mcp.tools.handlers.get_connection_with_retry") as mock_conn:
            mock_conn.return_value = MagicMock()
            with patch("scout_mcp.tools.handlers.cat_file") as mock_cat:
                mock_cat.return_value = ("file contents here", False)
                with patch("scout_mcp.tools.handlers.get_config") as mock_cfg:
                    mock_cfg.return_value.max_file_size = 1024

                    result = await handle_file_read(mock_host, "/etc/hosts")

                    assert result == "file contents here"

    async def test_indicates_truncation(self):
        """Should indicate when file was truncated."""
        from scout_mcp.tools.handlers import handle_file_read

        mock_host = MagicMock()
        with patch("scout_mcp.tools.handlers.get_connection_with_retry") as mock_conn:
            mock_conn.return_value = MagicMock()
            with patch("scout_mcp.tools.handlers.cat_file") as mock_cat:
                mock_cat.return_value = ("partial content", True)
                with patch("scout_mcp.tools.handlers.get_config") as mock_cfg:
                    mock_cfg.return_value.max_file_size = 100

                    result = await handle_file_read(mock_host, "/var/log/big.log")

                    assert "truncated" in result


class TestHandleDirectoryList:
    """Test directory listing handler."""

    async def test_returns_ls_output_by_default(self):
        """Should return ls output by default."""
        from scout_mcp.tools.handlers import handle_directory_list

        mock_host = MagicMock()
        with patch("scout_mcp.tools.handlers.get_connection_with_retry") as mock_conn:
            mock_conn.return_value = MagicMock()
            with patch("scout_mcp.tools.handlers.ls_dir") as mock_ls:
                mock_ls.return_value = "drwxr-xr-x 2 root root 4096 Jan 1 file.txt"

                result = await handle_directory_list(mock_host, "/tmp")

                assert "file.txt" in result
                mock_ls.assert_called_once()

    async def test_returns_tree_output_when_requested(self):
        """Should return tree output when use_tree=True."""
        from scout_mcp.tools.handlers import handle_directory_list

        mock_host = MagicMock()
        with patch("scout_mcp.tools.handlers.get_connection_with_retry") as mock_conn:
            mock_conn.return_value = MagicMock()
            with patch("scout_mcp.tools.handlers.tree_dir") as mock_tree:
                mock_tree.return_value = "/tmp\n├── file1.txt\n└── file2.txt"

                result = await handle_directory_list(mock_host, "/tmp", use_tree=True)

                assert "├──" in result
                mock_tree.assert_called_once()


class TestDeterminePathType:
    """Test path type determination."""

    async def test_returns_file_for_file(self):
        """Should return 'file' for files."""
        from scout_mcp.tools.handlers import determine_path_type

        mock_host = MagicMock()
        with patch("scout_mcp.tools.handlers.get_connection_with_retry") as mock_conn:
            mock_conn.return_value = MagicMock()
            with patch("scout_mcp.tools.handlers.stat_path") as mock_stat:
                mock_stat.return_value = "file"

                path_type, error = await determine_path_type(mock_host, "/etc/hosts")

                assert path_type == "file"
                assert error is None

    async def test_returns_directory_for_directory(self):
        """Should return 'directory' for directories."""
        from scout_mcp.tools.handlers import determine_path_type

        mock_host = MagicMock()
        with patch("scout_mcp.tools.handlers.get_connection_with_retry") as mock_conn:
            mock_conn.return_value = MagicMock()
            with patch("scout_mcp.tools.handlers.stat_path") as mock_stat:
                mock_stat.return_value = "directory"

                path_type, error = await determine_path_type(mock_host, "/tmp")

                assert path_type == "directory"
                assert error is None

    async def test_returns_error_for_not_found(self):
        """Should return error for non-existent paths."""
        from scout_mcp.tools.handlers import determine_path_type

        mock_host = MagicMock()
        with patch("scout_mcp.tools.handlers.get_connection_with_retry") as mock_conn:
            mock_conn.return_value = MagicMock()
            with patch("scout_mcp.tools.handlers.stat_path") as mock_stat:
                mock_stat.return_value = None

                path_type, error = await determine_path_type(mock_host, "/nonexistent")

                assert path_type is None
                assert "not found" in error.lower()
```

**Run and verify RED:**
```bash
uv run pytest tests/test_handlers.py -v
# Expected: ModuleNotFoundError - tests FAIL
```

##### STEP 2: GREEN - Implement Handler Module

Create `scout_mcp/tools/handlers.py`:
```python
# scout_mcp/tools/handlers.py (NEW FILE)
"""Scout tool handlers for different operations."""

import logging
from typing import TYPE_CHECKING

from scout_mcp.services import get_config, get_pool, get_connection_with_retry, ConnectionError
from scout_mcp.services.executors import cat_file, ls_dir, run_command, stat_path, tree_dir
from scout_mcp.utils.ping import check_hosts_online

if TYPE_CHECKING:
    from scout_mcp.models import SSHHost

logger = logging.getLogger(__name__)


async def handle_hosts_list() -> str:
    """Handle 'hosts' command - list available SSH hosts with status.

    Returns:
        Formatted host list with online/offline status
    """
    config = get_config()
    hosts = config.get_hosts()

    if not hosts:
        return "No SSH hosts configured."

    # Check online status concurrently
    host_endpoints = {
        name: (host.hostname, host.port) for name, host in hosts.items()
    }
    online_status = await check_hosts_online(host_endpoints, timeout=2.0)

    lines = ["Available hosts:"]
    for name, host in sorted(hosts.items()):
        status_icon = "\u2713" if online_status.get(name) else "\u2717"
        status_text = "online" if online_status.get(name) else "offline"
        lines.append(
            f"  [{status_icon}] {name} ({status_text}) "
            f"-> {host.user}@{host.hostname}:{host.port}"
        )
    return "\n".join(lines)


async def handle_command_execution(
    ssh_host: "SSHHost",
    path: str,
    command: str,
) -> str:
    """Execute a command on remote host.

    Args:
        ssh_host: SSH host configuration
        path: Working directory for command
        command: Shell command to execute

    Returns:
        Command output or error message
    """
    config = get_config()

    try:
        conn = await get_connection_with_retry(ssh_host)
    except ConnectionError as e:
        return f"Error: {e}"

    try:
        result = await run_command(
            conn,
            path,
            command,
            timeout=config.command_timeout,
        )

        output_parts = []
        if result.output:
            output_parts.append(result.output)
        if result.error:
            output_parts.append(f"[stderr]\n{result.error}")
        if result.returncode != 0:
            output_parts.append(f"[exit code: {result.returncode}]")

        return "\n".join(output_parts) if output_parts else "(no output)"

    except Exception as e:
        return f"Error: Command failed: {e}"


async def handle_file_read(
    ssh_host: "SSHHost",
    path: str,
) -> str:
    """Read a file from remote host.

    Args:
        ssh_host: SSH host configuration
        path: Path to file

    Returns:
        File contents or error message
    """
    config = get_config()

    try:
        conn = await get_connection_with_retry(ssh_host)
    except ConnectionError as e:
        return f"Error: {e}"

    try:
        contents, was_truncated = await cat_file(
            conn, path, config.max_file_size
        )
        if was_truncated:
            contents += f"\n\n[truncated at {config.max_file_size} bytes]"
        return contents
    except Exception as e:
        return f"Error: {e}"


async def handle_directory_list(
    ssh_host: "SSHHost",
    path: str,
    use_tree: bool = False,
) -> str:
    """List a directory on remote host.

    Args:
        ssh_host: SSH host configuration
        path: Path to directory
        use_tree: If True, show tree view instead of ls

    Returns:
        Directory listing or error message
    """
    try:
        conn = await get_connection_with_retry(ssh_host)
    except ConnectionError as e:
        return f"Error: {e}"

    try:
        if use_tree:
            return await tree_dir(conn, path)
        else:
            return await ls_dir(conn, path)
    except Exception as e:
        return f"Error: {e}"


async def determine_path_type(
    ssh_host: "SSHHost",
    path: str,
) -> tuple[str | None, str | None]:
    """Determine if path is a file or directory.

    Args:
        ssh_host: SSH host configuration
        path: Path to check

    Returns:
        Tuple of (path_type, error_message)
        path_type is 'file', 'directory', or None
        error_message is set if an error occurred
    """
    try:
        conn = await get_connection_with_retry(ssh_host)
    except ConnectionError as e:
        return (None, str(e))

    try:
        path_type = await stat_path(conn, path)
        if path_type is None:
            return (None, f"Path not found: {path}")
        return (path_type, None)
    except Exception as e:
        return (None, f"Cannot stat {path}: {e}")
```

2. **Refactor scout.py:**
```python
# scout_mcp/tools/scout.py
"""Scout tool for remote file operations via SSH."""

import logging

from scout_mcp.services import get_config
from scout_mcp.tools.handlers import (
    determine_path_type,
    handle_command_execution,
    handle_directory_list,
    handle_file_read,
    handle_hosts_list,
)
from scout_mcp.utils.parser import parse_target

logger = logging.getLogger(__name__)


async def scout(target: str, query: str | None = None, tree: bool = False) -> str:
    """Scout remote files and directories via SSH.

    Args:
        target: Either 'hosts' to list available hosts,
            or 'hostname:/path' to target a path.
        query: Optional shell command to execute
            (e.g., "rg 'pattern'", "find . -name '*.py'").
        tree: If True, show directory tree instead of ls -la.

    Examples:
        scout("hosts") - List available SSH hosts
        scout("dookie:/var/log/app.log") - Cat a file
        scout("tootie:/etc/nginx") - List directory contents
        scout("tootie:/etc/nginx", tree=True) - Show directory tree
        scout("squirts:~/code", "rg 'TODO' -t py") - Search for pattern

    Returns:
        File contents, directory listing, command output, or host list.
    """
    config = get_config()

    # Parse target
    try:
        parsed = parse_target(target)
    except ValueError as e:
        return f"Error: {e}"

    # Handle hosts command
    if parsed.is_hosts_command:
        return await handle_hosts_list()

    # Validate host exists
    ssh_host = config.get_host(parsed.host)  # type: ignore[arg-type]
    if ssh_host is None:
        available = ", ".join(sorted(config.get_hosts().keys()))
        return f"Error: Unknown host '{parsed.host}'. Available: {available}"

    # If query provided, run command
    if query:
        return await handle_command_execution(ssh_host, parsed.path, query)

    # Determine if path is file or directory
    path_type, error = await determine_path_type(ssh_host, parsed.path)
    if error:
        return f"Error: {error}"

    # Handle file or directory
    if path_type == "file":
        return await handle_file_read(ssh_host, parsed.path)
    else:
        return await handle_directory_list(ssh_host, parsed.path, tree)
```

**Run and verify GREEN:**
```bash
uv run pytest tests/test_handlers.py -v
# Expected: All tests PASS
```

##### STEP 3: Integration Tests for Refactored scout() (RED again)

```python
# tests/test_scout_refactored.py
"""TDD: Verify refactored scout() uses handlers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestScoutUsesHandlers:
    """Verify scout() delegates to handlers."""

    async def test_hosts_command_uses_handler(self):
        """scout('hosts') should use handle_hosts_list."""
        with patch("scout_mcp.tools.scout.handle_hosts_list") as mock_handler:
            mock_handler.return_value = "Available hosts..."
            with patch("scout_mcp.tools.scout.parse_target") as mock_parse:
                mock_parse.return_value = MagicMock(is_hosts_command=True)

                from scout_mcp.tools.scout import scout
                result = await scout("hosts")

                mock_handler.assert_called_once()
                assert result == "Available hosts..."

    async def test_file_read_uses_handler(self):
        """scout() should use handle_file_read for files."""
        with patch("scout_mcp.tools.scout.parse_target") as mock_parse:
            mock_parse.return_value = MagicMock(
                is_hosts_command=False, host="h", path="/f"
            )
            with patch("scout_mcp.tools.scout.get_config") as mock_cfg:
                mock_cfg.return_value.get_host.return_value = MagicMock()
                with patch("scout_mcp.tools.scout.determine_path_type") as mock_type:
                    mock_type.return_value = ("file", None)
                    with patch("scout_mcp.tools.scout.handle_file_read") as mock_handler:
                        mock_handler.return_value = "file contents"

                        from scout_mcp.tools.scout import scout
                        result = await scout("h:/f")

                        mock_handler.assert_called_once()
```

##### STEP 4: GREEN - Refactor scout.py

Update `scout_mcp/tools/scout.py` to import and use handlers.

##### STEP 5: REFACTOR - Verify Size Reduction

```bash
# Verify scout.py is now ~50 lines
wc -l scout_mcp/tools/scout.py
# Expected: ~50 lines (was 128)

# Verify handlers are ≤30 lines each
wc -l scout_mcp/tools/handlers.py
# Expected: ~150-200 lines total for 5 handlers

# Run full suite
uv run pytest tests/ -v
uv run mypy scout_mcp/
```

#### TDD Acceptance Criteria (All must be GREEN)
- [ ] `tests/test_handlers.py` - All handler unit tests pass (RED→GREEN)
- [ ] `tests/test_scout_refactored.py` - Integration tests pass
- [ ] New `scout_mcp/tools/handlers.py` with 5 handler functions
- [ ] `scout()` reduced to ~50 lines (was 128)
- [ ] Each handler function ≤30 lines
- [ ] Full test suite passes: `uv run pytest tests/ -v`
- [ ] Code coverage maintained or improved

---

### Agent 7: scout_mcp-y6f - Fix pytest-asyncio Configuration

**Files:** `pyproject.toml`, test files
**Effort:** 2 hours

#### Current State
```toml
# pyproject.toml:48
asyncio_mode = "auto"  # DEPRECATED in pytest-asyncio 0.23+
```

---

#### TDD Implementation Steps

##### STEP 1: RED - Capture Current Test State

First, document current test behavior and any failures:

```bash
# Run tests and capture baseline
uv run pytest tests/ -v --tb=short 2>&1 | tee /tmp/test_baseline.txt

# Count passing/failing tests
uv run pytest tests/ -v --tb=no | grep -E "(PASSED|FAILED|ERROR)" | wc -l

# Check for deprecation warnings
uv run pytest tests/ -v -W default::DeprecationWarning 2>&1 | grep -i deprecat
```

Write a verification test for the new config:

```python
# tests/test_pytest_config.py
"""TDD: Verify pytest-asyncio configuration."""

import pytest
import sys


class TestAsyncioConfig:
    """Test that async tests work correctly."""

    async def test_async_function_runs(self):
        """Simple async test should run without markers."""
        import asyncio
        await asyncio.sleep(0.001)
        assert True

    async def test_async_fixture_works(self):
        """Async tests should have access to event loop."""
        import asyncio
        loop = asyncio.get_running_loop()
        assert loop is not None

    def test_sync_still_works(self):
        """Sync tests should continue to work."""
        assert 1 + 1 == 2


class TestNoDeprecationWarnings:
    """Verify no deprecation warnings from pytest-asyncio."""

    def test_no_asyncio_mode_warning(self):
        """Should not warn about deprecated asyncio_mode."""
        # This test passes if no warning is raised during collection
        # Run with: pytest -W error::DeprecationWarning
        pass
```

##### STEP 2: GREEN - Update Configuration

Update `pyproject.toml`:

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]
cache_dir = ".cache/.pytest_cache"
# Remove: asyncio_mode = "auto"
```

**Run and verify:**
```bash
# Should pass with no warnings
uv run pytest tests/test_pytest_config.py -v -W error::DeprecationWarning
```

##### STEP 3: Verify Full Test Suite

```bash
# Run all tests
uv run pytest tests/ -v --tb=short

# Verify no deprecation warnings
uv run pytest tests/ -v -W error::DeprecationWarning

# Compare to baseline - should have same or more passing tests
uv run pytest tests/ -v --tb=no | grep -E "(PASSED|FAILED|ERROR)" | wc -l
```

##### STEP 4: Add Coverage Configuration

```toml
# pyproject.toml
[tool.coverage.run]
data_file = ".cache/.coverage"
branch = true
source = ["scout_mcp"]

[tool.coverage.report]
show_missing = true
fail_under = 80
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
```

##### STEP 5: REFACTOR - Generate Coverage Report

```bash
# Run with coverage
uv run pytest tests/ -v --cov=scout_mcp --cov-report=term-missing

# Generate HTML report
uv run pytest tests/ --cov=scout_mcp --cov-report=html

# Verify coverage meets threshold
uv run pytest tests/ --cov=scout_mcp --cov-fail-under=80
```

#### TDD Acceptance Criteria (All must be GREEN)
- [ ] `tests/test_pytest_config.py` - Async config tests pass
- [ ] `asyncio_mode = "auto"` replaced with `asyncio_default_fixture_loop_scope`
- [ ] All async tests run successfully without explicit markers
- [ ] No deprecation warnings: `pytest -W error::DeprecationWarning` passes
- [ ] Test count same or higher than baseline
- [ ] Coverage report generated with ≥80% coverage

---

## Batch 3: Security Features (Parallel - 3 Agents)

Execute after Batch 2 completes.

### Agent 8: scout_mcp-0wx - Implement API Key Authentication

**Files:** `scout_mcp/server.py`, `scout_mcp/middleware/auth.py` (NEW)
**Effort:** 4 hours

Based on [FastMCP Authentication docs](https://gofastmcp.com/servers/auth/authentication).

---

#### TDD Implementation Steps

##### STEP 1: RED - Write Failing Tests First

```python
# tests/test_auth_middleware.py
"""TDD: Tests for API key authentication - written BEFORE implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestAPIKeyValidation:
    """Test API key validation logic."""

    def test_validates_correct_key(self, monkeypatch):
        """Should accept valid API key."""
        monkeypatch.setenv("SCOUT_API_KEYS", "valid-key-123")

        from scout_mcp.middleware.auth import APIKeyMiddleware
        middleware = APIKeyMiddleware()

        assert middleware._validate_key("valid-key-123") is True

    def test_rejects_invalid_key(self, monkeypatch):
        """Should reject invalid API key."""
        monkeypatch.setenv("SCOUT_API_KEYS", "valid-key-123")

        from scout_mcp.middleware.auth import APIKeyMiddleware
        middleware = APIKeyMiddleware()

        assert middleware._validate_key("wrong-key") is False

    def test_supports_multiple_keys(self, monkeypatch):
        """Should accept any of multiple configured keys."""
        monkeypatch.setenv("SCOUT_API_KEYS", "key1,key2,key3")

        from scout_mcp.middleware.auth import APIKeyMiddleware
        middleware = APIKeyMiddleware()

        assert middleware._validate_key("key1") is True
        assert middleware._validate_key("key2") is True
        assert middleware._validate_key("key3") is True
        assert middleware._validate_key("key4") is False

    def test_uses_constant_time_comparison(self, monkeypatch):
        """Should use constant-time comparison to prevent timing attacks."""
        monkeypatch.setenv("SCOUT_API_KEYS", "secret-key")

        # Verify secrets.compare_digest is used
        with patch("scout_mcp.middleware.auth.secrets.compare_digest") as mock_compare:
            mock_compare.return_value = True

            from scout_mcp.middleware.auth import APIKeyMiddleware
            middleware = APIKeyMiddleware()
            middleware._validate_key("test-key")

            mock_compare.assert_called()


class TestAPIKeyMiddleware:
    """Test middleware request handling."""

    @pytest.fixture
    def middleware(self, monkeypatch):
        monkeypatch.setenv("SCOUT_API_KEYS", "valid-key")
        from scout_mcp.middleware.auth import APIKeyMiddleware
        return APIKeyMiddleware()

    @pytest.fixture
    def mock_request(self):
        request = MagicMock()
        request.url.path = "/mcp"
        request.client.host = "127.0.0.1"
        return request

    async def test_allows_valid_key(self, middleware, mock_request):
        """Should allow requests with valid API key."""
        mock_request.headers.get.return_value = "valid-key"
        call_next = AsyncMock(return_value="success")

        result = await middleware(mock_request, call_next)

        assert result == "success"
        call_next.assert_called_once()

    async def test_rejects_missing_key(self, middleware, mock_request):
        """Should reject requests without API key."""
        mock_request.headers.get.return_value = ""
        call_next = AsyncMock()

        result = await middleware(mock_request, call_next)

        assert result.status_code == 401
        call_next.assert_not_called()

    async def test_rejects_invalid_key(self, middleware, mock_request):
        """Should reject requests with invalid API key."""
        mock_request.headers.get.return_value = "wrong-key"
        call_next = AsyncMock()

        result = await middleware(mock_request, call_next)

        assert result.status_code == 401
        call_next.assert_not_called()

    async def test_bypasses_health_endpoint(self, middleware, mock_request):
        """Should bypass auth for /health endpoint."""
        mock_request.url.path = "/health"
        mock_request.headers.get.return_value = ""  # No key
        call_next = AsyncMock(return_value="healthy")

        result = await middleware(mock_request, call_next)

        assert result == "healthy"
        call_next.assert_called_once()

    async def test_disabled_when_no_keys_configured(self, monkeypatch):
        """Should skip auth when SCOUT_API_KEYS not set."""
        monkeypatch.delenv("SCOUT_API_KEYS", raising=False)

        from scout_mcp.middleware.auth import APIKeyMiddleware
        middleware = APIKeyMiddleware()

        mock_request = MagicMock()
        mock_request.url.path = "/mcp"
        mock_request.headers.get.return_value = ""
        call_next = AsyncMock(return_value="allowed")

        result = await middleware(mock_request, call_next)

        assert result == "allowed"
```

**Run and verify RED:**
```bash
uv run pytest tests/test_auth_middleware.py -v
# Expected: ModuleNotFoundError - tests FAIL
```

##### STEP 2: GREEN - Implement Auth Middleware

Create `scout_mcp/middleware/auth.py`:
```python
# scout_mcp/middleware/auth.py (NEW FILE)
"""API key authentication middleware for Scout MCP."""

import hashlib
import hmac
import logging
import os
import secrets
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class APIKeyAuthMiddleware:
    """Middleware to validate API keys in request headers.

    Requires X-API-Key header with valid key from SCOUT_API_KEYS env var.

    Environment Variables:
        SCOUT_API_KEYS: Comma-separated list of valid API keys
        SCOUT_AUTH_ENABLED: Set to "false" to disable auth (default: true if keys set)
    """

    def __init__(self) -> None:
        self._api_keys: set[str] = set()
        self._auth_enabled = False
        self._load_keys()

    def _load_keys(self) -> None:
        """Load API keys from environment."""
        keys_str = os.getenv("SCOUT_API_KEYS", "").strip()
        auth_enabled = os.getenv("SCOUT_AUTH_ENABLED", "").lower()

        if keys_str:
            self._api_keys = {k.strip() for k in keys_str.split(",") if k.strip()}
            self._auth_enabled = auth_enabled != "false"

            if self._auth_enabled:
                logger.info(
                    "API key authentication enabled (%d key(s) configured)",
                    len(self._api_keys),
                )
            else:
                logger.warning(
                    "API key authentication DISABLED via SCOUT_AUTH_ENABLED=false"
                )
        else:
            self._auth_enabled = False
            logger.warning(
                "No API keys configured (SCOUT_API_KEYS not set). "
                "Authentication disabled - server is open to all requests!"
            )

    def _validate_key(self, provided_key: str) -> bool:
        """Validate API key using constant-time comparison."""
        for valid_key in self._api_keys:
            if secrets.compare_digest(provided_key, valid_key):
                return True
        return False

    async def __call__(
        self,
        request: Request,
        call_next: Any,
    ) -> Any:
        """Validate API key before processing request."""
        # Skip auth for health checks
        if request.url.path == "/health":
            return await call_next(request)

        # Skip if auth disabled
        if not self._auth_enabled:
            return await call_next(request)

        # Get API key from header
        api_key = request.headers.get("X-API-Key", "")

        if not api_key:
            logger.warning(
                "Request rejected: missing X-API-Key header from %s",
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                {"error": "Missing X-API-Key header"},
                status_code=401,
            )

        if not self._validate_key(api_key):
            logger.warning(
                "Request rejected: invalid API key from %s",
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                {"error": "Invalid API key"},
                status_code=401,
            )

        # Key valid - proceed
        logger.debug("API key validated for request to %s", request.url.path)
        return await call_next(request)
```

2. **Note: FastMCP uses MCP middleware, not ASGI middleware**

Actually, FastMCP's middleware is different from Starlette middleware. Let me revise:

```python
# scout_mcp/middleware/auth.py (REVISED)
"""API key authentication for Scout MCP.

Note: This implements HTTP-level authentication since FastMCP's
MCP middleware operates at the protocol level, not HTTP level.
"""

import logging
import os
import secrets
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """ASGI middleware for API key authentication."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Skip health checks
        if request.url.path == "/health":
            return await call_next(request)

        # Check if auth is enabled
        api_keys_str = os.getenv("SCOUT_API_KEYS", "").strip()
        if not api_keys_str:
            return await call_next(request)

        api_keys = {k.strip() for k in api_keys_str.split(",") if k.strip()}

        # Get key from header
        provided_key = request.headers.get("X-API-Key", "")

        if not provided_key:
            return JSONResponse(
                {"error": "Missing X-API-Key header"},
                status_code=401,
            )

        # Constant-time comparison
        valid = any(
            secrets.compare_digest(provided_key, key)
            for key in api_keys
        )

        if not valid:
            return JSONResponse(
                {"error": "Invalid API key"},
                status_code=401,
            )

        return await call_next(request)
```

3. **Update server.py to add ASGI middleware:**
```python
# scout_mcp/server.py - In create_server()

def create_server() -> FastMCP:
    """Create and configure the MCP server."""
    server = FastMCP(
        "scout_mcp",
        lifespan=app_lifespan,
    )

    configure_middleware(server)

    # Add ASGI-level auth middleware if API keys configured
    if os.getenv("SCOUT_API_KEYS"):
        from scout_mcp.middleware.auth import APIKeyMiddleware
        # Note: Need to access underlying Starlette app
        # This may require FastMCP customization
        logger.info("API key authentication enabled")

    # ... rest of setup ...
```

4. **Update CLAUDE.md:**
```markdown
### Authentication

Set `SCOUT_API_KEYS` to enable API key authentication:

```bash
# Single key
export SCOUT_API_KEYS="your-secret-key-here"

# Multiple keys (comma-separated)
export SCOUT_API_KEYS="key1,key2,key3"
```

Clients must include the key in the `X-API-Key` header.

**MCP Client Configuration (with auth):**
```json
{
  "mcpServers": {
    "scout_mcp": {
      "url": "http://127.0.0.1:8000/mcp",
      "headers": {
        "X-API-Key": "your-secret-key-here"
      }
    }
  }
}
```
```

**Run and verify GREEN:**
```bash
uv run pytest tests/test_auth_middleware.py -v
# Expected: All tests PASS
```

##### STEP 3: Integration Test with Server

```python
# tests/test_auth_integration.py
"""TDD: Verify auth middleware integrates with server."""

import pytest
from unittest.mock import patch


class TestAuthIntegration:
    """Test auth middleware integration."""

    async def test_server_logs_auth_enabled(self, monkeypatch):
        """Server should log when auth is enabled."""
        monkeypatch.setenv("SCOUT_API_KEYS", "test-key")

        with patch("scout_mcp.server.logger") as mock_logger:
            from scout_mcp.server import create_server
            # Importing should configure auth
            # Verify log message

            # Check for auth-related log call
            log_messages = [str(c) for c in mock_logger.info.call_args_list]
            # At least one should mention auth or API key
```

##### STEP 4: GREEN - Update server.py

Integrate auth middleware with server.py.

##### STEP 5: REFACTOR - Verify and Document

```bash
uv run pytest tests/ -v
uv run mypy scout_mcp/
```

#### TDD Acceptance Criteria (All must be GREEN)
- [ ] `tests/test_auth_middleware.py` - All unit tests pass (RED→GREEN)
- [ ] `tests/test_auth_integration.py` - Server integration tests pass
- [ ] Auth middleware created at `scout_mcp/middleware/auth.py`
- [ ] Auth enabled when SCOUT_API_KEYS is set
- [ ] Health endpoint bypasses auth
- [ ] Invalid/missing keys return 401
- [ ] Constant-time comparison used (`secrets.compare_digest`)
- [ ] Documentation updated in CLAUDE.md

---

### Agent 9: scout_mcp-drx - Add Rate Limiting

**Files:** `scout_mcp/middleware/ratelimit.py` (NEW)
**Effort:** 3 hours

---

#### TDD Implementation Steps

##### STEP 1: RED - Write Failing Tests First

```python
# tests/test_ratelimit_middleware.py
"""TDD: Tests for rate limiting - written BEFORE implementation."""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock


class TestRateLimitBucket:
    """Test token bucket algorithm."""

    def test_consume_with_tokens_available(self):
        """Should consume token when available."""
        from scout_mcp.middleware.ratelimit import RateLimitBucket

        bucket = RateLimitBucket(tokens=5.0)
        assert bucket.consume(1.0, 10.0) is True
        assert bucket.tokens == 4.0

    def test_consume_when_empty(self):
        """Should reject when no tokens available."""
        from scout_mcp.middleware.ratelimit import RateLimitBucket

        bucket = RateLimitBucket(tokens=0.0)
        assert bucket.consume(1.0, 10.0) is False

    def test_tokens_refill_over_time(self):
        """Should refill tokens based on elapsed time."""
        from scout_mcp.middleware.ratelimit import RateLimitBucket

        bucket = RateLimitBucket(tokens=0.0)
        # Simulate 5 seconds passing
        bucket.last_update = time.monotonic() - 5.0
        # With 1 token/second, should now have 5 tokens
        assert bucket.consume(1.0, 10.0) is True

    def test_tokens_capped_at_max(self):
        """Should not exceed max_tokens."""
        from scout_mcp.middleware.ratelimit import RateLimitBucket

        bucket = RateLimitBucket(tokens=0.0)
        # Simulate 100 seconds passing with max=10
        bucket.last_update = time.monotonic() - 100.0
        bucket.consume(1.0, 10.0)
        # Should be capped at max (10) minus 1 consumed = 9
        assert bucket.tokens <= 9.0


class TestRateLimitMiddleware:
    """Test rate limit middleware."""

    @pytest.fixture
    def middleware(self, monkeypatch):
        monkeypatch.setenv("SCOUT_RATE_LIMIT_PER_MINUTE", "60")
        monkeypatch.setenv("SCOUT_RATE_LIMIT_BURST", "5")
        from scout_mcp.middleware.ratelimit import RateLimitMiddleware
        return RateLimitMiddleware()

    @pytest.fixture
    def mock_request(self):
        request = MagicMock()
        request.url.path = "/mcp"
        request.client.host = "127.0.0.1"
        request.headers.get.return_value = None
        return request

    async def test_allows_normal_traffic(self, middleware, mock_request):
        """Should allow requests within rate limit."""
        call_next = AsyncMock(return_value="response")

        result = await middleware(mock_request, call_next)

        assert result == "response"
        call_next.assert_called_once()

    async def test_blocks_after_burst_exceeded(self, middleware, mock_request):
        """Should block after burst limit exceeded."""
        call_next = AsyncMock(return_value="response")

        # Exhaust burst (5 requests)
        for _ in range(5):
            await middleware(mock_request, call_next)

        # Next request should be blocked
        result = await middleware(mock_request, call_next)

        assert result.status_code == 429

    async def test_returns_retry_after_header(self, middleware, mock_request):
        """Should include Retry-After header on 429."""
        call_next = AsyncMock(return_value="response")

        # Exhaust burst
        for _ in range(5):
            await middleware(mock_request, call_next)

        result = await middleware(mock_request, call_next)

        assert "Retry-After" in result.headers

    async def test_bypasses_health_endpoint(self, middleware, mock_request):
        """Should bypass rate limit for /health."""
        mock_request.url.path = "/health"
        call_next = AsyncMock(return_value="healthy")

        # Even with burst exceeded, health should pass
        for _ in range(10):
            result = await middleware(mock_request, call_next)
            assert result == "healthy"

    async def test_per_client_tracking(self, middleware):
        """Should track rate limits per client IP."""
        call_next = AsyncMock(return_value="response")

        # Client 1 exhausts their burst
        client1 = MagicMock()
        client1.url.path = "/mcp"
        client1.client.host = "192.168.1.1"
        client1.headers.get.return_value = None

        for _ in range(5):
            await middleware(client1, call_next)

        # Client 1 should be blocked
        result = await middleware(client1, call_next)
        assert result.status_code == 429

        # Client 2 should still work
        client2 = MagicMock()
        client2.url.path = "/mcp"
        client2.client.host = "192.168.1.2"
        client2.headers.get.return_value = None

        result = await middleware(client2, call_next)
        assert result == "response"

    async def test_disabled_when_rate_zero(self, monkeypatch):
        """Should skip rate limiting when rate is 0."""
        monkeypatch.setenv("SCOUT_RATE_LIMIT_PER_MINUTE", "0")

        from scout_mcp.middleware.ratelimit import RateLimitMiddleware
        middleware = RateLimitMiddleware()

        mock_request = MagicMock()
        mock_request.url.path = "/mcp"
        mock_request.client.host = "127.0.0.1"
        call_next = AsyncMock(return_value="allowed")

        # Should allow unlimited requests
        for _ in range(100):
            result = await middleware(mock_request, call_next)
            assert result == "allowed"
```

**Run and verify RED:**
```bash
uv run pytest tests/test_ratelimit_middleware.py -v
# Expected: ModuleNotFoundError - tests FAIL
```

##### STEP 2: GREEN - Implement Rate Limit Middleware

Create `scout_mcp/middleware/ratelimit.py`:
```python
# scout_mcp/middleware/ratelimit.py (NEW FILE)
"""Rate limiting middleware for Scout MCP."""

import asyncio
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting."""
    tokens: float = 0.0
    last_update: float = field(default_factory=time.monotonic)

    def consume(self, tokens_per_second: float, max_tokens: float) -> bool:
        """Try to consume a token. Returns True if allowed."""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.last_update = now

        # Refill tokens
        self.tokens = min(max_tokens, self.tokens + elapsed * tokens_per_second)

        # Try to consume
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimitMiddleware:
    """Simple in-memory rate limiting.

    Uses token bucket algorithm per client IP.

    Environment Variables:
        SCOUT_RATE_LIMIT_PER_MINUTE: Requests per minute per client (default: 60)
        SCOUT_RATE_LIMIT_BURST: Max burst size (default: 10)
    """

    def __init__(self) -> None:
        self._buckets: dict[str, RateLimitBucket] = defaultdict(RateLimitBucket)
        self._lock = asyncio.Lock()

        # Load config
        self._rate_per_minute = int(os.getenv("SCOUT_RATE_LIMIT_PER_MINUTE", "60"))
        self._burst = int(os.getenv("SCOUT_RATE_LIMIT_BURST", "10"))
        self._tokens_per_second = self._rate_per_minute / 60.0

        # Initialize buckets with burst capacity
        self._enabled = self._rate_per_minute > 0

        if self._enabled:
            logger.info(
                "Rate limiting enabled: %d req/min, burst=%d",
                self._rate_per_minute,
                self._burst,
            )
        else:
            logger.info("Rate limiting disabled")

    def _get_client_key(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Use X-Forwarded-For if behind proxy, else client IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def __call__(
        self,
        request: Request,
        call_next: Any,
    ) -> Any:
        """Apply rate limiting."""
        # Skip if disabled
        if not self._enabled:
            return await call_next(request)

        # Skip health checks
        if request.url.path == "/health":
            return await call_next(request)

        client_key = self._get_client_key(request)

        async with self._lock:
            bucket = self._buckets[client_key]
            allowed = bucket.consume(self._tokens_per_second, self._burst)

        if not allowed:
            logger.warning(
                "Rate limit exceeded for client %s on %s",
                client_key,
                request.url.path,
            )
            return JSONResponse(
                {
                    "error": "Rate limit exceeded",
                    "retry_after": int(60 / self._rate_per_minute),
                },
                status_code=429,
                headers={
                    "Retry-After": str(int(60 / self._rate_per_minute)),
                },
            )

        return await call_next(request)
```

2. **Add cleanup for stale buckets:**
```python
# Add to RateLimitMiddleware

async def cleanup_stale_buckets(self, max_age_seconds: int = 3600) -> int:
    """Remove buckets that haven't been used recently."""
    async with self._lock:
        now = time.monotonic()
        stale = [
            key for key, bucket in self._buckets.items()
            if now - bucket.last_update > max_age_seconds
        ]
        for key in stale:
            del self._buckets[key]
        return len(stale)
```

3. **Add tests:**
```python
# tests/test_middleware/test_ratelimit.py (NEW FILE)
"""Tests for rate limiting middleware."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from scout_mcp.middleware.ratelimit import RateLimitMiddleware, RateLimitBucket


class TestRateLimitBucket:
    """Test token bucket algorithm."""

    def test_consume_success(self):
        bucket = RateLimitBucket(tokens=5.0)
        assert bucket.consume(1.0, 10.0) is True
        assert bucket.tokens == 4.0

    def test_consume_empty(self):
        bucket = RateLimitBucket(tokens=0.0)
        assert bucket.consume(1.0, 10.0) is False

    def test_consume_refill(self):
        bucket = RateLimitBucket(tokens=0.0)
        # Simulate time passing
        import time
        bucket.last_update = time.monotonic() - 5.0  # 5 seconds ago
        assert bucket.consume(1.0, 10.0) is True  # Should have 5 tokens


class TestRateLimitMiddleware:
    """Test rate limiting middleware."""

    @pytest.fixture
    def middleware(self, monkeypatch):
        monkeypatch.setenv("SCOUT_RATE_LIMIT_PER_MINUTE", "60")
        monkeypatch.setenv("SCOUT_RATE_LIMIT_BURST", "5")
        return RateLimitMiddleware()

    async def test_allows_normal_traffic(self, middleware):
        request = MagicMock()
        request.url.path = "/mcp"
        request.client.host = "127.0.0.1"
        request.headers.get.return_value = None

        call_next = AsyncMock(return_value="response")

        result = await middleware(request, call_next)

        assert result == "response"
        call_next.assert_called_once()

    async def test_blocks_burst_exceeded(self, middleware):
        request = MagicMock()
        request.url.path = "/mcp"
        request.client.host = "127.0.0.1"
        request.headers.get.return_value = None

        call_next = AsyncMock(return_value="response")

        # Exhaust burst
        for _ in range(5):
            await middleware(request, call_next)

        # Next should be blocked
        result = await middleware(request, call_next)

        assert result.status_code == 429
```

**Run and verify GREEN:**
```bash
uv run pytest tests/test_ratelimit_middleware.py -v
# Expected: All tests PASS
```

##### STEP 3: REFACTOR - Add Stale Bucket Cleanup

```python
# Add cleanup method and test
async def test_cleanup_stale_buckets(self):
    """Should remove buckets not used recently."""
    from scout_mcp.middleware.ratelimit import RateLimitMiddleware
    middleware = RateLimitMiddleware()

    # Add some buckets
    middleware._buckets["old-client"] = RateLimitBucket(tokens=5.0)
    middleware._buckets["old-client"].last_update = time.monotonic() - 7200  # 2 hours ago

    removed = await middleware.cleanup_stale_buckets(max_age_seconds=3600)

    assert removed == 1
    assert "old-client" not in middleware._buckets
```

##### STEP 4: Final Verification

```bash
uv run pytest tests/ -v
uv run mypy scout_mcp/
```

#### TDD Acceptance Criteria (All must be GREEN)
- [ ] `tests/test_ratelimit_middleware.py` - All unit tests pass (RED→GREEN)
- [ ] Rate limiting middleware created at `scout_mcp/middleware/ratelimit.py`
- [ ] Token bucket algorithm correctly implemented
- [ ] Configurable via `SCOUT_RATE_LIMIT_PER_MINUTE` and `SCOUT_RATE_LIMIT_BURST`
- [ ] Health endpoint bypasses rate limit
- [ ] 429 response with Retry-After header
- [ ] Per-client tracking by IP
- [ ] Stale bucket cleanup implemented

---

### Agent 10: scout_mcp-6ce - Add Security Documentation

**Files:** `README.md`, `SECURITY.md` (NEW)
**Effort:** 2 hours
**Depends on:** scout_mcp-0wx, scout_mcp-7di

---

#### TDD Implementation Steps

Note: For documentation, TDD means defining acceptance criteria first, then writing docs to meet them.

##### STEP 1: RED - Define Documentation Requirements

Create a test that validates documentation exists and contains required sections:

```python
# tests/test_security_docs.py
"""TDD: Verify security documentation exists and is complete."""

import pytest
from pathlib import Path


class TestSecurityDocumentation:
    """Test security documentation completeness."""

    @pytest.fixture
    def security_md(self):
        path = Path("SECURITY.md")
        assert path.exists(), "SECURITY.md must exist"
        return path.read_text()

    @pytest.fixture
    def readme_md(self):
        path = Path("README.md")
        assert path.exists(), "README.md must exist"
        return path.read_text()

    def test_security_md_has_supported_versions(self, security_md):
        """SECURITY.md should list supported versions."""
        assert "Supported Versions" in security_md

    def test_security_md_has_reporting_section(self, security_md):
        """SECURITY.md should explain how to report vulnerabilities."""
        assert "Reporting" in security_md or "report" in security_md.lower()

    def test_security_md_has_trust_boundaries(self, security_md):
        """SECURITY.md should document trust boundaries."""
        assert "Trust" in security_md or "boundary" in security_md.lower()

    def test_security_md_has_feature_table(self, security_md):
        """SECURITY.md should have security features table."""
        assert "API Key" in security_md
        assert "Rate Limit" in security_md
        assert "Host Key" in security_md

    def test_security_md_has_recommendations(self, security_md):
        """SECURITY.md should have security recommendations."""
        assert "Recommendation" in security_md or "recommend" in security_md.lower()

    def test_security_md_documents_environment_vars(self, security_md):
        """SECURITY.md should document security-related env vars."""
        assert "SCOUT_API_KEYS" in security_md
        assert "SCOUT_KNOWN_HOSTS" in security_md

    def test_readme_has_security_section(self, readme_md):
        """README.md should have a security section."""
        assert "## Security" in readme_md or "### Security" in readme_md

    def test_readme_has_quick_checklist(self, readme_md):
        """README.md should have security checklist."""
        assert "checklist" in readme_md.lower() or "[ ]" in readme_md

    def test_readme_links_to_security_md(self, readme_md):
        """README.md should link to SECURITY.md."""
        assert "SECURITY.md" in readme_md
```

**Run and verify RED:**
```bash
uv run pytest tests/test_security_docs.py -v
# Expected: Tests FAIL (SECURITY.md doesn't exist)
```

##### STEP 2: GREEN - Create Documentation

1. **Create SECURITY.md:**
```markdown
# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting Vulnerabilities

Please report security vulnerabilities by emailing [security contact].

## Security Model

Scout MCP provides SSH access to remote hosts. It is designed for trusted
environments where the MCP client is authenticated.

### Trust Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                     MCP Client                               │
│  (Claude Desktop, IDE Extension, etc.)                       │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ HTTP/SSE (API Key auth)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Scout MCP Server                          │
│  - Validates API keys                                        │
│  - Rate limits requests                                      │
│  - Validates paths                                           │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ SSH (Key-based auth, host verification)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Remote SSH Hosts                          │
│  - File system access controls                               │
│  - Command execution permissions                             │
│  - User-based authorization                                  │
└─────────────────────────────────────────────────────────────┘
```

### Security Features

| Feature | Status | Configuration |
|---------|--------|---------------|
| API Key Authentication | Optional | `SCOUT_API_KEYS` |
| Rate Limiting | Optional | `SCOUT_RATE_LIMIT_PER_MINUTE` |
| SSH Host Key Verification | Default On | `SCOUT_KNOWN_HOSTS` |
| Path Traversal Protection | Default On | Built-in |
| Command Injection Protection | Default On | Uses shlex.quote() |

### Security Recommendations

1. **Always enable API key authentication in production:**
   ```bash
   export SCOUT_API_KEYS="$(openssl rand -hex 32)"
   ```

2. **Bind to localhost unless network access needed:**
   ```bash
   export SCOUT_HTTP_HOST="127.0.0.1"
   ```

3. **Use SSH key-based authentication only** (no passwords)

4. **Limit SSH user permissions** on remote hosts

5. **Review known_hosts** before deployment:
   ```bash
   ssh-keyscan your-host >> ~/.ssh/known_hosts
   ```

### Known Limitations

- STDIO transport relies on local process security (no MCP-level auth)
- Command execution allows arbitrary shell commands (by design)
- File access is limited only by SSH user permissions

## Vulnerability Disclosure

Responsibly disclosed vulnerabilities will be addressed within:
- Critical: 24 hours
- High: 72 hours
- Medium: 1 week
- Low: Next release
```

2. **Update README.md with security section:**
```markdown
## Security

> **Warning**: Scout MCP provides remote shell access. Deploy with care.

### Quick Security Checklist

- [ ] Set `SCOUT_API_KEYS` to enable authentication
- [ ] Bind to `127.0.0.1` unless network access required
- [ ] Verify SSH host keys are in `~/.ssh/known_hosts`
- [ ] Use SSH keys, not passwords
- [ ] Limit SSH user permissions on remote hosts

### Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `SCOUT_API_KEYS` | (none) | Comma-separated API keys for auth |
| `SCOUT_HTTP_HOST` | 0.0.0.0 | Bind address |
| `SCOUT_KNOWN_HOSTS` | ~/.ssh/known_hosts | SSH host verification |
| `SCOUT_RATE_LIMIT_PER_MINUTE` | 60 | Rate limit per client |

See [SECURITY.md](SECURITY.md) for full security documentation.
```

#### Acceptance Criteria
- [ ] SECURITY.md created with threat model
- [ ] README.md updated with security section
- [ ] Configuration table complete
- [ ] Security checklist included
- [ ] Trust boundary diagram

---

## Batch 4: Performance (Sequential - 2 Agents)

Execute after Batch 3 completes. These are sequential due to dependencies.

### Agent 11: scout_mcp-kvk - Fix Global Lock Performance

**Files:** `scout_mcp/services/pool.py`
**Effort:** 3 hours
**Depends on:** scout_mcp-2rf (connection helper)

#### Current State
```python
# pool.py:25
self._lock = asyncio.Lock()  # Single lock for ALL hosts

# pool.py:34 - Holds lock during network I/O!
async with self._lock:
    # ... includes asyncssh.connect() call
```

---

#### TDD Implementation Steps

##### STEP 1: RED - Write Failing Tests First

Create `tests/test_pool_concurrency.py` with tests that verify concurrent access:

```python
# tests/test_pool_concurrency.py
"""TDD: Concurrency tests for connection pool - written BEFORE implementation."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestPerHostLocking:
    """Test that pool uses per-host locking instead of global lock."""

    @pytest.fixture
    def mock_asyncssh(self):
        with patch("scout_mcp.services.pool.asyncssh") as mock:
            # Simulate connection delay to expose locking issues
            async def slow_connect(*args, **kwargs):
                await asyncio.sleep(0.1)
                return MagicMock()
            mock.connect = slow_connect
            yield mock

    async def test_concurrent_different_hosts_parallel(self, mock_asyncssh):
        """Concurrent connections to DIFFERENT hosts should run in parallel."""
        from scout_mcp.services.pool import ConnectionPool

        pool = ConnectionPool(idle_timeout=60)

        host1 = MagicMock()
        host1.name = "host1"
        host1.hostname = "h1"
        host1.port = 22
        host1.user = "u"
        host1.identity_file = None

        host2 = MagicMock()
        host2.name = "host2"
        host2.hostname = "h2"
        host2.port = 22
        host2.user = "u"
        host2.identity_file = None

        # Both connections should complete in ~0.1s (parallel), not ~0.2s (serial)
        start = asyncio.get_event_loop().time()
        await asyncio.gather(
            pool.get_connection(host1),
            pool.get_connection(host2),
        )
        elapsed = asyncio.get_event_loop().time() - start

        # If global lock: ~0.2s (serial)
        # If per-host lock: ~0.1s (parallel)
        assert elapsed < 0.15, f"Took {elapsed:.2f}s - likely using global lock (should be parallel)"

    async def test_concurrent_same_host_serialized(self, mock_asyncssh):
        """Concurrent connections to SAME host should serialize correctly."""
        from scout_mcp.services.pool import ConnectionPool

        pool = ConnectionPool(idle_timeout=60)

        host = MagicMock()
        host.name = "host1"
        host.hostname = "h1"
        host.port = 22
        host.user = "u"
        host.identity_file = None

        # Both requests for same host - second should reuse first's connection
        results = await asyncio.gather(
            pool.get_connection(host),
            pool.get_connection(host),
        )

        # Should only create ONE connection (second reuses first)
        assert pool.pool_size == 1


class TestHostLockManagement:
    """Test per-host lock creation and management."""

    async def test_get_host_lock_creates_lock(self):
        """Should create new lock for unknown host."""
        from scout_mcp.services.pool import ConnectionPool

        pool = ConnectionPool(idle_timeout=60)

        # Initially no locks
        assert len(pool._host_locks) == 0

        # Get lock for new host
        lock = await pool._get_host_lock("new-host")

        assert lock is not None
        assert "new-host" in pool._host_locks

    async def test_get_host_lock_reuses_existing(self):
        """Should reuse existing lock for known host."""
        from scout_mcp.services.pool import ConnectionPool

        pool = ConnectionPool(idle_timeout=60)

        # Get lock twice for same host
        lock1 = await pool._get_host_lock("test-host")
        lock2 = await pool._get_host_lock("test-host")

        # Should be the exact same lock object
        assert lock1 is lock2

    async def test_meta_lock_only_protects_lock_dict(self):
        """Meta-lock should only protect _host_locks dictionary, not I/O."""
        from scout_mcp.services.pool import ConnectionPool

        pool = ConnectionPool(idle_timeout=60)

        # Getting a host lock should be fast (no I/O)
        start = asyncio.get_event_loop().time()
        for i in range(100):
            await pool._get_host_lock(f"host-{i}")
        elapsed = asyncio.get_event_loop().time() - start

        # Should be very fast (< 0.1s for 100 lock creations)
        assert elapsed < 0.1, f"Lock creation too slow: {elapsed:.2f}s"


class TestCleanupWithPerHostLocks:
    """Test cleanup operations with per-host locking."""

    async def test_cleanup_acquires_correct_locks(self):
        """Cleanup should acquire per-host locks, not global lock."""
        from scout_mcp.services.pool import ConnectionPool

        with patch("scout_mcp.services.pool.asyncssh") as mock:
            mock.connect = AsyncMock(return_value=MagicMock())

            pool = ConnectionPool(idle_timeout=60)

            # Create some connections
            for i in range(3):
                host = MagicMock()
                host.name = f"host{i}"
                host.hostname = f"h{i}"
                host.port = 22
                host.user = "u"
                host.identity_file = None
                await pool.get_connection(host)

            assert pool.pool_size == 3

            # Close all should work without deadlock
            await pool.close_all()

            assert pool.pool_size == 0


class TestRemoveConnectionWithPerHostLocks:
    """Test remove_connection with per-host locking."""

    async def test_remove_connection_uses_host_lock(self):
        """remove_connection should use per-host lock."""
        from scout_mcp.services.pool import ConnectionPool

        with patch("scout_mcp.services.pool.asyncssh") as mock:
            mock_conn = MagicMock()
            mock.connect = AsyncMock(return_value=mock_conn)

            pool = ConnectionPool(idle_timeout=60)

            host = MagicMock()
            host.name = "test-host"
            host.hostname = "h1"
            host.port = 22
            host.user = "u"
            host.identity_file = None

            await pool.get_connection(host)
            assert pool.pool_size == 1

            # Remove should work
            await pool.remove_connection("test-host")
            assert pool.pool_size == 0
            mock_conn.close.assert_called_once()
```

**Run and verify RED:**
```bash
uv run pytest tests/test_pool_concurrency.py -v
# Expected: Tests FAIL because _get_host_lock doesn't exist, or timing tests fail
```

##### STEP 2: GREEN - Implement Per-Host Locking

Update `scout_mcp/services/pool.py`:
```python
# scout_mcp/services/pool.py

class ConnectionPool:
    """SSH connection pool with per-host locking."""

    def __init__(self, idle_timeout: int = 60) -> None:
        self.idle_timeout = idle_timeout
        self._connections: dict[str, PooledConnection] = {}
        self._host_locks: dict[str, asyncio.Lock] = {}
        self._meta_lock = asyncio.Lock()  # Only for accessing _host_locks
        self._cleanup_task: asyncio.Task[Any] | None = None
        # ... rest of init ...

    async def _get_host_lock(self, host_name: str) -> asyncio.Lock:
        """Get or create lock for a specific host."""
        async with self._meta_lock:
            if host_name not in self._host_locks:
                self._host_locks[host_name] = asyncio.Lock()
            return self._host_locks[host_name]

    async def get_connection(self, host: "SSHHost") -> asyncssh.SSHClientConnection:
        """Get or create a connection to the host."""
        host_lock = await self._get_host_lock(host.name)

        async with host_lock:
            pooled = self._connections.get(host.name)

            # Return existing if valid
            if pooled and not pooled.is_stale:
                pooled.touch()
                logger.debug(
                    "Reusing connection to %s (pool_size=%d)",
                    host.name,
                    len(self._connections),
                )
                return pooled.connection

            # Create new connection (outside meta lock - only host lock held)
            logger.info(
                "Opening SSH connection to %s (%s@%s:%d)",
                host.name,
                host.user,
                host.hostname,
                host.port,
            )
            client_keys = [host.identity_file] if host.identity_file else None
            conn = await asyncssh.connect(
                host.hostname,
                port=host.port,
                username=host.user,
                known_hosts=self._known_hosts,
                client_keys=client_keys,
            )

            self._connections[host.name] = PooledConnection(connection=conn)
            logger.info(
                "SSH connection established to %s (pool_size=%d)",
                host.name,
                len(self._connections),
            )

            # Start cleanup task if needed
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._cleanup_loop())

            return conn

    async def _cleanup_idle(self) -> None:
        """Close connections that have been idle too long."""
        # Get snapshot of hosts to check
        async with self._meta_lock:
            hosts_to_check = list(self._connections.keys())

        cutoff = datetime.now() - timedelta(seconds=self.idle_timeout)

        for host_name in hosts_to_check:
            host_lock = await self._get_host_lock(host_name)
            async with host_lock:
                pooled = self._connections.get(host_name)
                if pooled and (pooled.last_used < cutoff or pooled.is_stale):
                    reason = "stale" if pooled.is_stale else "idle"
                    logger.info("Closing %s connection to %s", reason, host_name)
                    pooled.connection.close()
                    del self._connections[host_name]

    async def remove_connection(self, host_name: str) -> None:
        """Remove a specific connection from the pool."""
        host_lock = await self._get_host_lock(host_name)
        async with host_lock:
            if host_name in self._connections:
                logger.info("Removing connection to %s", host_name)
                pooled = self._connections[host_name]
                pooled.connection.close()
                del self._connections[host_name]

    async def close_all(self) -> None:
        """Close all connections."""
        # Get all host locks first
        async with self._meta_lock:
            host_names = list(self._connections.keys())

        for host_name in host_names:
            await self.remove_connection(host_name)

        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
```

**Run and verify GREEN:**
```bash
uv run pytest tests/test_pool_concurrency.py -v
# Expected: All tests PASS
```

##### STEP 3: REFACTOR - Verify Performance and Clean Up

1. **Run full test suite:**
```bash
uv run pytest tests/ -v
```

2. **Type check:**
```bash
uv run mypy scout_mcp/
```

3. **Performance verification test:**
```python
# Add to tests/test_pool_concurrency.py

class TestPerformanceVerification:
    """Verify performance improvements from per-host locking."""

    async def test_ten_concurrent_hosts(self):
        """10 concurrent connections to different hosts should complete quickly."""
        from scout_mcp.services.pool import ConnectionPool

        with patch("scout_mcp.services.pool.asyncssh") as mock:
            async def slow_connect(*args, **kwargs):
                await asyncio.sleep(0.05)  # 50ms per connection
                return MagicMock()
            mock.connect = slow_connect

            pool = ConnectionPool(idle_timeout=60)

            hosts = []
            for i in range(10):
                host = MagicMock()
                host.name = f"host{i}"
                host.hostname = f"h{i}"
                host.port = 22
                host.user = "u"
                host.identity_file = None
                hosts.append(host)

            # With global lock: 10 * 50ms = 500ms
            # With per-host lock: ~50ms (all parallel)
            start = asyncio.get_event_loop().time()
            await asyncio.gather(*[pool.get_connection(h) for h in hosts])
            elapsed = asyncio.get_event_loop().time() - start

            # Should be < 100ms (parallel), not > 400ms (serial)
            assert elapsed < 0.1, f"10 hosts took {elapsed:.3f}s - should be parallel"
            assert pool.pool_size == 10
```

#### TDD Acceptance Criteria (All must be GREEN)
- [ ] `tests/test_pool_concurrency.py` - All concurrency tests pass (RED→GREEN)
- [ ] Per-host locking implemented with `_host_locks` dict
- [ ] `_get_host_lock()` method creates/retrieves per-host locks
- [ ] Meta-lock (`_meta_lock`) only protects `_host_locks` dictionary
- [ ] Network I/O (asyncssh.connect) NOT under meta-lock
- [ ] Concurrent requests to different hosts run in parallel
- [ ] Concurrent requests to same host serialize correctly
- [ ] Cleanup and remove operations use per-host locks
- [ ] Full test suite passes: `uv run pytest tests/ -v`
- [ ] Type check passes: `uv run mypy scout_mcp/`

---

### Agent 12: scout_mcp-82l - Add Pool Size Limits

**Files:** `scout_mcp/services/pool.py`, `scout_mcp/config.py`
**Effort:** 3 hours
**Depends on:** scout_mcp-kvk (per-host locks)

---

#### TDD Implementation Steps

##### STEP 1: RED - Write Failing Tests First

Create `tests/test_pool_limits.py` with tests for size limits and LRU eviction:

```python
# tests/test_pool_limits.py
"""TDD: Tests for connection pool size limits - written BEFORE implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestPoolSizeConfiguration:
    """Test pool size configuration via environment."""

    def test_default_max_pool_size(self, monkeypatch):
        """Should default to 100 connections."""
        monkeypatch.delenv("SCOUT_MAX_POOL_SIZE", raising=False)

        from scout_mcp.config import Config
        config = Config()

        assert config.max_pool_size == 100

    def test_custom_max_pool_size(self, monkeypatch):
        """Should read max pool size from environment."""
        monkeypatch.setenv("SCOUT_MAX_POOL_SIZE", "50")

        from scout_mcp.config import Config
        config = Config()

        assert config.max_pool_size == 50


class TestLRUEviction:
    """Test LRU eviction when pool is at capacity."""

    @pytest.fixture
    def mock_asyncssh(self):
        with patch("scout_mcp.services.pool.asyncssh") as mock:
            mock.connect = AsyncMock(return_value=MagicMock())
            yield mock

    def make_host(self, name: str) -> MagicMock:
        """Create a mock host."""
        host = MagicMock()
        host.name = name
        host.hostname = f"{name}.example.com"
        host.port = 22
        host.user = "user"
        host.identity_file = None
        return host

    async def test_evicts_lru_when_full(self, mock_asyncssh):
        """Should evict LRU (oldest) connection when pool is full."""
        from scout_mcp.services.pool import ConnectionPool

        pool = ConnectionPool(idle_timeout=60, max_size=2)

        host0 = self.make_host("host0")
        host1 = self.make_host("host1")
        host2 = self.make_host("host2")

        # Fill pool to capacity
        await pool.get_connection(host0)
        await pool.get_connection(host1)
        assert pool.pool_size == 2

        # Adding third should evict first (LRU)
        await pool.get_connection(host2)

        assert pool.pool_size == 2
        assert "host0" not in pool.active_hosts, "host0 should have been evicted (LRU)"
        assert "host1" in pool.active_hosts
        assert "host2" in pool.active_hosts

    async def test_reuse_updates_lru_order(self, mock_asyncssh):
        """Reusing a connection should move it to end of LRU list."""
        from scout_mcp.services.pool import ConnectionPool

        pool = ConnectionPool(idle_timeout=60, max_size=2)

        host0 = self.make_host("host0")
        host1 = self.make_host("host1")
        host2 = self.make_host("host2")

        # Fill pool: host0 then host1
        await pool.get_connection(host0)
        await pool.get_connection(host1)

        # Reuse host0 - should move to end of LRU list
        await pool.get_connection(host0)

        # Now host1 is LRU (oldest), not host0
        # Adding host2 should evict host1
        await pool.get_connection(host2)

        assert "host0" in pool.active_hosts, "host0 should NOT be evicted (was recently used)"
        assert "host1" not in pool.active_hosts, "host1 should be evicted (now LRU)"
        assert "host2" in pool.active_hosts

    async def test_pool_never_exceeds_max_size(self, mock_asyncssh):
        """Pool should never have more connections than max_size."""
        from scout_mcp.services.pool import ConnectionPool

        pool = ConnectionPool(idle_timeout=60, max_size=5)

        # Try to add 10 connections
        for i in range(10):
            host = self.make_host(f"host{i}")
            await pool.get_connection(host)

            # Pool should never exceed max_size
            assert pool.pool_size <= 5, f"Pool exceeded max_size at iteration {i}"

        # Final pool should have exactly max_size connections
        assert pool.pool_size == 5


class TestEvictionLogging:
    """Test that eviction is properly logged."""

    async def test_eviction_logs_which_host(self, caplog):
        """Eviction should log which host was evicted."""
        import logging
        caplog.set_level(logging.INFO)

        with patch("scout_mcp.services.pool.asyncssh") as mock:
            mock.connect = AsyncMock(return_value=MagicMock())

            from scout_mcp.services.pool import ConnectionPool

            pool = ConnectionPool(idle_timeout=60, max_size=1)

            host0 = MagicMock()
            host0.name = "host0"
            host0.hostname = "h0"
            host0.port = 22
            host0.user = "u"
            host0.identity_file = None

            host1 = MagicMock()
            host1.name = "host1"
            host1.hostname = "h1"
            host1.port = 22
            host1.user = "u"
            host1.identity_file = None

            await pool.get_connection(host0)
            await pool.get_connection(host1)

            # Should log eviction
            assert any("evict" in r.message.lower() and "host0" in r.message
                      for r in caplog.records), "Should log which host was evicted"


class TestOrderedDictUsage:
    """Test that OrderedDict is used for LRU tracking."""

    async def test_uses_ordered_dict(self):
        """Pool should use OrderedDict for connections."""
        from scout_mcp.services.pool import ConnectionPool
        from collections import OrderedDict

        pool = ConnectionPool(idle_timeout=60, max_size=10)

        # _connections should be OrderedDict
        assert isinstance(pool._connections, OrderedDict), \
            "_connections should be OrderedDict for LRU tracking"

    async def test_move_to_end_on_reuse(self, mock_asyncssh):
        """Reusing connection should call move_to_end."""
        with patch("scout_mcp.services.pool.asyncssh") as mock:
            mock.connect = AsyncMock(return_value=MagicMock())

            from scout_mcp.services.pool import ConnectionPool

            pool = ConnectionPool(idle_timeout=60, max_size=10)

            host = MagicMock()
            host.name = "test-host"
            host.hostname = "h"
            host.port = 22
            host.user = "u"
            host.identity_file = None

            # First call creates connection
            await pool.get_connection(host)

            # Spy on move_to_end
            with patch.object(pool._connections, "move_to_end") as mock_move:
                # Second call reuses - should move to end
                await pool.get_connection(host)
                mock_move.assert_called_once_with("test-host")
```

**Run and verify RED:**
```bash
uv run pytest tests/test_pool_limits.py -v
# Expected: Tests FAIL - max_pool_size property doesn't exist, OrderedDict not used
```

##### STEP 2: GREEN - Implement Pool Size Limits

1. **Add configuration to config.py:**
```python
# scout_mcp/config.py - Add to Config class

@property
def max_pool_size(self) -> int:
    """Maximum number of concurrent SSH connections.

    Environment: SCOUT_MAX_POOL_SIZE
    Default: 100
    """
    return int(os.getenv("SCOUT_MAX_POOL_SIZE", "100"))
```

2. **Implement LRU eviction in pool:**
```python
# scout_mcp/services/pool.py

from collections import OrderedDict

class ConnectionPool:
    """SSH connection pool with size limits and LRU eviction."""

    def __init__(
        self,
        idle_timeout: int = 60,
        max_size: int = 100,
    ) -> None:
        self.idle_timeout = idle_timeout
        self.max_size = max_size
        self._connections: OrderedDict[str, PooledConnection] = OrderedDict()
        self._host_locks: dict[str, asyncio.Lock] = {}
        self._meta_lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task[Any] | None = None

        logger.info(
            "ConnectionPool initialized (idle_timeout=%ds, max_size=%d)",
            idle_timeout,
            max_size,
        )

    async def _evict_lru_if_needed(self) -> None:
        """Evict least recently used connection if at capacity.

        Must be called with appropriate locks held.
        """
        while len(self._connections) >= self.max_size:
            # Get oldest (first) key
            oldest_host = next(iter(self._connections))
            logger.info(
                "Pool at capacity (%d/%d), evicting LRU: %s",
                len(self._connections),
                self.max_size,
                oldest_host,
            )
            # Remove it
            pooled = self._connections.pop(oldest_host)
            pooled.connection.close()

    async def get_connection(self, host: "SSHHost") -> asyncssh.SSHClientConnection:
        """Get or create a connection to the host."""
        host_lock = await self._get_host_lock(host.name)

        async with host_lock:
            pooled = self._connections.get(host.name)

            # Return existing if valid (move to end for LRU)
            if pooled and not pooled.is_stale:
                pooled.touch()
                # Move to end (most recently used)
                self._connections.move_to_end(host.name)
                logger.debug("Reusing connection to %s", host.name)
                return pooled.connection

            # Check capacity before creating new
            await self._evict_lru_if_needed()

            # Create new connection
            logger.info("Opening SSH connection to %s", host.name)
            client_keys = [host.identity_file] if host.identity_file else None
            conn = await asyncssh.connect(
                host.hostname,
                port=host.port,
                username=host.user,
                known_hosts=self._known_hosts,
                client_keys=client_keys,
            )

            self._connections[host.name] = PooledConnection(connection=conn)
            # New connections go to end (most recently used)
            self._connections.move_to_end(host.name)

            logger.info(
                "SSH connection established to %s (pool_size=%d/%d)",
                host.name,
                len(self._connections),
                self.max_size,
            )

            # Start cleanup if needed
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._cleanup_loop())

            return conn
```

3. **Update state.py to pass config:**
```python
# scout_mcp/services/state.py

def get_pool() -> ConnectionPool:
    """Get the global connection pool."""
    global _pool
    if _pool is None:
        config = get_config()
        _pool = ConnectionPool(
            idle_timeout=config.idle_timeout,
            max_size=config.max_pool_size,
        )
    return _pool
```

**Run and verify GREEN:**
```bash
uv run pytest tests/test_pool_limits.py -v
# Expected: All tests PASS
```

##### STEP 3: REFACTOR - Integration Tests and Final Verification

1. **Add integration test for state.py:**
```python
# tests/test_pool_state_integration.py
"""TDD: Integration tests for pool state management."""

import pytest
from unittest.mock import patch


class TestPoolStateIntegration:
    """Test that state.py correctly initializes pool with config."""

    def test_get_pool_passes_max_size(self, monkeypatch):
        """get_pool should pass max_pool_size from config."""
        monkeypatch.setenv("SCOUT_MAX_POOL_SIZE", "25")

        # Reset state to force re-initialization
        from scout_mcp.services import state
        state._pool = None
        state._config = None

        from scout_mcp.services import get_pool
        pool = get_pool()

        assert pool.max_size == 25

    def test_get_pool_uses_default(self, monkeypatch):
        """get_pool should use default 100 when env not set."""
        monkeypatch.delenv("SCOUT_MAX_POOL_SIZE", raising=False)

        from scout_mcp.services import state
        state._pool = None
        state._config = None

        from scout_mcp.services import get_pool
        pool = get_pool()

        assert pool.max_size == 100
```

2. **Run full test suite:**
```bash
uv run pytest tests/ -v
```

3. **Type check:**
```bash
uv run mypy scout_mcp/
```

4. **Lint:**
```bash
uv run ruff check scout_mcp/ tests/
```

#### TDD Acceptance Criteria (All must be GREEN)
- [ ] `tests/test_pool_limits.py` - All LRU/size tests pass (RED→GREEN)
- [ ] `tests/test_pool_state_integration.py` - State integration tests pass
- [ ] `max_pool_size` config property added with default 100
- [ ] `_connections` changed from `dict` to `OrderedDict`
- [ ] `_evict_lru_if_needed()` method evicts oldest connection
- [ ] `move_to_end()` called on connection reuse
- [ ] Pool size never exceeds `max_size`
- [ ] Eviction logs include host name being evicted
- [ ] `state.py` passes `max_size` from config to pool
- [ ] Full test suite passes: `uv run pytest tests/ -v`
- [ ] Type check passes: `uv run mypy scout_mcp/`
- [ ] Lint passes: `uv run ruff check scout_mcp/ tests/`

---

## Execution Summary

### Parallel Execution Plan

```
Batch 1 (Parallel - 3 agents):
├── Agent 1: scout_mcp-vn7 (asyncssh version)     ─┐
├── Agent 2: scout_mcp-zge (command injection)    ─┼── ~2 hours
└── Agent 3: scout_mcp-7di (host key verification)─┘

Batch 2 (Parallel - 4 agents):
├── Agent 4: scout_mcp-2rf (retry helper)         ─┐
├── Agent 5: scout_mcp-pya (path traversal)       ─┼── ~4 hours
├── Agent 6: scout_mcp-ydy (scout refactor)       ─┤ (depends on 2rf)
└── Agent 7: scout_mcp-y6f (pytest-asyncio)       ─┘

Batch 3 (Parallel - 3 agents):
├── Agent 8: scout_mcp-0wx (API auth)             ─┐
├── Agent 9: scout_mcp-drx (rate limiting)        ─┼── ~4 hours
└── Agent 10: scout_mcp-6ce (security docs)       ─┘ (depends on 0wx, 7di)

Batch 4 (Sequential - 2 agents):
├── Agent 11: scout_mcp-kvk (per-host locks)      ── ~3 hours
└── Agent 12: scout_mcp-82l (pool size limits)    ── ~3 hours (depends on kvk)

Total: ~16 hours parallel execution (vs ~40 hours sequential)
```

### Verification Checklist

After each batch:
- [ ] `uv run pytest tests/ -v` - All tests pass
- [ ] `uv run mypy scout_mcp/` - No type errors
- [ ] `uv run ruff check scout_mcp/ tests/` - No lint errors
- [ ] Manual smoke test of scout tool

### Rollback Plan

Each batch creates atomic commits. If issues arise:
```bash
git log --oneline -10  # Find last good commit
git revert <batch-commits>  # Revert problematic batch
```

---

## Files Created/Modified Summary

### New Files
- `scout_mcp/utils/shell.py` - Shell quoting utilities
- `scout_mcp/utils/validation.py` - Path/host validation
- `scout_mcp/services/connection.py` - Connection retry helper
- `scout_mcp/tools/handlers.py` - Scout operation handlers
- `scout_mcp/middleware/auth.py` - API key authentication
- `scout_mcp/middleware/ratelimit.py` - Rate limiting
- `SECURITY.md` - Security documentation
- `tests/test_security.py` - Security tests
- `tests/test_validation.py` - Validation tests
- `tests/test_connection.py` - Connection helper tests
- `tests/test_pool_concurrency.py` - Concurrency tests
- `tests/test_pool_limits.py` - Pool limit tests
- `tests/test_middleware/test_auth.py` - Auth tests
- `tests/test_middleware/test_ratelimit.py` - Rate limit tests

### Modified Files
- `pyproject.toml` - asyncssh version, pytest config
- `scout_mcp/config.py` - New config options
- `scout_mcp/services/pool.py` - Per-host locks, size limits, host key verification
- `scout_mcp/services/state.py` - Pass config to pool
- `scout_mcp/services/__init__.py` - Export connection helper
- `scout_mcp/services/executors.py` - shlex.quote() everywhere
- `scout_mcp/tools/scout.py` - Refactored to use handlers
- `scout_mcp/utils/parser.py` - Add validation
- `scout_mcp/server.py` - Add auth middleware
- `scout_mcp/middleware/__init__.py` - Export new middleware
- `scout_mcp/resources/*.py` - Use connection helper
- `README.md` - Security section
- `CLAUDE.md` - Updated configuration docs

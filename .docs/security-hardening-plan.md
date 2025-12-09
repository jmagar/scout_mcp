# Scout MCP Security Hardening & Refactoring Plan

## Overview

This plan addresses 12 P1 issues for scout_mcp, organized into parallelizable batches for efficient execution using multiple agents.

**Total Estimated Effort:** 40-50 hours
**Execution Strategy:** 4 parallel batches with dependency-aware sequencing

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

**Files:** `scout_mcp/services/executors.py`
**Effort:** 2 hours

#### Current State (VULNERABLE)
```python
# executors.py:161
full_command = f"cd {working_dir!r} && timeout {timeout} {command}"

# Also at lines: 17, 53, 87, 124, 137, 214, 281, 368, 403, 487, 518, 567
```

The `!r` format spec uses `repr()` which is NOT safe for shell escaping.

#### Implementation

1. **Add shlex import and create helper:**
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

2. **Update executors.py - Replace ALL instances of `!r` with `shlex.quote()`:**

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


class TestShellQuoting:
    """Test shell quoting utilities."""

    def test_quote_path_simple(self):
        assert quote_path("/var/log") == "'/var/log'"

    def test_quote_path_with_spaces(self):
        assert quote_path("/var/log/my file.txt") == "'/var/log/my file.txt'"

    def test_quote_path_injection_attempt(self):
        malicious = "/tmp'; rm -rf / #"
        quoted = quote_path(malicious)
        # Should be safely quoted - cannot break out
        assert "rm -rf" not in shlex.split(f"cat {quoted}")[1:]

    def test_quote_path_backticks(self):
        malicious = "/tmp/`whoami`.txt"
        quoted = quote_path(malicious)
        assert quoted == "'/tmp/`whoami`.txt'"

    def test_quote_path_dollar_expansion(self):
        malicious = "/tmp/$HOME/file"
        quoted = quote_path(malicious)
        assert quoted == "'/tmp/$HOME/file'"

    def test_quote_arg_semicolon(self):
        malicious = "arg; rm -rf /"
        quoted = quote_arg(malicious)
        assert ";" not in shlex.split(quoted)[0] or quoted.startswith("'")
```

#### Acceptance Criteria
- [ ] All `!r` format specs in executors.py replaced with `shlex.quote()`
- [ ] New `scout_mcp/utils/shell.py` with quote functions
- [ ] Security tests pass with injection attempts
- [ ] All existing tests pass
- [ ] mypy type checks pass

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

#### Implementation

1. **Add configuration option:**
```python
# scout_mcp/config.py - Add to Config class

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

#### Implementation

1. **Create connection helper:**
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

5. **Add tests:**
```python
# tests/test_connection.py (NEW FILE)
"""Tests for connection retry helper."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from scout_mcp.services.connection import (
    ConnectionError,
    get_connection_with_retry,
)


@pytest.fixture
def mock_pool():
    with patch("scout_mcp.services.connection.get_pool") as mock:
        yield mock.return_value


@pytest.fixture
def mock_host():
    host = MagicMock()
    host.name = "test-host"
    return host


class TestGetConnectionWithRetry:
    """Test connection retry helper."""

    async def test_success_first_try(self, mock_pool, mock_host):
        """Connection succeeds on first attempt."""
        mock_conn = AsyncMock()
        mock_pool.get_connection = AsyncMock(return_value=mock_conn)

        result = await get_connection_with_retry(mock_host)

        assert result == mock_conn
        mock_pool.get_connection.assert_called_once_with(mock_host)

    async def test_success_after_retry(self, mock_pool, mock_host):
        """Connection fails first, succeeds on retry."""
        mock_conn = AsyncMock()
        mock_pool.get_connection = AsyncMock(
            side_effect=[Exception("First fail"), mock_conn]
        )
        mock_pool.remove_connection = AsyncMock()

        result = await get_connection_with_retry(mock_host)

        assert result == mock_conn
        assert mock_pool.get_connection.call_count == 2
        mock_pool.remove_connection.assert_called_once_with("test-host")

    async def test_failure_after_retry(self, mock_pool, mock_host):
        """Connection fails on both attempts."""
        mock_pool.get_connection = AsyncMock(
            side_effect=[Exception("First"), Exception("Second")]
        )
        mock_pool.remove_connection = AsyncMock()

        with pytest.raises(ConnectionError) as exc_info:
            await get_connection_with_retry(mock_host)

        assert "test-host" in str(exc_info.value)
        assert exc_info.value.host_name == "test-host"
```

#### Acceptance Criteria
- [ ] New `scout_mcp/services/connection.py` with `get_connection_with_retry()`
- [ ] All 8+ resource files updated to use helper
- [ ] ~100 lines of duplication removed
- [ ] Unit tests for retry helper
- [ ] All existing tests pass

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

#### Implementation

1. **Create validation module:**
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

3. **Add tests:**
```python
# tests/test_validation.py (NEW FILE)
"""Tests for path validation."""

import pytest

from scout_mcp.utils.validation import (
    PathTraversalError,
    validate_path,
    validate_host,
)


class TestValidatePath:
    """Test path validation."""

    def test_simple_absolute_path(self):
        assert validate_path("/var/log") == "/var/log"

    def test_simple_relative_path(self):
        assert validate_path("logs/app.log") == "logs/app.log"

    def test_home_directory(self):
        assert validate_path("~/code") == "~/code"

    def test_traversal_dot_dot_slash(self):
        with pytest.raises(PathTraversalError):
            validate_path("../etc/passwd")

    def test_traversal_embedded(self):
        with pytest.raises(PathTraversalError):
            validate_path("/var/log/../../../etc/passwd")

    def test_traversal_normalized(self):
        with pytest.raises(PathTraversalError):
            validate_path("/var/log/../../..")

    def test_null_byte(self):
        with pytest.raises(PathTraversalError):
            validate_path("/var/log/app.log\x00.txt")

    def test_empty_path(self):
        with pytest.raises(ValueError):
            validate_path("")

    def test_absolute_not_allowed(self):
        with pytest.raises(ValueError):
            validate_path("/etc/passwd", allow_absolute=False)


class TestValidateHost:
    """Test host validation."""

    def test_simple_host(self):
        assert validate_host("myserver") == "myserver"

    def test_host_with_domain(self):
        assert validate_host("server.example.com") == "server.example.com"

    def test_empty_host(self):
        with pytest.raises(ValueError):
            validate_host("")

    def test_host_with_slash(self):
        with pytest.raises(ValueError):
            validate_host("server/path")

    def test_host_with_semicolon(self):
        with pytest.raises(ValueError):
            validate_host("server;rm -rf /")

    def test_host_with_pipe(self):
        with pytest.raises(ValueError):
            validate_host("server|cat /etc/passwd")
```

#### Acceptance Criteria
- [ ] New `scout_mcp/utils/validation.py` with `validate_path()` and `validate_host()`
- [ ] `parser.py` updated to use validation
- [ ] Path traversal attempts rejected with clear error
- [ ] Null byte injection blocked
- [ ] All tests pass
- [ ] Documentation updated

---

### Agent 6: scout_mcp-ydy - Split scout() Function

**Files:** `scout_mcp/tools/scout.py`
**Effort:** 4 hours
**Depends on:** scout_mcp-2rf (uses `get_connection_with_retry`)

#### Current State (128 lines, 5+ responsibilities)
```python
async def scout(target: str, query: str | None = None, tree: bool = False) -> str:
    # Lines 19-147: Handles hosts, files, directories, commands
```

#### Implementation

1. **Create handler module:**
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

#### Acceptance Criteria
- [ ] New `scout_mcp/tools/handlers.py` with 5 handler functions
- [ ] `scout()` reduced to ~50 lines (was 128)
- [ ] Each handler function ≤30 lines
- [ ] All existing tests pass
- [ ] Code coverage maintained

---

### Agent 7: scout_mcp-y6f - Fix pytest-asyncio Configuration

**Files:** `pyproject.toml`, test files
**Effort:** 2 hours

#### Current State
```toml
# pyproject.toml:48
asyncio_mode = "auto"  # DEPRECATED in pytest-asyncio 0.23+
```

#### Implementation

1. **Update pyproject.toml:**
```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]
cache_dir = ".cache/.pytest_cache"
```

2. **Verify all async tests have proper markers:**
```python
# Ensure all async test functions work without explicit markers
# The new config auto-detects async functions
```

3. **Run full test suite:**
```bash
uv run pytest tests/ -v --tb=short
```

4. **Check for deprecation warnings:**
```bash
uv run pytest tests/ -v -W error::DeprecationWarning
```

5. **Update coverage targets:**
```toml
# pyproject.toml
[tool.coverage.report]
show_missing = true
fail_under = 80  # Set realistic target based on unblocked tests
```

#### Acceptance Criteria
- [ ] `asyncio_mode = "auto"` replaced with new config
- [ ] All async tests run successfully
- [ ] No deprecation warnings from pytest-asyncio
- [ ] Test count increases (unblocked tests)
- [ ] Coverage report generated

---

## Batch 3: Security Features (Parallel - 3 Agents)

Execute after Batch 2 completes.

### Agent 8: scout_mcp-0wx - Implement API Key Authentication

**Files:** `scout_mcp/server.py`, `scout_mcp/middleware/auth.py` (NEW)
**Effort:** 4 hours

#### Implementation

Based on [FastMCP Authentication docs](https://gofastmcp.com/servers/auth/authentication), implement custom API key middleware.

1. **Create auth middleware:**
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

#### Acceptance Criteria
- [ ] Auth middleware created
- [ ] Auth enabled when SCOUT_API_KEYS is set
- [ ] Health endpoint bypasses auth
- [ ] Invalid keys return 401
- [ ] Missing keys return 401
- [ ] Constant-time comparison used
- [ ] Documentation updated

---

### Agent 9: scout_mcp-drx - Add Rate Limiting

**Files:** `scout_mcp/middleware/ratelimit.py` (NEW)
**Effort:** 3 hours

#### Implementation

1. **Create rate limit middleware:**
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

#### Acceptance Criteria
- [ ] Rate limiting middleware created
- [ ] Token bucket algorithm implemented
- [ ] Configurable via environment variables
- [ ] Health endpoint bypasses rate limit
- [ ] 429 response with Retry-After header
- [ ] Per-client tracking (by IP)
- [ ] Tests pass

---

### Agent 10: scout_mcp-6ce - Add Security Documentation

**Files:** `README.md`, `SECURITY.md` (NEW)
**Effort:** 2 hours
**Depends on:** scout_mcp-0wx, scout_mcp-7di

#### Implementation

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

#### Implementation

1. **Implement per-host locking:**
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

2. **Add concurrency tests:**
```python
# tests/test_pool_concurrency.py (NEW FILE)
"""Concurrency tests for connection pool."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from scout_mcp.services.pool import ConnectionPool


class TestPoolConcurrency:
    """Test concurrent access to connection pool."""

    @pytest.fixture
    def mock_asyncssh(self):
        with patch("scout_mcp.services.pool.asyncssh") as mock:
            # Simulate connection delay
            async def slow_connect(*args, **kwargs):
                await asyncio.sleep(0.1)
                return MagicMock()
            mock.connect = slow_connect
            yield mock

    async def test_concurrent_different_hosts(self, mock_asyncssh):
        """Concurrent connections to different hosts should not block."""
        pool = ConnectionPool(idle_timeout=60)

        host1 = MagicMock(name="host1", hostname="h1", port=22, user="u", identity_file=None)
        host1.name = "host1"
        host2 = MagicMock(name="host2", hostname="h2", port=22, user="u", identity_file=None)
        host2.name = "host2"

        # Both should complete in ~0.1s, not ~0.2s
        start = asyncio.get_event_loop().time()
        await asyncio.gather(
            pool.get_connection(host1),
            pool.get_connection(host2),
        )
        elapsed = asyncio.get_event_loop().time() - start

        # Should be close to 0.1s (parallel), not 0.2s (serial)
        assert elapsed < 0.15

    async def test_concurrent_same_host(self, mock_asyncssh):
        """Concurrent connections to same host should serialize."""
        pool = ConnectionPool(idle_timeout=60)

        host = MagicMock(name="host1", hostname="h1", port=22, user="u", identity_file=None)
        host.name = "host1"

        # First creates, second reuses (but must wait for first)
        await asyncio.gather(
            pool.get_connection(host),
            pool.get_connection(host),
        )

        # Should only create one connection
        assert pool.pool_size == 1
```

#### Acceptance Criteria
- [ ] Per-host locking implemented
- [ ] Meta-lock only protects lock dictionary
- [ ] Network I/O not under meta-lock
- [ ] Concurrent requests to different hosts don't block
- [ ] Concurrent requests to same host serialize correctly
- [ ] All existing tests pass
- [ ] Concurrency tests pass

---

### Agent 12: scout_mcp-82l - Add Pool Size Limits

**Files:** `scout_mcp/services/pool.py`, `scout_mcp/config.py`
**Effort:** 3 hours
**Depends on:** scout_mcp-kvk (per-host locks)

#### Implementation

1. **Add configuration:**
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

4. **Add tests:**
```python
# tests/test_pool_limits.py (NEW FILE)
"""Tests for connection pool size limits."""

import pytest
from unittest.mock import MagicMock, patch

from scout_mcp.services.pool import ConnectionPool


class TestPoolSizeLimits:
    """Test pool size limiting and LRU eviction."""

    @pytest.fixture
    def mock_asyncssh(self):
        with patch("scout_mcp.services.pool.asyncssh") as mock:
            mock.connect = MagicMock(return_value=MagicMock())
            yield mock

    async def test_evicts_lru_when_full(self, mock_asyncssh):
        """Pool evicts LRU connection when at capacity."""
        pool = ConnectionPool(idle_timeout=60, max_size=2)

        hosts = [
            MagicMock(name=f"host{i}", hostname=f"h{i}", port=22, user="u", identity_file=None)
            for i in range(3)
        ]
        for i, h in enumerate(hosts):
            h.name = f"host{i}"

        # Fill pool
        await pool.get_connection(hosts[0])
        await pool.get_connection(hosts[1])
        assert pool.pool_size == 2

        # Third should evict first (LRU)
        await pool.get_connection(hosts[2])
        assert pool.pool_size == 2
        assert "host0" not in pool.active_hosts
        assert "host1" in pool.active_hosts
        assert "host2" in pool.active_hosts

    async def test_reuse_updates_lru_order(self, mock_asyncssh):
        """Reusing connection updates LRU order."""
        pool = ConnectionPool(idle_timeout=60, max_size=2)

        hosts = [
            MagicMock(name=f"host{i}", hostname=f"h{i}", port=22, user="u", identity_file=None)
            for i in range(3)
        ]
        for i, h in enumerate(hosts):
            h.name = f"host{i}"

        # Fill pool
        await pool.get_connection(hosts[0])
        await pool.get_connection(hosts[1])

        # Reuse host0 (moves to end)
        await pool.get_connection(hosts[0])

        # Third should evict host1 (now LRU)
        await pool.get_connection(hosts[2])
        assert "host0" in pool.active_hosts
        assert "host1" not in pool.active_hosts
        assert "host2" in pool.active_hosts
```

#### Acceptance Criteria
- [ ] `max_pool_size` config added (default 100)
- [ ] LRU eviction implemented with OrderedDict
- [ ] Pool never exceeds max_size
- [ ] Connection reuse updates LRU order
- [ ] Eviction logs which connection was removed
- [ ] All tests pass

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

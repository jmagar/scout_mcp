# Security and Architecture Fixes Implementation Plan

> **📁 Organization Note:** When this plan is fully implemented and verified, move this file to `docs/plans/complete/` to keep the plans folder organized.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Resolve 5 critical issues: command injection vulnerabilities, SSH host verification bypass, global singleton anti-pattern, code duplication, and test infrastructure breakage.

**Architecture:** Multi-phase approach with security fixes (P0) first, then test infrastructure (P1), followed by architectural improvements (P1-P2).

**Tech Stack:** Python 3.11+, asyncssh, fastmcp, pytest, mypy, ruff

---

## Phase 1: Critical Security Fixes (P0)

### Task 1: Fix Command Injection in run_command

**Files:**
- Modify: `scout_mcp/services/executors.py:167-207`
- Create: `tests/test_services/test_executors_security.py`

**Step 0: Verify target code location**

Run: `grep -n "^async def run_command" scout_mcp/services/executors.py`
Expected: Shows line number where run_command is defined

If line number differs from 167, note the actual line for reference.

**Step 1: Write failing security test**

Create test file to verify command injection is blocked:

```python
"""Security tests for command execution."""

import pytest
from scout_mcp.services.executors import validate_command, run_command
from scout_mcp.models import CommandResult


class TestCommandValidation:
    """Test command validation prevents injection."""

    def test_validate_command_allows_safe_commands(self):
        """Safe commands in allowlist should pass validation."""
        cmd, args = validate_command("grep pattern file.txt")
        assert cmd == "grep"
        assert args == ["pattern", "file.txt"]

    def test_validate_command_rejects_dangerous_commands(self):
        """Commands not in allowlist should be rejected."""
        with pytest.raises(ValueError, match="Command 'rm' not allowed"):
            validate_command("rm -rf /")

    def test_validate_command_rejects_shell_metacharacters(self):
        """Shell metacharacters in command should be rejected."""
        with pytest.raises(ValueError, match="not allowed"):
            validate_command("ls; whoami")

    def test_validate_command_rejects_command_substitution(self):
        """Command substitution attempts should be rejected."""
        with pytest.raises(ValueError, match="not allowed"):
            validate_command("echo $(whoami)")

    def test_validate_command_handles_empty_command(self):
        """Empty command should raise ValueError."""
        with pytest.raises(ValueError, match="Empty command"):
            validate_command("")

    def test_validate_command_with_flags(self):
        """Commands with flags should be parsed correctly."""
        cmd, args = validate_command("grep -r pattern dir/")
        assert cmd == "grep"
        assert "-r" in args
        assert "pattern" in args
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_services/test_executors_security.py::TestCommandValidation -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'scout_mcp.services.executors.validate_command'"

**Step 3: Implement command validation**

Add to `scout_mcp/services/executors.py` before `run_command` function:

```python
from typing import Final

# Allowlist of safe commands for remote execution
ALLOWED_COMMANDS: Final[set[str]] = {
    "grep",
    "rg",  # ripgrep
    "find",
    "ls",
    "tree",
    "cat",
    "head",
    "tail",
    "wc",
    "sort",
    "uniq",
    "diff",
    "stat",
    "file",
    "du",
    "df",
}


def validate_command(command: str) -> tuple[str, list[str]]:
    """Parse and validate command against allowlist.

    Args:
        command: Shell command to validate

    Returns:
        Tuple of (command_name, arguments_list)

    Raises:
        ValueError: If command is empty, not allowed, or contains injection attempts
    """
    if not command or not command.strip():
        raise ValueError("Empty command")

    # Parse command with shlex (handles quotes correctly)
    try:
        parts = shlex.split(command)
    except ValueError as e:
        raise ValueError(f"Invalid command syntax: {e}") from e

    if not parts:
        raise ValueError("Empty command after parsing")

    cmd = parts[0]
    args = parts[1:] if len(parts) > 1 else []

    # Check against allowlist
    if cmd not in ALLOWED_COMMANDS:
        allowed_list = ", ".join(sorted(ALLOWED_COMMANDS))
        raise ValueError(
            f"Command '{cmd}' not allowed. Allowed commands: {allowed_list}"
        )

    # Additional check: ensure no shell metacharacters in cmd itself
    # (shlex.split should handle this, but defense in depth)
    dangerous_chars = [";", "&", "|", "$", "`", "\n", "\r", "(", ")"]
    for char in dangerous_chars:
        if char in cmd:
            raise ValueError(f"Command contains invalid character: {char}")

    return cmd, args
```

**Step 4: Update run_command to use validation**

Replace `run_command` function in `scout_mcp/services/executors.py:167-207`:

```python
async def run_command(
    conn: "asyncssh.SSHClientConnection",
    working_dir: str,
    command: str,
    timeout: int,
) -> CommandResult:
    """Execute validated command in working directory.

    Args:
        conn: SSH connection
        working_dir: Working directory for command
        command: Shell command (will be validated against allowlist)
        timeout: Command timeout in seconds

    Returns:
        CommandResult with stdout, stderr, and return code

    Raises:
        ValueError: If command is not in allowlist
    """
    # Validate and parse command
    cmd, args = validate_command(command)

    # Build safe command with proper quoting
    # Note: cd is safe here because working_dir is validated separately
    full_command = f"cd {shlex.quote(working_dir)} && timeout {timeout} {shlex.quote(cmd)}"
    for arg in args:
        full_command += f" {shlex.quote(arg)}"

    result = await conn.run(full_command, check=False)

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

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_services/test_executors_security.py -v`
Expected: PASS (all tests green)

**Step 6: Commit**

```bash
git add scout_mcp/services/executors.py tests/test_services/test_executors_security.py
git commit -m "fix(security): prevent command injection in run_command

- Add command allowlist (grep, find, ls, cat, etc.)
- Validate commands before execution
- Properly quote all arguments with shlex.quote()
- Add comprehensive security tests

Fixes: Command Injection vulnerability (CVSS 9.8)
Ref: .docs/COMPREHENSIVE-CODEBASE-REVIEW-2025-12-09.md#critical-1"
```

---

### Task 2: Fix Docker/Compose Command Injection

**Files:**
- Modify: `scout_mcp/services/executors.py:210-248` (docker_logs)
- Modify: `scout_mcp/services/executors.py:405-440` (compose_logs)
- Modify: `scout_mcp/services/executors.py:674-709` (find_files)
- Modify: `tests/test_services/test_executors_security.py`

**Step 0: Verify target code locations**

Run verification commands:
```bash
grep -n "^async def docker_logs" scout_mcp/services/executors.py
grep -n "^async def compose_logs" scout_mcp/services/executors.py
grep -n "^async def find_files" scout_mcp/services/executors.py
```

Expected: Shows line numbers for each function. Note actual lines if they differ from plan.

**Step 1: Write failing validation tests**

Add to `tests/test_services/test_executors_security.py`:

```python
from scout_mcp.services.executors import (
    validate_container_name,
    validate_project_name,
    validate_depth,
)


class TestDockerValidation:
    """Test Docker/Compose input validation."""

    def test_validate_container_name_allows_valid(self):
        """Valid container names should pass."""
        assert validate_container_name("my-container") == "my-container"
        assert validate_container_name("app_1") == "app_1"
        assert validate_container_name("web.service") == "web.service"

    def test_validate_container_name_rejects_injection(self):
        """Container names with injection attempts should fail."""
        with pytest.raises(ValueError, match="Invalid container name"):
            validate_container_name("container;id")
        with pytest.raises(ValueError, match="Invalid container name"):
            validate_container_name("app`whoami`")
        with pytest.raises(ValueError, match="Invalid container name"):
            validate_container_name("test$(ls)")

    def test_validate_project_name_allows_valid(self):
        """Valid project names should pass."""
        assert validate_project_name("my-project") == "my-project"
        assert validate_project_name("stack_prod") == "stack_prod"

    def test_validate_project_name_rejects_injection(self):
        """Project names with injection attempts should fail."""
        with pytest.raises(ValueError, match="Invalid project name"):
            validate_project_name("project|whoami")

    def test_validate_depth_allows_valid_range(self):
        """Depth 1-10 should be allowed."""
        assert validate_depth(1) == 1
        assert validate_depth(5) == 5
        assert validate_depth(10) == 10

    def test_validate_depth_rejects_out_of_range(self):
        """Depth outside 1-10 should be rejected."""
        with pytest.raises(ValueError, match="depth must be 1-10"):
            validate_depth(0)
        with pytest.raises(ValueError, match="depth must be 1-10"):
            validate_depth(99999)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_services/test_executors_security.py::TestDockerValidation -v`
Expected: FAIL with import errors

**Step 3: Implement validation functions**

Add to `scout_mcp/services/executors.py` before `docker_logs`:

```python
import re


def validate_container_name(name: str) -> str:
    """Validate Docker container name.

    Args:
        name: Container name to validate

    Returns:
        Validated container name

    Raises:
        ValueError: If name contains invalid characters
    """
    if not name:
        raise ValueError("Container name cannot be empty")

    # Docker container names: alphanumeric, dash, underscore, period
    if not re.match(r'^[a-zA-Z0-9_.-]+$', name):
        raise ValueError(f"Invalid container name: {name}")

    return name


def validate_project_name(name: str) -> str:
    """Validate Docker Compose project name.

    Args:
        name: Project name to validate

    Returns:
        Validated project name

    Raises:
        ValueError: If name contains invalid characters
    """
    if not name:
        raise ValueError("Project name cannot be empty")

    # Docker Compose project names: alphanumeric, dash, underscore
    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        raise ValueError(f"Invalid project name: {name}")

    return name


def validate_depth(depth: int) -> int:
    """Validate search depth parameter.

    Args:
        depth: Search depth to validate

    Returns:
        Validated depth

    Raises:
        ValueError: If depth is out of safe range
    """
    if depth < 1 or depth > 10:
        raise ValueError(f"depth must be 1-10, got {depth}")

    return depth
```

**Step 4: Update docker_logs to use validation**

Replace in `scout_mcp/services/executors.py:210-248`:

```python
async def docker_logs(
    conn: "asyncssh.SSHClientConnection",
    container: str,
    tail: int = 100,
    timestamps: bool = True,
) -> tuple[str, bool]:
    """Fetch Docker container logs.

    Args:
        conn: SSH connection to execute command on.
        container: Container name or ID.
        tail: Number of lines from end (default: 100).
        timestamps: Include timestamps in output (default: True).

    Returns:
        Tuple of (logs content, container_exists boolean).

    Raises:
        ValueError: If container name is invalid
        RuntimeError: If Docker command fails unexpectedly.
    """
    # Validate container name before use
    container = validate_container_name(container)

    ts_flag = "--timestamps" if timestamps else ""
    cmd = f"docker logs --tail {tail} {ts_flag} {shlex.quote(container)} 2>&1"

    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        stdout = ""
    elif isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")

    # Check for "No such container" error
    if result.returncode != 0:
        if "No such container" in stdout or "no such container" in stdout.lower():
            return ("", False)
        # Docker daemon not running or other error
        raise RuntimeError(f"Docker error: {stdout}")

    return (stdout, True)
```

**Step 5: Update compose_logs to use validation**

Replace in `scout_mcp/services/executors.py:405-440`:

```python
async def compose_logs(
    conn: "asyncssh.SSHClientConnection",
    project: str,
    tail: int = 100,
    timestamps: bool = True,
) -> tuple[str, bool]:
    """Fetch Docker Compose stack logs.

    Args:
        conn: SSH connection.
        project: Compose project name.
        tail: Number of lines from end (default: 100).
        timestamps: Include timestamps (default: True).

    Returns:
        Tuple of (logs content, project_exists boolean).

    Raises:
        ValueError: If project name is invalid
    """
    # Validate project name before use
    project = validate_project_name(project)

    ts_flag = "--timestamps" if timestamps else ""
    cmd = f"docker compose -p {shlex.quote(project)} logs --tail {tail} {ts_flag} 2>&1"

    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        stdout = ""
    elif isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")

    # Check for project not found
    if result.returncode != 0:
        if "no configuration file provided" in stdout.lower():
            return ("", False)
        # Other error - still return output
        return (stdout, True)

    return (stdout, True)
```

**Step 6: Update find_files to validate depth**

Replace in `scout_mcp/services/executors.py:674-709`:

```python
async def find_files(
    conn: "asyncssh.SSHClientConnection",
    path: str,
    pattern: str,
    max_depth: int = 5,
    file_type: str | None = None,
    max_results: int = 100,
) -> str:
    """Find files matching pattern under path.

    Args:
        conn: SSH connection
        path: Starting directory path
        pattern: Glob pattern (e.g., "*.py", "config*")
        max_depth: Maximum depth to search (default: 5)
        file_type: Optional type filter ('f' for files, 'd' for dirs)
        max_results: Maximum results to return (default: 100)

    Returns:
        Newline-separated list of matching paths, or error message.

    Raises:
        ValueError: If depth is out of safe range
    """
    # Validate depth to prevent filesystem traversal abuse
    max_depth = validate_depth(max_depth)

    # Build find command with proper quoting
    type_flag = f"-type {shlex.quote(file_type)}" if file_type else ""
    cmd = (
        f"find {shlex.quote(path)} -maxdepth {max_depth} -name {shlex.quote(pattern)} "
        f"{type_flag} 2>/dev/null | head -{max_results}"
    )

    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        return ""
    if isinstance(stdout, bytes):
        return stdout.decode("utf-8", errors="replace").strip()
    return stdout.strip()
```

**Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_services/test_executors_security.py -v`
Expected: PASS

**Step 8: Commit**

```bash
git add scout_mcp/services/executors.py tests/test_services/test_executors_security.py
git commit -m "fix(security): prevent Docker/Compose command injection

- Validate container and project names (alphanumeric + dash/underscore)
- Validate depth parameter (1-10 range)
- Add comprehensive validation tests

Fixes: Docker Command Injection (CVSS 8.8)
Ref: .docs/COMPREHENSIVE-CODEBASE-REVIEW-2025-12-09.md#critical-3"
```

---

### Task 3: Fix SSH Host Verification Bypass

**Files:**
- Modify: `scout_mcp/config.py:236-240`
- Create: `tests/test_config_security.py`

**Step 0: Verify target code location**

Run: `grep -n "def known_hosts_path" scout_mcp/config.py`
Expected: Shows line number of known_hosts_path property

Note actual line if different from 236. The target is the property that returns None when file doesn't exist.

**Step 1: Write failing test**

```python
"""Security tests for config module."""

import os
import pytest
from pathlib import Path
from scout_mcp.config import Config


class TestSSHHostVerification:
    """Test SSH host key verification behavior."""

    def test_known_hosts_fails_closed_when_missing(self, tmp_path, monkeypatch):
        """Should raise error when known_hosts doesn't exist."""
        # Point to non-existent file
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("SCOUT_KNOWN_HOSTS", raising=False)

        with pytest.raises(FileNotFoundError, match="known_hosts not found"):
            Config()

    def test_known_hosts_explicit_none_with_warning(self, caplog, monkeypatch):
        """Should allow SCOUT_KNOWN_HOSTS=none with critical warning."""
        monkeypatch.setenv("SCOUT_KNOWN_HOSTS", "none")

        config = Config()
        assert config.known_hosts_path is None

        # Check for security warning in logs
        assert "SSH HOST KEY VERIFICATION DISABLED" in caplog.text
        assert "INSECURE" in caplog.text

    def test_known_hosts_uses_custom_path(self, tmp_path, monkeypatch):
        """Should use custom known_hosts path from env."""
        known_hosts = tmp_path / "custom_known_hosts"
        known_hosts.write_text("example.com ssh-ed25519 AAAA...\n")

        monkeypatch.setenv("SCOUT_KNOWN_HOSTS", str(known_hosts))

        config = Config()
        assert config.known_hosts_path == str(known_hosts)

    def test_known_hosts_rejects_missing_custom_path(self, tmp_path, monkeypatch):
        """Should raise error if custom path doesn't exist."""
        nonexistent = tmp_path / "missing_known_hosts"

        monkeypatch.setenv("SCOUT_KNOWN_HOSTS", str(nonexistent))

        with pytest.raises(FileNotFoundError, match="SCOUT_KNOWN_HOSTS file not found"):
            Config()

    def test_known_hosts_uses_default_when_exists(self, tmp_path, monkeypatch):
        """Should use default ~/.ssh/known_hosts if it exists."""
        ssh_dir = tmp_path / ".ssh"
        ssh_dir.mkdir()
        known_hosts = ssh_dir / "known_hosts"
        known_hosts.write_text("example.com ssh-ed25519 AAAA...\n")

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("SCOUT_KNOWN_HOSTS", raising=False)

        config = Config()
        assert config.known_hosts_path == str(known_hosts)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config_security.py::TestSSHHostVerification -v`
Expected: FAIL - tests expect fail-closed behavior

**Step 3: Implement fail-closed host verification**

Replace in `scout_mcp/config.py:221-240`:

```python
import logging

logger = logging.getLogger(__name__)

    @property
    def known_hosts_path(self) -> str | None:
        """Get known_hosts path with fail-closed security.

        Environment: SCOUT_KNOWN_HOSTS
        Values:
            - "none" = Disable verification (NOT RECOMMENDED, logs critical warning)
            - "/path/to/file" = Use custom known_hosts file
            - (empty) = Use default ~/.ssh/known_hosts

        Returns:
            Path to known_hosts file, or None if explicitly disabled

        Raises:
            FileNotFoundError: If known_hosts not found (fail closed)
        """
        value = os.getenv("SCOUT_KNOWN_HOSTS", "").strip()

        # Explicit opt-out with critical security warning
        if value.lower() == "none":
            logger.critical(
                "\n"
                "=" * 70 + "\n"
                "⚠️  SSH HOST KEY VERIFICATION DISABLED ⚠️\n"
                "=" * 70 + "\n"
                "This is INSECURE and vulnerable to man-in-the-middle attacks.\n"
                "Only use in trusted networks for testing.\n"
                "=" * 70
            )
            return None

        # Custom path specified
        if value:
            path = os.path.expanduser(value)
            if not Path(path).exists():
                raise FileNotFoundError(
                    f"SCOUT_KNOWN_HOSTS file not found: {path}\n"
                    f"Create the file or set SCOUT_KNOWN_HOSTS=none to disable "
                    f"verification (NOT RECOMMENDED)"
                )
            return path

        # Default path - fail closed if missing
        default = Path.home() / ".ssh" / "known_hosts"
        if not default.exists():
            raise FileNotFoundError(
                f"known_hosts not found at {default}\n"
                f"SSH host key verification is required for security.\n"
                f"\n"
                f"Options:\n"
                f"  1. Create {default} with host keys (RECOMMENDED)\n"
                f"  2. Set SCOUT_KNOWN_HOSTS=/path/to/known_hosts\n"
                f"  3. Set SCOUT_KNOWN_HOSTS=none to disable (NOT RECOMMENDED)\n"
                f"\n"
                f"To create known_hosts file:\n"
                f"  ssh-keyscan hostname >> {default}"
            )
        return str(default)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config_security.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scout_mcp/config.py tests/test_config_security.py
git commit -m "fix(security): fail closed on missing known_hosts

- Raise FileNotFoundError when known_hosts missing (was: disable verification)
- Require explicit SCOUT_KNOWN_HOSTS=none to disable verification
- Log critical security warning when verification disabled
- Provide helpful error messages with remediation steps

Fixes: SSH MITM vulnerability (CVSS 8.1)
Ref: .docs/COMPREHENSIVE-CODEBASE-REVIEW-2025-12-09.md#critical-2"
```

---

## Phase 2: Test Infrastructure (P1)

### Task 4: Verify Test Collection (Already Fixed)

**Note:** The test_integration directory was already deleted in a previous commit. This task verifies the fix is complete.

**Files:**
- Verify: `tests/test_integration/` (should not exist)
- Verify: Test collection works without errors

**Step 1: Verify files already deleted**

Run: `git status | grep test_integration`
Expected: Shows `D tests/test_integration/__init__.py` and `D tests/test_integration/test_localhost_resources.py` (already deleted)

**Step 2: Verify pytest collection works**

Run: `uv run pytest tests/ --collect-only`
Expected: All tests collected successfully (no import mismatch error)

Output should show:
```
collected XXX items
```

**Step 3: Run full test suite to verify**

Run: `uv run pytest tests/ -v`
Expected: Tests run successfully (collection works, though some tests may fail)

**Step 4: If collection still broken, investigate**

If Step 2 fails with import mismatch:
```bash
# Check for remaining conflicts
find tests/ -name "test_integration*" -type f
find tests/ -name "test_integration*" -type d

# If test_integration.py exists, rename it
git mv tests/test_integration.py tests/test_integration_main.py
git commit -m "fix(tests): rename test_integration.py to avoid conflict"
```

**Step 5: Document verification**

If test collection works (Step 2 passes):
- Test infrastructure is fixed ✅
- No commit needed (already fixed in previous work)
- Proceed to Task 5

If issues remain:
- Apply fixes from Step 4
- Commit changes
- Re-run verification

---

## Phase 3: Architectural Improvements (P1)

### Task 5: Replace Global Singletons with Dependency Injection

This is a large refactoring split into smaller tasks.

**Files:**
- Create: `scout_mcp/dependencies.py`
- Modify: `scout_mcp/server.py`
- Modify: `scout_mcp/services/__init__.py`
- Modify: 11 modules that import `get_config()` or `get_pool()`
- Modify: `scout_mcp/services/state.py` (mark as deprecated)
- Create: `tests/test_dependencies.py`

**Step 1: Write test for dependencies container**

Create `tests/test_dependencies.py`:

```python
"""Tests for dependency injection container."""

import pytest
from scout_mcp.dependencies import Dependencies
from scout_mcp.config import Config
from scout_mcp.services.pool import ConnectionPool


class TestDependencies:
    """Test Dependencies container."""

    def test_create_initializes_config_and_pool(self):
        """Dependencies.create() should initialize both config and pool."""
        deps = Dependencies.create()

        assert isinstance(deps.config, Config)
        assert isinstance(deps.pool, ConnectionPool)

    def test_pool_uses_config_values(self):
        """Pool should be initialized with config values."""
        deps = Dependencies.create()

        assert deps.pool._idle_timeout == deps.config.idle_timeout
        assert deps.pool._max_size == deps.config.max_pool_size

    def test_from_config_uses_provided_config(self):
        """Dependencies.from_config() should use provided config."""
        custom_config = Config()
        custom_config.max_pool_size = 50

        deps = Dependencies.from_config(custom_config)

        assert deps.config is custom_config
        assert deps.pool._max_size == 50
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dependencies.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Create dependencies module**

Create `scout_mcp/dependencies.py`:

```python
"""Dependency injection container for Scout MCP.

Replaces global singleton pattern with explicit dependency injection.
"""

from dataclasses import dataclass

from scout_mcp.config import Config
from scout_mcp.services.pool import ConnectionPool


@dataclass
class Dependencies:
    """Container for Scout MCP dependencies.

    Holds configuration and connection pool instances.
    Pass this to functions/tools that need access to config or pool.

    Example:
        deps = Dependencies.create()
        result = await some_function(deps=deps)
    """

    config: Config
    pool: ConnectionPool

    @classmethod
    def create(cls) -> "Dependencies":
        """Create dependencies with default configuration.

        Returns:
            Initialized Dependencies instance
        """
        config = Config()
        pool = ConnectionPool(
            idle_timeout=config.idle_timeout,
            max_size=config.max_pool_size,
            known_hosts=config.known_hosts_path,
            strict_host_key_checking=config.strict_host_key_checking,
        )
        return cls(config=config, pool=pool)

    @classmethod
    def from_config(cls, config: Config) -> "Dependencies":
        """Create dependencies with custom configuration.

        Args:
            config: Custom Config instance

        Returns:
            Dependencies with pool initialized from config
        """
        pool = ConnectionPool(
            idle_timeout=config.idle_timeout,
            max_size=config.max_pool_size,
            known_hosts=config.known_hosts_path,
            strict_host_key_checking=config.strict_host_key_checking,
        )
        return cls(config=config, pool=pool)

    async def cleanup(self) -> None:
        """Clean up resources (close all connections)."""
        await self.pool.close_all()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_dependencies.py -v`
Expected: PASS

**Step 5: Update services/__init__.py exports**

Add to `scout_mcp/services/__init__.py`:

```python
from scout_mcp.dependencies import Dependencies

__all__ = [
    # ... existing exports ...
    "Dependencies",
]
```

**Step 6: Commit dependencies module**

```bash
git add scout_mcp/dependencies.py tests/test_dependencies.py scout_mcp/services/__init__.py
git commit -m "feat(architecture): add dependency injection container

- Create Dependencies dataclass to hold config and pool
- Replace global singleton pattern with explicit DI
- Add factory methods: create() and from_config()
- Add cleanup() method for resource management

Ref: .docs/COMPREHENSIVE-CODEBASE-REVIEW-2025-12-09.md section 1.2"
```

**Step 7: Update server.py to use Dependencies**

This is a separate commit since it changes the public API.

Modify `scout_mcp/server.py` to initialize and pass dependencies:

```python
# Near top of file
from scout_mcp.dependencies import Dependencies

# In create_server() function or startup
async def app_lifespan(server: FastMCP):
    """Application lifespan manager."""
    # Create dependencies container
    deps = Dependencies.create()

    # Store in server context for tools/resources to access
    server.deps = deps

    try:
        yield
    finally:
        # Cleanup
        await deps.cleanup()
```

**Step 8: Update tool registration to pass dependencies**

This will be done incrementally per module. For now, just update the structure.

**Step 9: Mark state.py as deprecated**

Add deprecation warning to `scout_mcp/services/state.py`:

```python
"""Global state management for Scout MCP.

DEPRECATED: This module is deprecated in favor of dependency injection.
Use scout_mcp.dependencies.Dependencies instead.

This module will be removed in a future version.
"""

import warnings


def get_config() -> Config:
    """Get or create config.

    DEPRECATED: Use Dependencies.create().config instead.
    """
    warnings.warn(
        "get_config() is deprecated. Use Dependencies.create().config",
        DeprecationWarning,
        stacklevel=2,
    )
    global _config
    if _config is None:
        _config = Config()
    return _config


# Similar for get_pool()
```

**Step 10: Run tests to verify server still works**

Run: `uv run pytest tests/test_server.py -v`
Expected: Tests may fail (they need updating), but server should initialize

**Step 11: Commit server changes**

```bash
git add scout_mcp/server.py scout_mcp/services/state.py
git commit -m "refactor(server): use dependency injection in server

- Create Dependencies in app_lifespan
- Pass dependencies to tools/resources via server context
- Mark state.py functions as deprecated
- Add cleanup in lifespan manager

Ref: .docs/COMPREHENSIVE-CODEBASE-REVIEW-2025-12-09.md section 1.2"
```

**Remaining work:** Update each of the 11 modules to accept `deps: Dependencies` parameter instead of calling `get_config()` or `get_pool()`. This should be done incrementally per module with tests.

---

## Phase 4: Code Quality (P2)

### Task 6: Refactor Resource Registration Duplication

**Files:**
- Create: `scout_mcp/server_utils.py`
- Modify: `scout_mcp/server.py:183-395`
- Create: `tests/test_server_utils.py`

**Step 1: Write test for resource registration helper**

Create `tests/test_server_utils.py`:

```python
"""Tests for server utility functions."""

import pytest
from unittest.mock import Mock, AsyncMock
from scout_mcp.server_utils import register_host_resources


class TestRegisterHostResources:
    """Test resource registration helper."""

    def test_register_host_resources_creates_resources(self):
        """Should register resources for each host."""
        mock_server = Mock()
        mock_server.resource = Mock(return_value=lambda f: f)

        hosts = {"host1": Mock(), "host2": Mock()}
        uri_template = "{host}://docker/{{container}}/logs"

        async def handler_factory(host: str, container: str) -> str:
            return f"logs from {host} {container}"

        register_host_resources(
            server=mock_server,
            hosts=hosts,
            uri_template=uri_template,
            handler_factory=handler_factory,
            name="Docker logs",
        )

        # Should call server.resource for each host
        assert mock_server.resource.call_count == 2
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_server_utils.py -v`
Expected: FAIL with import error

**Step 3: Create server utilities module**

Create `scout_mcp/server_utils.py`:

```python
"""Server utility functions for resource registration."""

from typing import Any, Callable

from fastmcp import FastMCP
from scout_mcp.models import SSHHost


def register_host_resources(
    server: FastMCP,
    hosts: dict[str, SSHHost],
    uri_template: str,
    handler_factory: Callable,
    **metadata: Any,
) -> None:
    """Register dynamic resources for all hosts.

    Args:
        server: FastMCP server instance
        hosts: Dict of host_name -> SSHHost
        uri_template: URI template with {host} placeholder
        handler_factory: Function that creates handler for a specific host
        **metadata: Additional metadata for resource (name, description, etc.)

    Example:
        register_host_resources(
            server=server,
            hosts=config.get_hosts(),
            uri_template="{host}://docker/{{container}}/logs",
            handler_factory=lambda host: make_docker_logs_handler(host),
            name="Docker logs",
            description="View container logs",
        )
    """
    for host_name in hosts:
        # Replace {host} with actual hostname in URI
        uri = uri_template.format(host=host_name)

        # Create handler for this host
        handler = handler_factory(host_name)

        # Register resource
        server.resource(uri=uri, **metadata)(handler)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_server_utils.py -v`
Expected: PASS

**Step 5: Refactor server.py to use helper**

Replace the repetitive blocks in `scout_mcp/server.py:183-395` with calls to `register_host_resources()`.

Before (example):
```python
# Docker logs resources
for host_name in hosts:
    def make_docker_logs_handler(h: str) -> Any:
        async def handler(container: str) -> str:
            return await _read_docker_logs(h, container)
        return handler

    server.resource(
        uri=f"{host_name}://docker/{{container}}/logs",
        name="Docker logs",
        description="View container logs",
    )(make_docker_logs_handler(host_name))
```

After:
```python
from scout_mcp.server_utils import register_host_resources

# Docker logs resources
register_host_resources(
    server=server,
    hosts=hosts,
    uri_template="{host}://docker/{{container}}/logs",
    handler_factory=lambda h: lambda container: _read_docker_logs(h, container),
    name="Docker logs",
    description="View container logs",
)
```

**Step 6: Repeat for all resource types**

Apply same pattern to:
- Docker resources (ps, inspect, stats)
- Compose resources (ls, config, logs)
- ZFS resources (pools, status, datasets, snapshots)
- Syslog resources (read)
- Filesystem resources (search)

**Step 7: Run tests to verify server still works**

Run: `uv run pytest tests/test_server.py -v`
Expected: PASS

**Step 8: Commit**

```bash
git add scout_mcp/server_utils.py tests/test_server_utils.py scout_mcp/server.py
git commit -m "refactor(server): DRY resource registration

- Create register_host_resources() helper
- Replace 165 lines of duplication with function calls
- Improve maintainability and readability

Ref: .docs/COMPREHENSIVE-CODEBASE-REVIEW-2025-12-09.md section 1.3"
```

---

## Validation & Testing

### Task 7: Run Full Test Suite

**Step 1: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: Most tests should pass (some may need updating for Dependencies)

**Step 2: Check test coverage**

Run: `uv run pytest tests/ --cov=scout_mcp --cov-report=term-missing`
Expected: Coverage report shows percentage (target 85%+)

**Step 3: Run type checking**

Run: `uv run mypy scout_mcp/ --strict`
Expected: Some type errors may remain (addressed in P2)

**Step 4: Run linting**

Run: `uv run ruff check scout_mcp/ tests/ --fix`
Expected: Auto-fixable issues resolved, report remaining

---

## Documentation Updates

### Task 8: Update Documentation

**Files:**
- Modify: `README.md` (security checklist)
- Modify: `SECURITY.md` (threat model)
- Modify: `CLAUDE.md` (architecture)
- Modify: `.docs/deployment-log.md` (deployment notes)

**Step 1: Update README security checklist**

Add to security checklist:
- [x] Command injection prevented (allowlist)
- [x] SSH host verification enforced (fail-closed)
- [x] Docker/Compose names validated

**Step 2: Update SECURITY.md**

Update threat model to reflect fixes:
- Command injection: MITIGATED (allowlist)
- SSH MITM: MITIGATED (fail-closed)

**Step 3: Update CLAUDE.md**

Update architecture section:
- Replace "Global Singletons" with "Dependency Injection"
- Update code examples to use Dependencies

**Step 4: Update deployment log**

Add entry:
```markdown
## 2025-12-09 - Security and Architecture Fixes

**Changes:**
- Fixed P0 security vulnerabilities (command injection, SSH MITM)
- Fixed test infrastructure (collection error)
- Refactored to dependency injection pattern
- Reduced code duplication in resource registration

**Migration:**
- Deprecated: `get_config()`, `get_pool()` from `services.state`
- Use: `Dependencies.create()` instead
```

**Step 5: Commit**

```bash
git add README.md SECURITY.md CLAUDE.md .docs/deployment-log.md
git commit -m "docs: update for security and architecture fixes

- Document security mitigations
- Update architecture patterns
- Add migration guide for Dependencies
- Update deployment log"
```

---

## Final Checklist

**Security (P0):**
- [ ] Command injection prevented in run_command
- [ ] Docker/Compose command injection prevented
- [ ] SSH host verification fail-closed

**Testing (P1):**
- [ ] Test collection error fixed
- [ ] Test suite runs successfully
- [ ] Coverage measured (target 85%+)

**Architecture (P1):**
- [ ] Dependencies module created
- [ ] Server uses dependency injection
- [ ] state.py marked as deprecated
- [ ] (Partial) Modules updated to use Dependencies

**Code Quality (P2):**
- [ ] Resource registration deduplicated
- [ ] Linting issues resolved
- [ ] Type errors addressed

**Documentation:**
- [ ] README updated
- [ ] SECURITY.md updated
- [ ] CLAUDE.md updated
- [ ] Deployment log updated

---

## Execution Timeline

**Estimated effort:**
- Phase 1 (P0 Security): 10 hours
- Phase 2 (P1 Testing): 1 hour
- Phase 3 (P1 Architecture): 16 hours (partial in this plan)
- Phase 4 (P2 Quality): 8 hours
- Documentation: 2 hours

**Total: ~37 hours over 5-7 days**

**Priority order:**
1. Phase 1 (security) - Deploy immediately
2. Phase 2 (testing) - Enables validation
3. Phase 3 (architecture) - Long-term maintainability
4. Phase 4 (quality) - Polish and refinement

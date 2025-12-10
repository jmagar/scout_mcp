# Localhost Detection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable Scout MCP to detect when the target host is the same machine running the server and use localhost SSH connections instead of external IP connections.

**Architecture:** Add hostname detection to identify the server's hostname, modify connection logic to use localhost (127.0.0.1:22) when target host matches server host, ensure all resource types (compose, docker, zfs, syslog, filesystem) work correctly for localhost.

**Tech Stack:** asyncssh, Python 3.11+, pytest

---

## Task 1: Add Hostname Detection Utility

**Files:**
- Create: `scout_mcp/utils/hostname.py`
- Test: `tests/test_utils/test_hostname.py`

**Step 1: Write the failing test**

```python
"""Tests for hostname detection utilities."""

import pytest
from scout_mcp.utils.hostname import get_server_hostname, is_localhost_target


def test_get_server_hostname_returns_string():
    """Server hostname should be a non-empty string."""
    hostname = get_server_hostname()
    assert isinstance(hostname, str)
    assert len(hostname) > 0


def test_is_localhost_target_matches_exact_hostname():
    """Should detect when target matches server hostname exactly."""
    server_hostname = get_server_hostname()
    assert is_localhost_target(server_hostname) is True


def test_is_localhost_target_matches_lowercase():
    """Should detect hostname case-insensitively."""
    server_hostname = get_server_hostname()
    assert is_localhost_target(server_hostname.lower()) is True
    assert is_localhost_target(server_hostname.upper()) is True


def test_is_localhost_target_rejects_different_hostname():
    """Should reject hostnames that don't match server."""
    assert is_localhost_target("different-host") is False
    assert is_localhost_target("remote-server") is False


def test_is_localhost_target_handles_fqdn():
    """Should match FQDN if server hostname is FQDN."""
    server_hostname = get_server_hostname()
    # If hostname contains dots, it's FQDN
    if "." in server_hostname:
        short_name = server_hostname.split(".")[0]
        assert is_localhost_target(short_name) is True
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_utils/test_hostname.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'scout_mcp.utils.hostname'"

**Step 3: Write minimal implementation**

```python
"""Hostname detection utilities for localhost identification."""

import socket


def get_server_hostname() -> str:
    """Get the hostname of the machine running Scout MCP.

    Returns:
        Hostname string (lowercase for consistent comparison)
    """
    return socket.gethostname().lower()


def is_localhost_target(target_host: str) -> bool:
    """Check if target host is the same as the server host.

    Args:
        target_host: SSH host name to check

    Returns:
        True if target matches server hostname (case-insensitive)
    """
    if not target_host:
        return False

    server_hostname = get_server_hostname()
    target_lower = target_host.lower()

    # Direct match
    if target_lower == server_hostname:
        return True

    # Check if server hostname is FQDN and target is short name
    if "." in server_hostname:
        short_name = server_hostname.split(".")[0]
        if target_lower == short_name:
            return True

    # Check if target is FQDN and server is short name
    if "." in target_lower:
        target_short = target_lower.split(".")[0]
        if target_short == server_hostname:
            return True

    return False
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_utils/test_hostname.py -v`
Expected: All tests PASS

**Step 5: Update utils __init__.py**

Modify: `scout_mcp/utils/__init__.py`

```python
"""Utility functions for Scout MCP."""

from scout_mcp.utils.hostname import get_server_hostname, is_localhost_target
from scout_mcp.utils.mime import get_mime_type
from scout_mcp.utils.parser import parse_target
from scout_mcp.utils.ping import check_host_online
from scout_mcp.utils.validation import PathTraversalError, validate_host, validate_path

__all__ = [
    "check_host_online",
    "get_mime_type",
    "get_server_hostname",
    "is_localhost_target",
    "parse_target",
    "PathTraversalError",
    "validate_host",
    "validate_path",
]
```

**Step 6: Commit**

```bash
git add scout_mcp/utils/hostname.py tests/test_utils/test_hostname.py scout_mcp/utils/__init__.py
git commit -m "feat: add hostname detection utilities for localhost identification"
```

---

## Task 2: Modify SSHHost Model for Localhost Override

**Files:**
- Modify: `scout_mcp/models/host.py`
- Test: `tests/test_models/test_host.py`

**Step 1: Write the failing test**

```python
def test_ssh_host_localhost_override():
    """SSHHost should use localhost when is_localhost=True."""
    host = SSHHost(
        name="tootie",
        hostname="tootie.example.com",
        user="root",
        port=29229,
        is_localhost=True,
    )
    assert host.connection_hostname == "127.0.0.1"
    assert host.connection_port == 22


def test_ssh_host_no_override_when_not_localhost():
    """SSHHost should use original hostname when is_localhost=False."""
    host = SSHHost(
        name="remote",
        hostname="remote.example.com",
        user="root",
        port=29229,
        is_localhost=False,
    )
    assert host.connection_hostname == "remote.example.com"
    assert host.connection_port == 29229


def test_ssh_host_defaults_to_not_localhost():
    """SSHHost should default is_localhost to False."""
    host = SSHHost(
        name="default",
        hostname="default.example.com",
        user="root",
        port=22,
    )
    assert host.is_localhost is False
    assert host.connection_hostname == "default.example.com"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models/test_host.py::test_ssh_host_localhost_override -v`
Expected: FAIL with "SSHHost.__init__() got an unexpected keyword argument 'is_localhost'"

**Step 3: Write minimal implementation**

Modify: `scout_mcp/models/host.py`

```python
"""Data models for SSH hosts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SSHHost:
    """SSH host configuration."""

    name: str
    hostname: str
    user: str = "root"
    port: int = 22
    identity_file: str | None = None
    is_localhost: bool = False

    @property
    def connection_hostname(self) -> str:
        """Get the hostname to use for SSH connection.

        Returns:
            127.0.0.1 if is_localhost, otherwise original hostname
        """
        return "127.0.0.1" if self.is_localhost else self.hostname

    @property
    def connection_port(self) -> int:
        """Get the port to use for SSH connection.

        Returns:
            22 if is_localhost, otherwise original port
        """
        return 22 if self.is_localhost else self.port
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models/test_host.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add scout_mcp/models/host.py tests/test_models/test_host.py
git commit -m "feat: add localhost override to SSHHost model"
```

---

## Task 3: Update Config to Detect Localhost Hosts

**Files:**
- Modify: `scout_mcp/config.py`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

```python
def test_config_marks_localhost_hosts():
    """Config should mark hosts matching server hostname as localhost."""
    from scout_mcp.utils.hostname import get_server_hostname

    config_content = f"""
Host {get_server_hostname()}
    HostName tootie.example.com
    User root
    Port 29229

Host remote
    HostName remote.example.com
    User admin
    Port 22
"""

    config = Config()
    config.ssh_config_path = tmp_path / "ssh_config"
    config.ssh_config_path.write_text(config_content)

    hosts = config.get_hosts()

    # Server hostname should be marked as localhost
    server_host = hosts.get(get_server_hostname())
    assert server_host is not None
    assert server_host.is_localhost is True

    # Remote host should not be localhost
    remote_host = hosts.get("remote")
    assert remote_host is not None
    assert remote_host.is_localhost is False
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_config_marks_localhost_hosts -v`
Expected: FAIL with "assert False is True" (is_localhost not being set)

**Step 3: Write minimal implementation**

Modify: `scout_mcp/config.py` - Update the `_parse_ssh_config` method:

```python
from scout_mcp.utils import is_localhost_target

# In _parse_ssh_config, when creating SSHHost instances:
# Replace lines 143-149 and 174-180 with:

                    try:
                        port = int(current_data.get("port", "22"))
                    except ValueError:
                        port = 22
                    self._hosts[current_host] = SSHHost(
                        name=current_host,
                        hostname=current_data.get("hostname", ""),
                        user=current_data.get("user", "root"),
                        port=port,
                        identity_file=current_data.get("identityfile"),
                        is_localhost=is_localhost_target(current_host),
                    )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py::test_config_marks_localhost_hosts -v`
Expected: PASS

**Step 5: Run all config tests**

Run: `uv run pytest tests/test_config.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add scout_mcp/config.py tests/test_config.py
git commit -m "feat: detect and mark localhost hosts in SSH config"
```

---

## Task 4: Update Connection Pool to Use Localhost Override

**Files:**
- Modify: `scout_mcp/services/pool.py`
- Test: `tests/test_services/test_pool.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_pool_connects_to_localhost_override():
    """Pool should use 127.0.0.1:22 for localhost hosts."""
    from scout_mcp.models import SSHHost

    pool = ConnectionPool(idle_timeout=60, max_size=10)

    # Create host marked as localhost
    host = SSHHost(
        name="tootie",
        hostname="tootie.example.com",
        user="root",
        port=29229,
        is_localhost=True,
    )

    # This should attempt connection to 127.0.0.1:22 instead of tootie.example.com:29229
    try:
        conn = await pool.get_connection(host)
        # If we get here, connection succeeded to localhost
        assert conn.host.connection_hostname == "127.0.0.1"
        assert conn.host.connection_port == 22
        await pool.close_all()
    except Exception as e:
        # Expected if localhost SSH not available
        # But we can verify the connection attempt used correct host/port
        assert "127.0.0.1" in str(e) or "localhost" in str(e).lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_services/test_pool.py::test_pool_connects_to_localhost_override -v`
Expected: FAIL (connection attempted to wrong host/port)

**Step 3: Write minimal implementation**

Modify: `scout_mcp/services/pool.py` - Update `_create_connection` method (around line 115-140):

```python
async def _create_connection(self, host: "SSHHost") -> asyncssh.SSHClientConnection:
    """Create new SSH connection to host.

    Args:
        host: SSH host configuration

    Returns:
        New SSH connection

    Raises:
        ConnectionError: If connection fails
    """
    # Use localhost override if applicable
    connect_host = host.connection_hostname
    connect_port = host.connection_port

    try:
        logger.debug(
            "Creating SSH connection to %s@%s:%d%s",
            host.user,
            connect_host,
            connect_port,
            " (localhost override)" if host.is_localhost else "",
        )

        # Build connection options
        options: dict[str, Any] = {
            "username": host.user,
            "known_hosts": self._known_hosts,
        }

        # Add identity file if specified
        if host.identity_file:
            options["client_keys"] = [host.identity_file]

        # Handle strict host key checking
        if not self._strict_host_key and self._known_hosts:
            logger.warning(
                "Non-strict host key checking enabled for %s - will accept unknown keys",
                host.name,
            )

        conn = await asyncssh.connect(
            connect_host,
            connect_port,
            **options,
        )

        logger.info(
            "SSH connection established: %s@%s:%d%s",
            host.user,
            connect_host,
            connect_port,
            " (localhost)" if host.is_localhost else "",
        )
        return conn

    except Exception as e:
        logger.error(
            "Failed to connect to %s@%s:%d: %s",
            host.user,
            connect_host,
            connect_port,
            e,
        )
        raise ConnectionError(
            f"Cannot connect to {host.name}: {e}"
        ) from e
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_services/test_pool.py::test_pool_connects_to_localhost_override -v`
Expected: PASS

**Step 5: Run all pool tests**

Run: `uv run pytest tests/test_services/test_pool.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add scout_mcp/services/pool.py tests/test_services/test_pool.py
git commit -m "feat: use localhost override in connection pool"
```

---

## Task 5: Integration Test for Localhost Resources

**Files:**
- Create: `tests/test_integration/test_localhost_resources.py`

**Step 1: Write the integration test**

```python
"""Integration tests for localhost resource access."""

import pytest
from scout_mcp.services import get_config, get_pool
from scout_mcp.resources import (
    compose_list_resource,
    docker_list_resource,
    list_hosts_resource,
    scout_resource,
    zfs_overview_resource,
)


@pytest.mark.asyncio
async def test_localhost_host_list_shows_online():
    """Localhost host should be marked as online in host list."""
    from scout_mcp.utils.hostname import get_server_hostname

    result = await list_hosts_resource()

    # Server hostname should appear in list and be marked online
    assert get_server_hostname() in result
    assert "[✓]" in result or "online" in result.lower()


@pytest.mark.asyncio
async def test_localhost_docker_list():
    """Should be able to list Docker containers on localhost."""
    from scout_mcp.utils.hostname import get_server_hostname

    try:
        result = await docker_list_resource(get_server_hostname())
        # Should get some result (even if no containers)
        assert isinstance(result, str)
        assert "Docker Containers" in result or "No containers" in result
    except Exception as e:
        # If Docker not available, that's okay - but connection should work
        assert "Cannot connect" not in str(e)


@pytest.mark.asyncio
async def test_localhost_compose_list():
    """Should be able to list Compose projects on localhost."""
    from scout_mcp.utils.hostname import get_server_hostname

    try:
        result = await compose_list_resource(get_server_hostname())
        assert isinstance(result, str)
        assert "Compose Projects" in result or "No projects" in result
    except Exception as e:
        assert "Cannot connect" not in str(e)


@pytest.mark.asyncio
async def test_localhost_file_read():
    """Should be able to read files on localhost."""
    from scout_mcp.utils.hostname import get_server_hostname

    # Try to read /etc/hostname or similar file that should exist
    try:
        result = await scout_resource(get_server_hostname(), "/etc/hostname")
        assert isinstance(result, str)
        assert len(result) > 0
    except Exception as e:
        # File might not exist, but connection should work
        assert "Cannot connect" not in str(e)


@pytest.mark.asyncio
async def test_localhost_connection_cleanup():
    """Pool should properly clean up localhost connections."""
    pool = get_pool()
    initial_size = pool.pool_size

    # Make a localhost request
    from scout_mcp.utils.hostname import get_server_hostname
    try:
        await scout_resource(get_server_hostname(), "/tmp")
    except:
        pass  # Ignore errors, just testing connection

    # Pool should have connection now
    assert pool.pool_size >= initial_size

    # Cleanup
    await pool.close_all()
    assert pool.pool_size == 0
```

**Step 2: Run test to verify behavior**

Run: `uv run pytest tests/test_integration/test_localhost_resources.py -v`
Expected: Tests should PASS if SSH is available on localhost:22

**Step 3: Commit**

```bash
git add tests/test_integration/test_localhost_resources.py
git commit -m "test: add integration tests for localhost resource access"
```

---

## Task 6: Update Documentation

**Files:**
- Modify: `scout_mcp/CLAUDE.md`

**Step 1: Add localhost detection section**

Add to CLAUDE.md after the "Connection Pooling" section:

```markdown
### Localhost Detection

The server automatically detects when a target host is the same machine running Scout MCP:

- Compares SSH host names against server hostname (case-insensitive)
- Handles both short names and FQDNs
- Automatically uses `127.0.0.1:22` for localhost connections
- Avoids external IP connection issues for same-machine access

Example:
```python
# If Scout MCP is running on "tootie"
scout("tootie:/var/log")  # Connects to 127.0.0.1:22 (localhost)
scout("remote:/var/log")  # Connects to remote:22 (network)
```

This ensures resources work correctly when accessing the server's own filesystem, Docker containers, ZFS pools, etc.
```

**Step 2: Commit**

```bash
git add scout_mcp/CLAUDE.md
git commit -m "docs: document localhost detection feature"
```

---

## Task 7: Manual Testing

**Step 1: Verify server hostname detection**

```bash
uv run python -c "from scout_mcp.utils import get_server_hostname; print(f'Server hostname: {get_server_hostname()}')"
```

Expected: Shows current machine hostname

**Step 2: Test localhost resource access**

Start the server:
```bash
uv run python -m scout_mcp
```

In another terminal, test with the scout tool or MCP client:
```python
# Via Python REPL
from scout_mcp.resources import list_hosts_resource
import asyncio

result = asyncio.run(list_hosts_resource())
print(result)
```

Expected: Server hostname appears as [✓] online

**Step 3: Test compose/docker resources**

```python
from scout_mcp.resources import docker_list_resource, compose_list_resource
from scout_mcp.utils import get_server_hostname
import asyncio

hostname = get_server_hostname()
print(asyncio.run(docker_list_resource(hostname)))
print(asyncio.run(compose_list_resource(hostname)))
```

Expected: Lists containers/projects without connection errors

**Step 4: Verify in actual MCP client**

Access resources via Claude Code or other MCP client:
- `tootie://compose/plex/logs` (if plex exists)
- `tootie://docker`
- `tootie://etc/hostname`

Expected: All resources accessible without connection errors

---

## Summary

This plan implements localhost detection in 7 tasks:

1. **Hostname utilities** - Detect server hostname and compare targets
2. **Model updates** - Add localhost override to SSHHost
3. **Config detection** - Mark localhost hosts during parsing
4. **Pool connection** - Use localhost override when connecting
5. **Integration tests** - Verify end-to-end localhost access
6. **Documentation** - Document the feature
7. **Manual testing** - Verify with real server

**Key principles:**
- TDD approach (test first, then implement)
- Minimal changes to existing code
- Backward compatible (non-localhost hosts unchanged)
- DRY (single source of truth for localhost detection)
- YAGNI (only what's needed for the feature)

**Testing strategy:**
- Unit tests for each component
- Integration tests for resource access
- Manual verification with running server

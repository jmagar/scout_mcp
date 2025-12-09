# Remote-to-Remote Beam Transfer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable file transfers between two remote hosts using the beam parameter, with automatic detection of optimal transfer path.

**Architecture:** Extend existing beam functionality to support explicit source/target specification. When both endpoints are remote, relay through local temp directory. Auto-detect current hostname to optimize transfers when MCP server runs on one of the endpoints.

**Tech Stack:** Python 3.11+, asyncssh, pytest, existing scout_mcp architecture

---

## Background

**Current behavior:**
- `scout("host:/remote/file", beam="/local/file")` - Auto-detects direction based on local file existence
- Only supports transfers between local machine (MCP server) and one remote host
- Uses SFTP via asyncssh

**Desired behavior:**
- Support `scout("hostA:/path/file", beam_source="hostB:/path/file")` - Transfer from hostB to hostA
- Support `scout("hostA:/path/file", beam_target="hostB:/path/file")` - Transfer from hostA to hostB
- Auto-detect if MCP server is on one of the hosts to optimize transfer
- Maintain backward compatibility with existing `beam` parameter

**Transfer scenarios:**
1. **Local → Remote** (current) - Direct SFTP upload
2. **Remote → Local** (current) - Direct SFTP download
3. **Remote → Remote via relay** (new) - Download to temp, upload to destination
4. **Current host → Remote** (optimization) - Direct SFTP when MCP server is source
5. **Remote → Current host** (optimization) - Direct SFTP when MCP server is target

---

## Task 1: Add Hostname Detection Utility

**Files:**
- Create: `scout_mcp/utils/hostname.py`
- Test: `tests/test_utils/test_hostname.py`

**Step 1: Write failing test for hostname detection**

```python
"""Test hostname detection utilities."""

import pytest
from scout_mcp.utils.hostname import get_local_hostname, get_short_hostname


def test_get_local_hostname_returns_string():
    """Test that hostname detection returns a non-empty string."""
    hostname = get_local_hostname()
    assert isinstance(hostname, str)
    assert len(hostname) > 0


def test_get_short_hostname_strips_domain():
    """Test that short hostname removes domain suffix."""
    # Test with FQDN
    short = get_short_hostname("tootie.example.com")
    assert short == "tootie"

    # Test with just hostname
    short = get_short_hostname("tootie")
    assert short == "tootie"

    # Test with empty string
    short = get_short_hostname("")
    assert short == ""


def test_get_local_hostname_cacheable():
    """Test that hostname detection is consistent."""
    hostname1 = get_local_hostname()
    hostname2 = get_local_hostname()
    assert hostname1 == hostname2
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_utils/test_hostname.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'scout_mcp.utils.hostname'"

**Step 3: Write minimal implementation**

```python
"""Hostname detection utilities."""

import socket


def get_local_hostname() -> str:
    """Get the local machine's hostname.

    Returns:
        Hostname as string (may include domain).

    Examples:
        >>> get_local_hostname()
        'tootie.example.com'
    """
    return socket.gethostname()


def get_short_hostname(hostname: str) -> str:
    """Extract short hostname from FQDN.

    Args:
        hostname: Full hostname (may include domain)

    Returns:
        Short hostname without domain suffix.

    Examples:
        >>> get_short_hostname("tootie.example.com")
        'tootie'
        >>> get_short_hostname("tootie")
        'tootie'
    """
    if not hostname:
        return ""

    return hostname.split(".")[0]
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_utils/test_hostname.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add scout_mcp/utils/hostname.py tests/test_utils/test_hostname.py
git commit -m "feat: add hostname detection utilities

- Add get_local_hostname() using socket.gethostname()
- Add get_short_hostname() to strip domain suffix
- Include tests for both functions"
```

---

## Task 2: Add Transfer Path Detection Logic

**Files:**
- Create: `scout_mcp/utils/transfer.py`
- Test: `tests/test_utils/test_transfer.py`

**Step 1: Write failing test for transfer path detection**

```python
"""Test transfer path detection logic."""

import pytest
from scout_mcp.utils.transfer import (
    TransferPath,
    TransferStrategy,
    determine_transfer_strategy,
)


def test_determine_strategy_local_to_remote():
    """Test detection of local → remote transfer."""
    strategy = determine_transfer_strategy(
        source_host=None,
        target_host="remote1",
        current_hostname="localhost",
    )

    assert strategy == TransferStrategy.LOCAL_TO_REMOTE
    assert strategy.source_host is None
    assert strategy.target_host == "remote1"


def test_determine_strategy_remote_to_local():
    """Test detection of remote → local transfer."""
    strategy = determine_transfer_strategy(
        source_host="remote1",
        target_host=None,
        current_hostname="localhost",
    )

    assert strategy == TransferStrategy.REMOTE_TO_LOCAL
    assert strategy.source_host == "remote1"
    assert strategy.target_host is None


def test_determine_strategy_remote_to_remote_via_relay():
    """Test detection of remote → remote transfer requiring relay."""
    strategy = determine_transfer_strategy(
        source_host="remote1",
        target_host="remote2",
        current_hostname="localhost",
    )

    assert strategy == TransferStrategy.REMOTE_TO_REMOTE_RELAY
    assert strategy.source_host == "remote1"
    assert strategy.target_host == "remote2"


def test_determine_strategy_optimized_current_as_source():
    """Test optimization when MCP server is the source host."""
    strategy = determine_transfer_strategy(
        source_host="tootie",
        target_host="remote1",
        current_hostname="tootie",
    )

    assert strategy == TransferStrategy.LOCAL_TO_REMOTE
    assert strategy.source_host is None  # Optimized to local
    assert strategy.target_host == "remote1"


def test_determine_strategy_optimized_current_as_target():
    """Test optimization when MCP server is the target host."""
    strategy = determine_transfer_strategy(
        source_host="remote1",
        target_host="tootie",
        current_hostname="tootie",
    )

    assert strategy == TransferStrategy.REMOTE_TO_LOCAL
    assert strategy.source_host == "remote1"
    assert strategy.target_host is None  # Optimized to local


def test_determine_strategy_same_source_and_target():
    """Test error when source and target are the same."""
    with pytest.raises(ValueError, match="Source and target cannot be the same"):
        determine_transfer_strategy(
            source_host="remote1",
            target_host="remote1",
            current_hostname="localhost",
        )
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_utils/test_transfer.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'scout_mcp.utils.transfer'"

**Step 3: Write minimal implementation**

```python
"""Transfer path detection and strategy selection."""

from dataclasses import dataclass
from enum import Enum


class TransferStrategy(Enum):
    """Transfer strategy based on endpoint locations."""

    LOCAL_TO_REMOTE = "local_to_remote"
    REMOTE_TO_LOCAL = "remote_to_local"
    REMOTE_TO_REMOTE_RELAY = "remote_to_remote_relay"


@dataclass
class TransferPath:
    """Resolved transfer path with strategy."""

    strategy: TransferStrategy
    source_host: str | None  # None if local
    target_host: str | None  # None if local
    source_path: str
    target_path: str


def determine_transfer_strategy(
    source_host: str | None,
    target_host: str | None,
    current_hostname: str,
) -> TransferPath:
    """Determine optimal transfer strategy based on endpoint locations.

    Args:
        source_host: Source hostname (None if local)
        target_host: Target hostname (None if local)
        current_hostname: Hostname of machine running MCP server

    Returns:
        TransferPath with resolved strategy and optimized endpoints.

    Raises:
        ValueError: If source and target are the same host.

    Examples:
        >>> determine_transfer_strategy(None, "remote1", "localhost")
        TransferPath(strategy=LOCAL_TO_REMOTE, source_host=None, target_host="remote1")

        >>> determine_transfer_strategy("remote1", "remote2", "localhost")
        TransferPath(strategy=REMOTE_TO_REMOTE_RELAY, ...)

        >>> determine_transfer_strategy("tootie", "remote1", "tootie")
        TransferPath(strategy=LOCAL_TO_REMOTE, source_host=None, target_host="remote1")
    """
    # Validate not same host
    if source_host and target_host and source_host == target_host:
        raise ValueError(
            f"Source and target cannot be the same host: {source_host}"
        )

    # Optimize: if source is current host, treat as local
    if source_host == current_hostname:
        source_host = None

    # Optimize: if target is current host, treat as local
    if target_host == current_hostname:
        target_host = None

    # Determine strategy
    if source_host is None and target_host is not None:
        strategy = TransferStrategy.LOCAL_TO_REMOTE
    elif source_host is not None and target_host is None:
        strategy = TransferStrategy.REMOTE_TO_LOCAL
    elif source_host is not None and target_host is not None:
        strategy = TransferStrategy.REMOTE_TO_REMOTE_RELAY
    else:
        raise ValueError("Cannot transfer from local to local")

    # Return without paths (will be added by caller)
    return TransferPath(
        strategy=strategy,
        source_host=source_host,
        target_host=target_host,
        source_path="",  # Placeholder
        target_path="",  # Placeholder
    )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_utils/test_transfer.py -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add scout_mcp/utils/transfer.py tests/test_utils/test_transfer.py
git commit -m "feat: add transfer path detection logic

- Add TransferStrategy enum for transfer types
- Add TransferPath dataclass for resolved paths
- Add determine_transfer_strategy() with optimization
- Auto-optimize when MCP server is source or target
- Include comprehensive tests for all scenarios"
```

---

## Task 3: Add Remote-to-Remote Transfer Executor

**Files:**
- Modify: `scout_mcp/services/executors.py`
- Test: `tests/test_executors.py`

**Step 1: Write failing test for remote-to-remote transfer**

```python
"""Test remote-to-remote beam transfer."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from scout_mcp.services.executors import beam_transfer_remote_to_remote, TransferResult


@pytest.mark.asyncio
async def test_beam_transfer_remote_to_remote_success(tmp_path):
    """Test successful remote-to-remote transfer via relay."""
    # Mock connections
    source_conn = AsyncMock()
    target_conn = AsyncMock()

    # Mock SFTP clients
    source_sftp = AsyncMock()
    target_sftp = AsyncMock()

    source_conn.start_sftp_client.return_value.__aenter__.return_value = source_sftp
    target_conn.start_sftp_client.return_value.__aenter__.return_value = target_conn

    # Mock file download/upload
    test_content = b"test file content"
    source_sftp.get.return_value = None  # Download succeeds
    target_sftp.put.return_value = None  # Upload succeeds

    with patch("scout_mcp.services.executors.Path") as mock_path:
        mock_temp_file = MagicMock()
        mock_temp_file.exists.return_value = True
        mock_temp_file.stat.return_value.st_size = len(test_content)
        mock_path.return_value = mock_temp_file

        result = await beam_transfer_remote_to_remote(
            source_conn=source_conn,
            target_conn=target_conn,
            source_path="/remote1/file.txt",
            target_path="/remote2/file.txt",
        )

    assert result.success is True
    assert "Transferred" in result.message
    assert result.bytes_transferred == len(test_content)

    # Verify download was called
    source_sftp.get.assert_called_once()

    # Verify upload was called
    target_sftp.put.assert_called_once()


@pytest.mark.asyncio
async def test_beam_transfer_remote_to_remote_download_fails():
    """Test remote-to-remote transfer when download fails."""
    source_conn = AsyncMock()
    target_conn = AsyncMock()

    source_sftp = AsyncMock()
    source_sftp.get.side_effect = Exception("Download failed")

    source_conn.start_sftp_client.return_value.__aenter__.return_value = source_sftp

    result = await beam_transfer_remote_to_remote(
        source_conn=source_conn,
        target_conn=target_conn,
        source_path="/remote1/file.txt",
        target_path="/remote2/file.txt",
    )

    assert result.success is False
    assert "Download failed" in result.message


@pytest.mark.asyncio
async def test_beam_transfer_remote_to_remote_upload_fails(tmp_path):
    """Test remote-to-remote transfer when upload fails."""
    source_conn = AsyncMock()
    target_conn = AsyncMock()

    source_sftp = AsyncMock()
    target_sftp = AsyncMock()

    source_sftp.get.return_value = None  # Download succeeds
    target_sftp.put.side_effect = Exception("Upload failed")

    source_conn.start_sftp_client.return_value.__aenter__.return_value = source_sftp
    target_conn.start_sftp_client.return_value.__aenter__.return_value = target_sftp

    with patch("scout_mcp.services.executors.Path") as mock_path:
        mock_temp_file = MagicMock()
        mock_temp_file.exists.return_value = True
        mock_path.return_value = mock_temp_file

        result = await beam_transfer_remote_to_remote(
            source_conn=source_conn,
            target_conn=target_conn,
            source_path="/remote1/file.txt",
            target_path="/remote2/file.txt",
        )

    assert result.success is False
    assert "Upload failed" in result.message
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_executors.py::test_beam_transfer_remote_to_remote_success -v`
Expected: FAIL with "ImportError: cannot import name 'beam_transfer_remote_to_remote'"

**Step 3: Write minimal implementation**

Add to `scout_mcp/services/executors.py` (after existing `beam_transfer` function):

```python
async def beam_transfer_remote_to_remote(
    source_conn: "asyncssh.SSHClientConnection",
    target_conn: "asyncssh.SSHClientConnection",
    source_path: str,
    target_path: str,
) -> TransferResult:
    """Transfer file from one remote host to another via local relay.

    Downloads file from source to local temp directory, then uploads to target.
    Cleans up temp file after transfer completes or fails.

    Args:
        source_conn: SSH connection to source host
        target_conn: SSH connection to target host
        source_path: Path to file on source host
        target_path: Path to destination on target host

    Returns:
        TransferResult with success status, message, and bytes transferred.

    Raises:
        RuntimeError: If download or upload fails.
    """
    import tempfile

    # Create temp file for relay
    temp_file = None

    try:
        # Download from source to temp
        with tempfile.NamedTemporaryFile(delete=False, prefix="scout_beam_") as tf:
            temp_file = Path(tf.name)

        try:
            async with source_conn.start_sftp_client() as source_sftp:
                await source_sftp.get(source_path, str(temp_file))
        except Exception as e:
            return TransferResult(
                success=False,
                message=f"Download from source failed: {e}",
                bytes_transferred=0,
            )

        # Verify download succeeded
        if not temp_file.exists():
            return TransferResult(
                success=False,
                message="Download completed but temp file not found",
                bytes_transferred=0,
            )

        file_size = temp_file.stat().st_size

        # Upload from temp to target
        try:
            async with target_conn.start_sftp_client() as target_sftp:
                await target_sftp.put(str(temp_file), target_path)
        except Exception as e:
            return TransferResult(
                success=False,
                message=f"Upload to target failed: {e}",
                bytes_transferred=0,
            )

        return TransferResult(
            success=True,
            message=f"Transferred {source_path} → {target_path} (via relay)",
            bytes_transferred=file_size,
        )

    finally:
        # Clean up temp file
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass  # Best effort cleanup
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_executors.py -k beam_transfer_remote_to_remote -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add scout_mcp/services/executors.py tests/test_executors.py
git commit -m "feat: add remote-to-remote beam transfer executor

- Add beam_transfer_remote_to_remote() for relay transfers
- Download from source to temp, upload to target
- Automatic temp file cleanup in finally block
- Include tests for success and failure scenarios"
```

---

## Task 4: Update Scout Tool to Support beam_source/beam_target

**Files:**
- Modify: `scout_mcp/tools/scout.py`
- Modify: `scout_mcp/tools/handlers.py`
- Test: `tests/test_scout.py`

**Step 1: Write failing test for new parameters**

```python
"""Test scout tool with beam_source/beam_target parameters."""

import pytest
from unittest.mock import AsyncMock, patch

from scout_mcp.tools.scout import scout


@pytest.mark.asyncio
async def test_scout_beam_source_and_target_remote_to_remote():
    """Test remote-to-remote transfer with beam_source and beam_target."""
    with patch("scout_mcp.tools.scout.get_config") as mock_config, \
         patch("scout_mcp.tools.scout.get_pool") as mock_pool, \
         patch("scout_mcp.tools.handlers.handle_beam_transfer_remote_to_remote") as mock_handler:

        # Mock config
        config = AsyncMock()
        config.get_host.side_effect = lambda name: AsyncMock(name=name)
        mock_config.return_value = config

        # Mock handler
        mock_handler.return_value = "✓ Transferred remote1:/src → remote2:/dst"

        result = await scout(
            target="",  # Not used for remote-to-remote
            beam_source="remote1:/src/file.txt",
            beam_target="remote2:/dst/file.txt",
        )

        assert "Transferred" in result
        mock_handler.assert_called_once()


@pytest.mark.asyncio
async def test_scout_beam_source_without_target_error():
    """Test error when beam_source provided without beam_target."""
    result = await scout(
        target="",
        beam_source="remote1:/file.txt",
    )

    assert "Error" in result
    assert "beam_target" in result


@pytest.mark.asyncio
async def test_scout_beam_target_without_source_error():
    """Test error when beam_target provided without beam_source."""
    result = await scout(
        target="",
        beam_target="remote2:/file.txt",
    )

    assert "Error" in result
    assert "beam_source" in result


@pytest.mark.asyncio
async def test_scout_beam_with_beam_source_error():
    """Test error when both beam and beam_source provided."""
    result = await scout(
        target="remote1:/file.txt",
        beam="/local/file.txt",
        beam_source="remote2:/file.txt",
    )

    assert "Error" in result
    assert "cannot use both" in result.lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_scout.py -k beam_source -v`
Expected: FAIL with "TypeError: scout() got an unexpected keyword argument 'beam_source'"

**Step 3: Update scout() signature and add validation**

Modify `scout_mcp/tools/scout.py`:

```python
async def scout(
    target: str = "",
    query: str | None = None,
    tree: bool = False,
    find: str | None = None,
    depth: int = 5,
    diff: str | None = None,
    diff_content: str | None = None,
    targets: list[str] | None = None,
    beam: str | None = None,
    beam_source: str | None = None,
    beam_target: str | None = None,
) -> str:
    """Scout remote files and directories via SSH.

    Args:
        target: Either 'hosts' to list available hosts,
            or 'hostname:/path' to target a path.
        targets: List of targets for multi-host broadcast operations.
        query: Optional shell command to execute.
        tree: If True, show directory tree instead of ls -la.
        find: Glob pattern to search for files.
        depth: Maximum depth for find operations (default: 5).
        diff: Another target to compare against (e.g., "host2:/path").
        diff_content: Expected content to compare file against.
        beam: Local path for file transfer (backward compatible).
              If local file exists → upload to remote target.
              If local file doesn't exist → download from remote target.
        beam_source: Source for remote-to-remote transfer (format: "host:/path").
        beam_target: Target for remote-to-remote transfer (format: "host:/path").

    Examples:
        # Existing beam (backward compatible)
        scout("shart:/tmp/remote.txt", beam="/tmp/local.txt")

        # New remote-to-remote transfer
        scout(beam_source="shart:/tmp/file.txt", beam_target="squirts:/tmp/file.txt")

    Returns:
        File contents, directory listing, command output, search results,
        diff output, host list, transfer result, or formatted multi-host results.
    """
    config = get_config()
    pool = get_pool()

    # Validate beam parameters
    if beam and (beam_source or beam_target):
        return (
            "Error: Cannot use both 'beam' and 'beam_source/beam_target'. "
            "Use 'beam' for local transfers or 'beam_source/beam_target' for remote-to-remote."
        )

    if beam_source and not beam_target:
        return "Error: beam_source requires beam_target to be specified."

    if beam_target and not beam_source:
        return "Error: beam_target requires beam_source to be specified."

    # Handle remote-to-remote beam transfer
    if beam_source and beam_target:
        from scout_mcp.tools.handlers import handle_beam_transfer_remote_to_remote

        return await handle_beam_transfer_remote_to_remote(
            config,
            beam_source,
            beam_target,
        )

    # ... rest of existing scout() implementation ...
```

**Step 4: Add handler for remote-to-remote transfers**

Add to `scout_mcp/tools/handlers.py`:

```python
async def handle_beam_transfer_remote_to_remote(
    config: "Config",
    beam_source: str,
    beam_target: str,
) -> str:
    """Handle remote-to-remote file transfer.

    Args:
        config: Scout configuration
        beam_source: Source in format "host:/path"
        beam_target: Target in format "host:/path"

    Returns:
        Status message describing transfer result.
    """
    from scout_mcp.utils.parser import parse_target
    from scout_mcp.utils.hostname import get_local_hostname, get_short_hostname
    from scout_mcp.utils.transfer import determine_transfer_strategy
    from scout_mcp.services import get_connection_with_retry
    from scout_mcp.services.executors import beam_transfer, beam_transfer_remote_to_remote

    # Parse source and target
    try:
        source_parsed = parse_target(beam_source)
        target_parsed = parse_target(beam_target)
    except ValueError as e:
        return f"Error: {e}"

    # Validate both are host:/path format
    if source_parsed.is_hosts_command or source_parsed.host is None:
        return "Error: beam_source must be in format 'host:/path'"

    if target_parsed.is_hosts_command or target_parsed.host is None:
        return "Error: beam_target must be in format 'host:/path'"

    # Get SSH host configs
    source_ssh_host = config.get_host(source_parsed.host)
    if source_ssh_host is None:
        available = ", ".join(sorted(config.get_hosts().keys()))
        return f"Error: Unknown source host '{source_parsed.host}'. Available: {available}"

    target_ssh_host = config.get_host(target_parsed.host)
    if target_ssh_host is None:
        available = ", ".join(sorted(config.get_hosts().keys()))
        return f"Error: Unknown target host '{target_parsed.host}'. Available: {available}"

    # Detect current hostname for optimization
    current_hostname = get_short_hostname(get_local_hostname())

    # Determine transfer strategy
    source_host = source_parsed.host if source_parsed.host != current_hostname else None
    target_host = target_parsed.host if target_parsed.host != current_hostname else None

    try:
        # Case 1: Optimized to local → remote (source is current host)
        if source_host is None and target_host is not None:
            target_conn = await get_connection_with_retry(target_ssh_host)
            result = await beam_transfer(
                target_conn,
                source_parsed.path,  # Local path
                target_parsed.path,  # Remote path
                "upload",
            )

        # Case 2: Optimized to remote → local (target is current host)
        elif source_host is not None and target_host is None:
            source_conn = await get_connection_with_retry(source_ssh_host)
            result = await beam_transfer(
                source_conn,
                source_parsed.path,  # Remote path
                target_parsed.path,  # Local path
                "download",
            )

        # Case 3: Remote → remote (neither is current host)
        elif source_host is not None and target_host is not None:
            source_conn = await get_connection_with_retry(source_ssh_host)
            target_conn = await get_connection_with_retry(target_ssh_host)
            result = await beam_transfer_remote_to_remote(
                source_conn,
                target_conn,
                source_parsed.path,
                target_parsed.path,
            )

        else:
            return "Error: Cannot transfer from local to local"

        # Format result
        if result.success:
            size_kb = result.bytes_transferred / 1024
            return f"✓ {result.message}\n  Size: {size_kb:.2f} KB"
        else:
            return f"✗ Transfer failed: {result.message}"

    except Exception as e:
        return f"Error: Beam transfer failed: {e}"
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_scout.py -k beam_source -v`
Expected: PASS (4 tests)

**Step 6: Commit**

```bash
git add scout_mcp/tools/scout.py scout_mcp/tools/handlers.py tests/test_scout.py
git commit -m "feat: add beam_source/beam_target parameters to scout

- Add beam_source and beam_target parameters for remote-to-remote
- Add handle_beam_transfer_remote_to_remote() handler
- Auto-optimize when MCP server is source or target
- Validate parameter combinations
- Maintain backward compatibility with existing beam parameter
- Include comprehensive tests"
```

---

## Task 5: Update Documentation

**Files:**
- Modify: `scout_mcp/CLAUDE.md`
- Modify: `scout_mcp/scout_mcp/tools/CLAUDE.md`
- Modify: `README.md` (if exists)

**Step 1: Update tool documentation**

Modify `scout_mcp/scout_mcp/tools/CLAUDE.md`:

Add to Examples section:

```markdown
# Remote-to-Remote Transfers

# Transfer between two remote hosts
scout(beam_source="shart:/mnt/data/file.txt", beam_target="squirts:/backup/file.txt")

# Optimized: If MCP server runs on shart, this becomes a direct upload
scout(beam_source="shart:/local/file.txt", beam_target="squirts:/remote/file.txt")

# Optimized: If MCP server runs on squirts, this becomes a direct download
scout(beam_source="shart:/remote/file.txt", beam_target="squirts:/local/file.txt")
```

**Step 2: Update main documentation**

Modify `scout_mcp/CLAUDE.md`:

Update "Scout Tool" section with new examples.

**Step 3: Commit**

```bash
git add scout_mcp/CLAUDE.md scout_mcp/scout_mcp/tools/CLAUDE.md
git commit -m "docs: add remote-to-remote beam transfer examples

- Document beam_source and beam_target parameters
- Add examples for all transfer scenarios
- Document optimization when MCP server is endpoint
- Update tool and main documentation"
```

---

## Task 6: Integration Testing

**Files:**
- Create: `tests/test_beam_remote_to_remote_integration.py`

**Step 1: Write integration test**

```python
"""Integration tests for remote-to-remote beam transfers."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from scout_mcp.tools.scout import scout


@pytest.mark.asyncio
async def test_remote_to_remote_full_flow(tmp_path):
    """Test complete remote-to-remote transfer flow."""
    with patch("scout_mcp.tools.scout.get_config") as mock_config, \
         patch("scout_mcp.tools.scout.get_pool") as mock_pool, \
         patch("scout_mcp.services.get_connection_with_retry") as mock_conn, \
         patch("scout_mcp.utils.hostname.get_local_hostname") as mock_hostname:

        # Setup mocks
        config = AsyncMock()
        source_host = AsyncMock(name="remote1")
        target_host = AsyncMock(name="remote2")

        config.get_host.side_effect = lambda name: source_host if name == "remote1" else target_host
        mock_config.return_value = config

        mock_hostname.return_value = "localhost"

        # Mock SSH connections
        source_conn = AsyncMock()
        target_conn = AsyncMock()
        mock_conn.side_effect = [source_conn, target_conn]

        # Mock SFTP
        source_sftp = AsyncMock()
        target_sftp = AsyncMock()

        source_conn.start_sftp_client.return_value.__aenter__.return_value = source_sftp
        target_conn.start_sftp_client.return_value.__aenter__.return_value = target_sftp

        # Execute transfer
        result = await scout(
            beam_source="remote1:/src/file.txt",
            beam_target="remote2:/dst/file.txt",
        )

        # Verify success
        assert "✓" in result or "Transferred" in result

        # Verify SFTP operations were called
        source_sftp.get.assert_called_once()
        target_sftp.put.assert_called_once()


@pytest.mark.asyncio
async def test_optimization_when_server_is_source(tmp_path):
    """Test optimization when MCP server is the source host."""
    with patch("scout_mcp.tools.scout.get_config") as mock_config, \
         patch("scout_mcp.services.get_connection_with_retry") as mock_conn, \
         patch("scout_mcp.utils.hostname.get_local_hostname") as mock_hostname:

        # Setup: MCP server is "tootie"
        config = AsyncMock()
        target_host = AsyncMock(name="remote1")

        config.get_host.return_value = target_host
        mock_config.return_value = config

        mock_hostname.return_value = "tootie"

        # Mock connection (only to target)
        target_conn = AsyncMock()
        mock_conn.return_value = target_conn

        # Mock SFTP
        target_sftp = AsyncMock()
        target_conn.start_sftp_client.return_value.__aenter__.return_value = target_sftp

        # Create local source file
        source_file = tmp_path / "source.txt"
        source_file.write_text("test content")

        # Execute transfer
        with patch("scout_mcp.tools.handlers.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.stat.return_value.st_size = 12

            result = await scout(
                beam_source=f"tootie:{source_file}",
                beam_target="remote1:/dst/file.txt",
            )

        # Should be optimized to direct upload (no download)
        assert "✓" in result or "Uploaded" in result
        target_sftp.put.assert_called_once()
```

**Step 2: Run integration tests**

Run: `uv run pytest tests/test_beam_remote_to_remote_integration.py -v`
Expected: PASS (2 tests)

**Step 3: Commit**

```bash
git add tests/test_beam_remote_to_remote_integration.py
git commit -m "test: add integration tests for remote-to-remote beam

- Test complete transfer flow with mocked connections
- Test optimization when MCP server is source
- Verify SFTP operations are called correctly"
```

---

## Task 7: Manual Testing and Validation

**Manual test checklist:**

1. **Test backward compatibility:**
   ```python
   # Should still work as before
   scout("shart:/tmp/remote.txt", beam="/tmp/local.txt")  # Upload
   scout("squirts:/etc/hostname", beam="/tmp/hostname")   # Download
   ```

2. **Test remote-to-remote:**
   ```python
   # Transfer between two remotes
   scout(beam_source="shart:/tmp/test.txt", beam_target="squirts:/tmp/test.txt")
   ```

3. **Test optimization:**
   - Run MCP server on one of the hosts
   - Verify transfers are optimized to direct SFTP

4. **Test error handling:**
   ```python
   # Invalid parameters
   scout(beam="/local", beam_source="host:/remote")  # Should error
   scout(beam_source="host:/file")  # Missing beam_target, should error
   scout(beam_target="host:/file")  # Missing beam_source, should error
   ```

**No commit for manual testing - verification only.**

---

## Summary

**What was built:**
- Hostname detection utilities for current machine identification
- Transfer path detection with automatic optimization
- Remote-to-remote transfer executor with temp file relay
- Extended scout tool with beam_source/beam_target parameters
- Comprehensive tests and documentation

**Key features:**
- ✓ Backward compatible with existing `beam` parameter
- ✓ Support remote-to-remote transfers via relay
- ✓ Auto-optimize when MCP server is source or target host
- ✓ Clean temp file handling with proper cleanup
- ✓ Comprehensive error handling and validation
- ✓ Full test coverage for all scenarios

**Usage examples:**
```python
# Backward compatible (unchanged)
scout("host:/remote/file", beam="/local/file")

# New remote-to-remote transfer
scout(beam_source="hostA:/src/file", beam_target="hostB:/dst/file")

# Auto-optimized (if running on hostA)
scout(beam_source="hostA:/local/file", beam_target="hostB:/remote/file")
# → Optimized to direct upload from local to hostB
```

# Beam Action Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `beam` action to scout tool for simple file transfers between local and remote hosts

**Architecture:** Extend scout tool with new `beam` parameter that triggers SFTP-based file transfers. Uses asyncssh's native SFTP client for Python-native transfers (more reliable and portable than shelling out to rsync). Supports bidirectional transfers (local→remote, remote→local).

**Tech Stack:** asyncssh (SFTP), asyncio, pytest-asyncio

---

## Task 1: Add beam_transfer executor function

**Files:**
- Modify: `scout_mcp/services/executors.py`
- Test: `tests/test_executors.py`

**Step 1: Write the failing test**

Add to `tests/test_executors.py`:

```python
import tempfile
from pathlib import Path
import pytest
from scout_mcp.services.executors import beam_transfer


@pytest.mark.asyncio
async def test_beam_transfer_local_to_remote(mock_conn):
    """Test transferring file from local to remote."""
    # Create temp local file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("test content\n")
        local_path = f.name

    try:
        remote_path = "/tmp/test_beam_target.txt"

        # Mock SFTP client
        mock_sftp = mock_conn.start_sftp_client.return_value
        mock_sftp.__aenter__.return_value = mock_sftp
        mock_sftp.__aexit__.return_value = None

        result = await beam_transfer(
            mock_conn,
            source=local_path,
            destination=remote_path,
            direction="upload"
        )

        assert result.success is True
        assert "uploaded" in result.message.lower()
        mock_sftp.put.assert_called_once()
    finally:
        Path(local_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_beam_transfer_remote_to_local(mock_conn):
    """Test transferring file from remote to local."""
    with tempfile.TemporaryDirectory() as tmpdir:
        remote_path = "/etc/hostname"
        local_path = f"{tmpdir}/hostname"

        # Mock SFTP client
        mock_sftp = mock_conn.start_sftp_client.return_value
        mock_sftp.__aenter__.return_value = mock_sftp
        mock_sftp.__aexit__.return_value = None

        result = await beam_transfer(
            mock_conn,
            source=remote_path,
            destination=local_path,
            direction="download"
        )

        assert result.success is True
        assert "downloaded" in result.message.lower()
        mock_sftp.get.assert_called_once()


@pytest.mark.asyncio
async def test_beam_transfer_invalid_direction(mock_conn):
    """Test that invalid direction raises error."""
    with pytest.raises(ValueError, match="direction must be"):
        await beam_transfer(
            mock_conn,
            source="/tmp/source",
            destination="/tmp/dest",
            direction="invalid"
        )
```

**Step 2: Run test to verify it fails**

```bash
cd /mnt/cache/code/scout_mcp
uv run pytest tests/test_executors.py::test_beam_transfer_local_to_remote -v
```

Expected: `ImportError: cannot import name 'beam_transfer'` or `NameError`

**Step 3: Write minimal implementation**

Add to `scout_mcp/services/executors.py` (after existing imports):

```python
from pathlib import Path
from dataclasses import dataclass


@dataclass
class TransferResult:
    """Result of a file transfer operation."""
    success: bool
    message: str
    bytes_transferred: int = 0


async def beam_transfer(
    conn: "asyncssh.SSHClientConnection",
    source: str,
    destination: str,
    direction: str,
) -> TransferResult:
    """Transfer file using SFTP (beam action).

    Args:
        conn: SSH connection to remote host
        source: Source path (local or remote depending on direction)
        destination: Destination path (local or remote depending on direction)
        direction: Either "upload" (local→remote) or "download" (remote→local)

    Returns:
        TransferResult with success status and message

    Raises:
        ValueError: If direction is invalid
        RuntimeError: If transfer fails
    """
    if direction not in ("upload", "download"):
        raise ValueError(f"direction must be 'upload' or 'download', got '{direction}'")

    try:
        async with conn.start_sftp_client() as sftp:
            if direction == "upload":
                # Local → Remote
                source_path = Path(source)
                if not source_path.exists():
                    raise RuntimeError(f"Source file not found: {source}")

                file_size = source_path.stat().st_size
                await sftp.put(source, destination)

                return TransferResult(
                    success=True,
                    message=f"Uploaded {source} → {destination}",
                    bytes_transferred=file_size,
                )
            else:
                # Remote → Local
                await sftp.get(source, destination)

                # Get transferred file size
                dest_path = Path(destination)
                file_size = dest_path.stat().st_size if dest_path.exists() else 0

                return TransferResult(
                    success=True,
                    message=f"Downloaded {source} → {destination}",
                    bytes_transferred=file_size,
                )
    except Exception as e:
        return TransferResult(
            success=False,
            message=f"Transfer failed: {e}",
            bytes_transferred=0,
        )
```

**Step 4: Run test to verify it passes**

```bash
cd /mnt/cache/code/scout_mcp
uv run pytest tests/test_executors.py::test_beam_transfer_local_to_remote -v
uv run pytest tests/test_executors.py::test_beam_transfer_remote_to_local -v
uv run pytest tests/test_executors.py::test_beam_transfer_invalid_direction -v
```

Expected: All 3 tests PASS

**Step 5: Run type checking**

```bash
cd /mnt/cache/code/scout_mcp
uv run mypy scout_mcp/services/executors.py
```

Expected: No errors (or acceptable errors for TYPE_CHECKING)

**Step 6: Commit**

```bash
cd /mnt/cache/code/scout_mcp
git add scout_mcp/services/executors.py tests/test_executors.py
git commit -m "feat(executors): add beam_transfer for SFTP file transfers"
```

---

## Task 2: Add beam parameter to scout tool

**Files:**
- Modify: `scout_mcp/tools/scout.py`
- Modify: `scout_mcp/tools/handlers.py` (create new handler)
- Test: `tests/test_scout.py`

**Step 1: Write the failing test**

Add to `tests/test_scout.py`:

```python
import tempfile
from pathlib import Path
import pytest
from scout_mcp.tools.scout import scout


@pytest.mark.asyncio
async def test_scout_beam_upload(monkeypatch, mock_config, mock_pool, mock_conn):
    """Test beam parameter for uploading files."""
    # Setup mocks
    from scout_mcp import services
    monkeypatch.setattr(services, "_config", mock_config)
    monkeypatch.setattr(services, "_pool", mock_pool)

    # Create temp file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("test data\n")
        local_path = f.name

    try:
        # Mock SFTP
        mock_sftp = mock_conn.start_sftp_client.return_value
        mock_sftp.__aenter__.return_value = mock_sftp
        mock_sftp.__aexit__.return_value = None

        result = await scout(
            target="testhost:/tmp/remote.txt",
            beam=local_path
        )

        assert "uploaded" in result.lower() or "success" in result.lower()
        assert "error" not in result.lower()
    finally:
        Path(local_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_scout_beam_download(monkeypatch, mock_config, mock_pool, mock_conn):
    """Test beam parameter for downloading files."""
    # Setup mocks
    from scout_mcp import services
    monkeypatch.setattr(services, "_config", mock_config)
    monkeypatch.setattr(services, "_pool", mock_pool)

    with tempfile.TemporaryDirectory() as tmpdir:
        local_path = f"{tmpdir}/downloaded.txt"

        # Mock SFTP
        mock_sftp = mock_conn.start_sftp_client.return_value
        mock_sftp.__aenter__.return_value = mock_sftp
        mock_sftp.__aexit__.return_value = None

        result = await scout(
            target="testhost:/etc/hostname",
            beam=local_path
        )

        assert "downloaded" in result.lower() or "success" in result.lower()
        assert "error" not in result.lower()


@pytest.mark.asyncio
async def test_scout_beam_requires_valid_target(monkeypatch, mock_config, mock_pool):
    """Test that beam requires a valid target path."""
    from scout_mcp import services
    monkeypatch.setattr(services, "_config", mock_config)
    monkeypatch.setattr(services, "_pool", mock_pool)

    result = await scout(target="hosts", beam="/tmp/file.txt")

    assert "error" in result.lower()
    assert "beam" in result.lower() or "target" in result.lower()
```

**Step 2: Run test to verify it fails**

```bash
cd /mnt/cache/code/scout_mcp
uv run pytest tests/test_scout.py::test_scout_beam_upload -v
```

Expected: `TypeError: scout() got an unexpected keyword argument 'beam'`

**Step 3: Add beam parameter to scout function**

Modify `scout_mcp/tools/scout.py`:

```python
# Update function signature (around line 61)
async def scout(
    target: str = "",
    query: str | None = None,
    tree: bool = False,
    find: str | None = None,
    depth: int = 5,
    diff: str | None = None,
    diff_content: str | None = None,
    targets: list[str] | None = None,
    beam: str | None = None,  # NEW PARAMETER
) -> str:
    """Scout remote files and directories via SSH.

    Args:
        target: Either 'hosts' to list available hosts,
            or 'hostname:/path' to target a path.
        targets: List of targets for multi-host broadcast operations.
            When provided, executes on all hosts concurrently.
        query: Optional shell command to execute
            (e.g., "rg 'pattern'", "find . -name '*.py'").
        tree: If True, show directory tree instead of ls -la.
        find: Glob pattern to search for files (e.g., "*.py", "config*").
        depth: Maximum depth for find operations (default: 5).
        diff: Another target to compare against (e.g., "host2:/path").
        diff_content: Expected content to compare file against.
        beam: Local path for file transfer via SFTP.
              If local file exists → upload to remote target.
              If local file doesn't exist → download from remote target.

    Examples:
        scout("hosts") - List available SSH hosts
        scout("dookie:/var/log/app.log") - Cat a file
        scout("tootie:/etc/nginx") - List directory contents
        scout("tootie:/etc/nginx", tree=True) - Show directory tree
        scout("squirts:~/code", "rg 'TODO' -t py") - Search for pattern
        scout("host:/path", find="*.py") - Find Python files
        scout("host:/path", find="*.log", depth=2) - Find logs with limited depth
        scout("host1:/etc/nginx.conf", diff="host2:/etc/nginx.conf") - Compare files
        scout("host:/etc/hosts", diff_content="expected content") - Compare
        scout(targets=["web1:/var/log/app.log", "web2:/var/log/app.log"]) - Broadcast
        scout(targets=["host1:/etc", "host2:/etc"], query="ls -la") - Broadcast cmd
        scout("shart:/tmp/remote.txt", beam="/tmp/local.txt") - Upload or download

    Returns:
        File contents, directory listing, command output, search results,
        diff output, host list, transfer result, or formatted multi-host results.
    """
```

**Step 4: Add beam handling logic**

Add after line 143 (after `handle_hosts_list` check):

```python
    # Handle beam (file transfer) command
    if beam:
        from scout_mcp.tools.handlers import handle_beam_transfer
        return await handle_beam_transfer(ssh_host, parsed.path, beam)
```

**Step 5: Create beam transfer handler**

Create new file `scout_mcp/tools/handlers.py` or add to existing handlers:

```python
# Add to imports in scout_mcp/tools/handlers.py
from pathlib import Path
from scout_mcp.services.executors import beam_transfer


async def handle_beam_transfer(
    ssh_host: "SSHHost",
    remote_path: str,
    beam_path: str,
) -> str:
    """Handle file transfer (beam) operation.

    Args:
        ssh_host: Target SSH host
        remote_path: Remote file/directory path
        beam_path: Local file/directory path

    Returns:
        Status message describing the transfer result
    """
    from scout_mcp.services import get_connection_with_retry

    # Determine transfer direction
    local_path = Path(beam_path)

    if local_path.exists():
        # Local file exists → Upload (local → remote)
        direction = "upload"
        source = beam_path
        destination = remote_path
    else:
        # Local file doesn't exist → Download (remote → local)
        direction = "download"
        source = remote_path
        destination = beam_path

    try:
        conn = await get_connection_with_retry(ssh_host)
        result = await beam_transfer(conn, source, destination, direction)

        if result.success:
            size_kb = result.bytes_transferred / 1024
            return f"✓ {result.message}\n  Size: {size_kb:.2f} KB"
        else:
            return f"✗ Transfer failed: {result.message}"

    except Exception as e:
        return f"Error: Beam transfer failed: {e}"
```

**Step 6: Run tests to verify they pass**

```bash
cd /mnt/cache/code/scout_mcp
uv run pytest tests/test_scout.py::test_scout_beam_upload -v
uv run pytest tests/test_scout.py::test_scout_beam_download -v
uv run pytest tests/test_scout.py::test_scout_beam_requires_valid_target -v
```

Expected: All 3 tests PASS

**Step 7: Run type checking**

```bash
cd /mnt/cache/code/scout_mcp
uv run mypy scout_mcp/tools/scout.py scout_mcp/tools/handlers.py
```

Expected: No errors

**Step 8: Commit**

```bash
cd /mnt/cache/code/scout_mcp
git add scout_mcp/tools/scout.py scout_mcp/tools/handlers.py tests/test_scout.py
git commit -m "feat(scout): add beam parameter for SFTP file transfers"
```

---

## Task 3: Update service exports

**Files:**
- Modify: `scout_mcp/services/__init__.py`

**Step 1: Add TransferResult export**

Check current exports:

```bash
cat scout_mcp/services/__init__.py
```

Add to exports:

```python
from scout_mcp.services.executors import (
    # ... existing exports ...
    beam_transfer,
)
```

**Step 2: Verify imports work**

```bash
cd /mnt/cache/code/scout_mcp
uv run python -c "from scout_mcp.services import beam_transfer; print('Import successful')"
```

Expected: `Import successful`

**Step 3: Commit**

```bash
cd /mnt/cache/code/scout_mcp
git add scout_mcp/services/__init__.py
git commit -m "feat(services): export beam_transfer function"
```

---

## Task 4: Add integration tests

**Files:**
- Create: `tests/test_beam_integration.py`

**Step 1: Write integration test**

Create `tests/test_beam_integration.py`:

```python
"""Integration tests for beam (file transfer) functionality."""

import tempfile
from pathlib import Path
import pytest
from scout_mcp.tools.scout import scout


@pytest.mark.asyncio
async def test_beam_roundtrip(monkeypatch, mock_config, mock_pool, mock_conn):
    """Test uploading and downloading a file."""
    from scout_mcp import services
    monkeypatch.setattr(services, "_config", mock_config)
    monkeypatch.setattr(services, "_pool", mock_pool)

    # Create temp file with known content
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        original_content = "test beam content\nline 2\n"
        f.write(original_content)
        local_source = f.name

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            remote_path = "/tmp/beam_test_remote.txt"
            local_dest = f"{tmpdir}/downloaded.txt"

            # Mock SFTP for upload
            mock_sftp = mock_conn.start_sftp_client.return_value
            mock_sftp.__aenter__.return_value = mock_sftp
            mock_sftp.__aexit__.return_value = None

            # Upload
            upload_result = await scout(
                target=f"testhost:{remote_path}",
                beam=local_source
            )

            assert "uploaded" in upload_result.lower()
            assert "error" not in upload_result.lower()

            # Download
            download_result = await scout(
                target=f"testhost:{remote_path}",
                beam=local_dest
            )

            assert "downloaded" in download_result.lower()
            assert "error" not in download_result.lower()

        finally:
            Path(local_source).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_beam_with_nonexistent_remote(monkeypatch, mock_config, mock_pool, mock_conn):
    """Test beam handles nonexistent remote files gracefully."""
    from scout_mcp import services
    monkeypatch.setattr(services, "_config", mock_config)
    monkeypatch.setattr(services, "_pool", mock_pool)

    # Mock SFTP to raise error for nonexistent file
    mock_sftp = mock_conn.start_sftp_client.return_value
    mock_sftp.__aenter__.return_value = mock_sftp
    mock_sftp.__aexit__.return_value = None
    mock_sftp.get.side_effect = FileNotFoundError("No such file")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await scout(
            target="testhost:/nonexistent/file.txt",
            beam=f"{tmpdir}/output.txt"
        )

        assert "error" in result.lower() or "failed" in result.lower()
```

**Step 2: Run integration tests**

```bash
cd /mnt/cache/code/scout_mcp
uv run pytest tests/test_beam_integration.py -v
```

Expected: All tests PASS

**Step 3: Commit**

```bash
cd /mnt/cache/code/scout_mcp
git add tests/test_beam_integration.py
git commit -m "test(beam): add integration tests for file transfers"
```

---

## Task 5: Update documentation

**Files:**
- Modify: `scout_mcp/CLAUDE.md`
- Modify: `scout_mcp/README.md`
- Modify: `scout_mcp/tools/CLAUDE.md`

**Step 1: Update tool documentation**

Add to `scout_mcp/tools/CLAUDE.md` in the Commands table:

```markdown
| Input | Behavior |
|-------|----------|
| `scout("hosts")` | List available SSH hosts |
| `scout("host:/path")` | Read file or list directory |
| `scout("host:/path", tree=True)` | Show directory tree |
| `scout("host:/path", "cmd")` | Execute shell command |
| `scout("host:/remote", beam="/local")` | Upload or download file |
```

Add to Examples section:

```python
# Upload file (local → remote)
scout("shart:/mnt/cache/docs/file.txt", beam="/tmp/local.txt")

# Download file (remote → local)
scout("squirts:/etc/hostname", beam="/tmp/hostname")

# Auto-detects direction based on local file existence
```

**Step 2: Update main CLAUDE.md**

Add to `scout_mcp/CLAUDE.md` in Quick Reference:

```bash
# Transfer file to remote
scout("shart:/tmp/remote.txt", beam="/tmp/local.txt")

# Transfer file from remote
scout("squirts:/etc/hostname", beam="/tmp/hostname")
```

**Step 3: Update README.md**

Add beam examples to `scout_mcp/README.md`:

```markdown
## File Transfers

Scout includes `beam` - a simple file transfer feature using SFTP:

```python
# Upload: local file exists → transfer to remote
mcp__scout__scout(
    target="shart:/mnt/cache/docs/report.pdf",
    beam="/tmp/local-report.pdf"
)

# Download: local file doesn't exist → download from remote
mcp__scout__scout(
    target="squirts:/var/log/app.log",
    beam="/tmp/app.log"
)
```

Direction is auto-detected:
- Local file exists → Upload (local → remote)
- Local file doesn't exist → Download (remote → local)
```

**Step 4: Verify documentation builds**

```bash
cd /mnt/cache/code/scout_mcp
# Just verify markdown syntax
head -50 scout_mcp/CLAUDE.md
head -50 README.md
head -50 scout_mcp/tools/CLAUDE.md
```

Expected: No syntax errors, formatting looks correct

**Step 5: Commit**

```bash
cd /mnt/cache/code/scout_mcp
git add scout_mcp/CLAUDE.md README.md scout_mcp/tools/CLAUDE.md
git commit -m "docs: add beam (file transfer) documentation and examples"
```

---

## Task 6: Run full test suite

**Files:**
- None (verification only)

**Step 1: Run all tests**

```bash
cd /mnt/cache/code/scout_mcp
uv run pytest tests/ -v --tb=short
```

Expected: All tests PASS (including existing + new beam tests)

**Step 2: Check test coverage**

```bash
cd /mnt/cache/code/scout_mcp
uv run pytest tests/ --cov=scout_mcp --cov-report=term-missing
```

Expected: Coverage ≥ 80% overall, beam functionality covered

**Step 3: Run type checking on entire codebase**

```bash
cd /mnt/cache/code/scout_mcp
uv run mypy scout_mcp/
```

Expected: No errors (or only acceptable TYPE_CHECKING errors)

**Step 4: Run linter**

```bash
cd /mnt/cache/code/scout_mcp
uv run ruff check scout_mcp/ tests/ --fix
```

Expected: No errors, auto-fixes applied if any

**Step 5: Format code**

```bash
cd /mnt/cache/code/scout_mcp
uv run ruff format scout_mcp/ tests/
```

Expected: Code formatted according to style guidelines

**Step 6: Final commit for cleanup**

```bash
cd /mnt/cache/code/scout_mcp
git add -u
git commit -m "style: format code with ruff" || echo "No formatting changes needed"
```

---

## Task 7: Manual verification

**Files:**
- None (manual testing)

**Step 1: Start scout MCP server**

```bash
cd /mnt/cache/code/scout_mcp
uv run python -m scout_mcp
```

Expected: Server starts on port 8000, no errors

**Step 2: Test upload in separate terminal**

Create test file:
```bash
echo "test upload content" > /tmp/beam_test_upload.txt
```

Test via MCP client or direct tool call:
```python
# In Python REPL or via MCP client
from scout_mcp.tools.scout import scout
import asyncio

result = asyncio.run(scout(
    target="shart:/tmp/beam_uploaded.txt",
    beam="/tmp/beam_test_upload.txt"
))
print(result)
```

Expected: Success message with "uploaded"

**Step 3: Verify uploaded file on remote**

```bash
ssh shart "cat /tmp/beam_uploaded.txt"
```

Expected: "test upload content"

**Step 4: Test download**

```python
result = asyncio.run(scout(
    target="squirts:/etc/hostname",
    beam="/tmp/downloaded_hostname.txt"
))
print(result)
```

Expected: Success message with "downloaded"

**Step 5: Verify downloaded file**

```bash
cat /tmp/downloaded_hostname.txt
```

Expected: Content of remote /etc/hostname

**Step 6: Clean up test files**

```bash
rm /tmp/beam_test_upload.txt /tmp/downloaded_hostname.txt
ssh shart "rm /tmp/beam_uploaded.txt"
```

**Step 7: Document manual test results**

Create note in commit message or plan document confirming manual tests passed.

---

## Task 8: Create final summary commit

**Files:**
- None (meta-commit)

**Step 1: Review all changes**

```bash
cd /mnt/cache/code/scout_mcp
git log --oneline --graph --decorate -10
```

Expected: ~7-8 commits for this feature

**Step 2: Check diff stats**

```bash
git diff main..HEAD --stat
```

Expected:
- scout_mcp/services/executors.py: +60 lines
- scout_mcp/tools/scout.py: +10 lines
- scout_mcp/tools/handlers.py: +40 lines
- tests/: +150 lines
- docs: +30 lines

**Step 3: Create annotated tag**

```bash
git tag -a v0.2.0-beam -m "feat: add beam file transfer capability

- Add beam_transfer executor using asyncssh SFTP
- Add beam parameter to scout tool
- Auto-detect transfer direction (upload/download)
- Include comprehensive tests and documentation
"
```

**Step 4: Push if on feature branch**

```bash
# Only if working in a feature branch
git push origin HEAD
git push origin v0.2.0-beam
```

---

## Completion Checklist

- [ ] Task 1: beam_transfer executor implemented and tested
- [ ] Task 2: beam parameter added to scout tool
- [ ] Task 3: Service exports updated
- [ ] Task 4: Integration tests passing
- [ ] Task 5: Documentation updated
- [ ] Task 6: Full test suite passing with good coverage
- [ ] Task 7: Manual verification successful
- [ ] Task 8: Final commits and tag created

## Technical Notes

### Design Decisions

**Why SFTP?**
- Native to asyncssh (no subprocess overhead)
- More portable (doesn't require external tools on remote)
- Better error handling in Python code
- Simpler for basic file transfers
- Standard protocol supported by all SSH servers

**Why auto-detect transfer direction?**
- Simpler UX: one parameter instead of two
- Intuitive: local file exists = upload, doesn't exist = download
- Reduces cognitive load for users

**Why "beam" name?**
- Short, fun, and memorable
- Conveys the idea of "beaming" files between hosts
- Protocol-agnostic (SFTP now, could support others later)

### Limitations

Current implementation:
- Single file transfers only (no directory recursion)
- No compression option
- No partial transfer resume
- No exclude patterns

Future enhancements could add:
- Directory transfers (recursive)
- Progress callbacks
- Compression toggle
- Include/exclude patterns
- Bandwidth throttling

### Error Handling

The implementation handles:
- Missing source files (local or remote)
- Permission errors
- Network failures (via connection retry)
- Invalid paths

### Performance Considerations

- SFTP transfers entire files (no delta sync like rsync)
- No parallelization for multiple files
- Entire file loaded into memory for small/medium files

For large files (>100MB), future enhancements could add:
- Chunked transfers with progress callbacks
- Streaming to reduce memory usage
- Compression support
- Resume capability for interrupted transfers

## References

- asyncssh SFTP docs: https://asyncssh.readthedocs.io/en/latest/api.html#sftp-client
- Scout MCP architecture: `/mnt/cache/code/scout_mcp/CLAUDE.md`
- Existing executors: `scout_mcp/services/executors.py`
- Test patterns: `tests/test_executors.py`

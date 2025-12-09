# Implementation Plan: Streaming SFTP for Remote-to-Remote Beam Transfer

**Date:** 2025-12-07
**Author:** Claude
**Status:** Ready for Implementation

## Overview

Refactor the `beam_transfer_remote_to_remote()` function in `scout_mcp/services/executors.py` to use SFTP streaming instead of the current inefficient temp file relay approach.

### Current Problem

The existing implementation (lines 987-1063 in `executors.py`):
1. Downloads entire file from source to temp disk on MCP server
2. Uploads entire file from temp disk to target
3. Requires 2x disk I/O and 2x network transfer
4. Temp file cleanup complexity
5. Fails for files larger than available disk space

### Proposed Solution

Stream file data directly between source and target SFTP connections using asyncssh's native file handles:
- Open source file for reading (`sftp.open(path, 'rb')`)
- Open target file for writing (`sftp.open(path, 'wb')`)
- Stream in 64KB chunks
- No temp file, constant memory usage

## Implementation Tasks

### Task 1: Update beam_transfer_remote_to_remote() Function

**File:** `scout_mcp/services/executors.py`
**Location:** Lines 987-1063
**Action:** Replace entire function implementation

**Current Implementation:**
```python
async def beam_transfer_remote_to_remote(
    source_conn: "asyncssh.SSHClientConnection",
    target_conn: "asyncssh.SSHClientConnection",
    source_path: str,
    target_path: str,
) -> TransferResult:
    import tempfile
    temp_file = None

    try:
        # Download from source to temp
        with tempfile.NamedTemporaryFile(delete=False, prefix="scout_beam_") as tf:
            temp_file = Path(tf.name)

        # ... rest of temp file logic ...
```

**New Implementation:**
```python
async def beam_transfer_remote_to_remote(
    source_conn: "asyncssh.SSHClientConnection",
    target_conn: "asyncssh.SSHClientConnection",
    source_path: str,
    target_path: str,
) -> TransferResult:
    """Transfer file between two remote hosts using SFTP streaming.

    Streams file data in chunks without using temp files on the MCP server.
    This approach has constant memory usage and works for files of any size.

    Args:
        source_conn: SSH connection to source host
        target_conn: SSH connection to target host
        source_path: Path to source file on source host
        target_path: Path to destination file on target host

    Returns:
        TransferResult with success status, message, and bytes transferred
    """
    CHUNK_SIZE = 64 * 1024  # 64KB chunks
    bytes_transferred = 0

    try:
        # Open both SFTP clients
        async with source_conn.start_sftp_client() as source_sftp, \
                   target_conn.start_sftp_client() as target_sftp:

            # Verify source file exists
            try:
                source_attrs = await source_sftp.stat(source_path)
                total_size = source_attrs.size
            except Exception as e:
                return TransferResult(
                    success=False,
                    message=f"Source file not found or inaccessible: {e}",
                    bytes_transferred=0,
                )

            # Open source file for reading
            try:
                async with source_sftp.open(source_path, 'rb') as src_file:
                    # Open target file for writing
                    async with target_sftp.open(target_path, 'wb') as dst_file:
                        # Stream in chunks
                        while True:
                            chunk = await src_file.read(CHUNK_SIZE)
                            if not chunk:
                                break
                            await dst_file.write(chunk)
                            bytes_transferred += len(chunk)

                return TransferResult(
                    success=True,
                    message=f"Streamed {source_path} → {target_path} (remote-to-remote)",
                    bytes_transferred=bytes_transferred,
                )

            except Exception as e:
                return TransferResult(
                    success=False,
                    message=f"Transfer failed: {e}",
                    bytes_transferred=bytes_transferred,
                )

    except Exception as e:
        return TransferResult(
            success=False,
            message=f"SFTP connection failed: {e}",
            bytes_transferred=bytes_transferred,
        )
```

**Acceptance Criteria:**
- ✅ No temp file usage (removed `tempfile` import)
- ✅ Uses `sftp.open()` for streaming
- ✅ Tracks bytes transferred during streaming
- ✅ Proper error handling for source file not found
- ✅ Proper error handling for SFTP failures
- ✅ Returns TransferResult with correct message
- ✅ Function signature unchanged (backward compatible)

**Verification:**
```bash
# Run existing tests - they should still pass
cd /mnt/cache/code/scout_mcp
.venv/bin/pytest tests/test_executors.py::test_beam_transfer_remote_to_remote_success -v
.venv/bin/pytest tests/test_executors.py::test_beam_transfer_remote_to_remote_source_not_found -v
.venv/bin/pytest tests/test_executors.py::test_beam_transfer_remote_to_remote_upload_fails -v
```

---

### Task 2: Update Tests for Streaming Behavior

**File:** `tests/test_executors.py`
**Action:** Update mock expectations for streaming implementation

**Current Test Mocks:**
```python
# Tests mock source_sftp.get() and target_sftp.put()
source_sftp.get.assert_called_once()
target_sftp.put.assert_called_once()
```

**New Test Mocks:**
```python
# Tests should mock sftp.open() and file.read()/write()
source_sftp.open.assert_called_once_with(source_path, 'rb')
target_sftp.open.assert_called_once_with(target_path, 'wb')
```

**Test Changes:**

1. **test_beam_transfer_remote_to_remote_success** - Update to mock streaming:
```python
@pytest.mark.asyncio
async def test_beam_transfer_remote_to_remote_success():
    """Test successful remote-to-remote transfer with streaming."""
    from scout_mcp.services.executors import beam_transfer_remote_to_remote

    source_conn = AsyncMock()
    target_conn = AsyncMock()

    # Mock SFTP clients
    source_sftp = AsyncMock()
    target_sftp = AsyncMock()

    source_conn.start_sftp_client.return_value.__aenter__.return_value = source_sftp
    target_conn.start_sftp_client.return_value.__aenter__.return_value = target_sftp

    # Mock file attributes
    mock_attrs = AsyncMock()
    mock_attrs.size = 1024
    source_sftp.stat.return_value = mock_attrs

    # Mock file handles for streaming
    source_file = AsyncMock()
    target_file = AsyncMock()

    # Simulate reading chunks
    chunk_data = b"test data chunk"
    source_file.read.side_effect = [chunk_data, b""]  # First chunk, then EOF

    source_sftp.open.return_value.__aenter__.return_value = source_file
    target_sftp.open.return_value.__aenter__.return_value = target_file

    # Execute transfer
    result = await beam_transfer_remote_to_remote(
        source_conn,
        target_conn,
        "/remote/source.txt",
        "/remote/target.txt",
    )

    # Verify success
    assert result.success is True
    assert "Streamed" in result.message
    assert result.bytes_transferred == len(chunk_data)

    # Verify streaming calls
    source_sftp.stat.assert_called_once_with("/remote/source.txt")
    source_sftp.open.assert_called_once_with("/remote/source.txt", 'rb')
    target_sftp.open.assert_called_once_with("/remote/target.txt", 'wb')

    # Verify data was written
    assert target_file.write.call_count == 1
    target_file.write.assert_called_with(chunk_data)
```

2. **test_beam_transfer_remote_to_remote_source_not_found** - Update for stat() check:
```python
@pytest.mark.asyncio
async def test_beam_transfer_remote_to_remote_source_not_found():
    """Test remote-to-remote transfer with source file not found."""
    from scout_mcp.services.executors import beam_transfer_remote_to_remote

    source_conn = AsyncMock()
    target_conn = AsyncMock()

    source_sftp = AsyncMock()
    target_sftp = AsyncMock()

    source_conn.start_sftp_client.return_value.__aenter__.return_value = source_sftp
    target_conn.start_sftp_client.return_value.__aenter__.return_value = target_sftp

    # Simulate source file not found
    source_sftp.stat.side_effect = Exception("No such file")

    result = await beam_transfer_remote_to_remote(
        source_conn,
        target_conn,
        "/remote/missing.txt",
        "/remote/target.txt",
    )

    assert result.success is False
    assert "Source file not found" in result.message
    assert result.bytes_transferred == 0
```

3. **test_beam_transfer_remote_to_remote_upload_fails** - Update for write() failure:
```python
@pytest.mark.asyncio
async def test_beam_transfer_remote_to_remote_upload_fails():
    """Test remote-to-remote transfer with write failure."""
    from scout_mcp.services.executors import beam_transfer_remote_to_remote

    source_conn = AsyncMock()
    target_conn = AsyncMock()

    source_sftp = AsyncMock()
    target_sftp = AsyncMock()

    source_conn.start_sftp_client.return_value.__aenter__.return_value = source_sftp
    target_conn.start_sftp_client.return_value.__aenter__.return_value = target_sftp

    # Mock file attributes
    mock_attrs = AsyncMock()
    mock_attrs.size = 1024
    source_sftp.stat.return_value = mock_attrs

    # Mock file handles
    source_file = AsyncMock()
    target_file = AsyncMock()

    chunk_data = b"test data"
    source_file.read.side_effect = [chunk_data, b""]

    # Simulate write failure
    target_file.write.side_effect = Exception("Permission denied")

    source_sftp.open.return_value.__aenter__.return_value = source_file
    target_sftp.open.return_value.__aenter__.return_value = target_file

    result = await beam_transfer_remote_to_remote(
        source_conn,
        target_conn,
        "/remote/source.txt",
        "/remote/target.txt",
    )

    assert result.success is False
    assert "Transfer failed" in result.message
```

**Acceptance Criteria:**
- ✅ All 3 existing tests updated to mock streaming behavior
- ✅ Tests verify `sftp.open()` calls instead of `get()`/`put()`
- ✅ Tests verify chunk reading/writing
- ✅ Tests verify bytes_transferred tracking
- ✅ All tests pass with new implementation

**Verification:**
```bash
.venv/bin/pytest tests/test_executors.py -k "remote_to_remote" -v
```

---

### Task 3: Update Integration Tests

**File:** `tests/test_beam_remote_to_remote_integration.py`
**Action:** Update mocks to reflect streaming implementation

**Changes:**

1. **test_remote_to_remote_full_flow** - Update SFTP mock assertions:
```python
@pytest.mark.asyncio
async def test_remote_to_remote_full_flow(tmp_path):
    """Test complete remote-to-remote transfer flow."""
    # ... existing setup ...

    # Mock SFTP file handles for streaming
    source_file = AsyncMock()
    target_file = AsyncMock()

    # Mock file attributes
    mock_attrs = AsyncMock()
    mock_attrs.size = 1024
    source_sftp.stat.return_value = mock_attrs

    # Simulate streaming
    chunk_data = b"test file contents"
    source_file.read.side_effect = [chunk_data, b""]

    source_sftp.open.return_value.__aenter__.return_value = source_file
    target_sftp.open.return_value.__aenter__.return_value = target_file

    # Execute transfer
    result = await scout(
        beam_source="remote1:/src/file.txt",
        beam_target="remote2:/dst/file.txt",
    )

    # Verify success
    assert "✓" in result or "Streamed" in result

    # Verify streaming operations
    source_sftp.stat.assert_called_once()
    source_sftp.open.assert_called_once_with("/src/file.txt", 'rb')
    target_sftp.open.assert_called_once_with("/dst/file.txt", 'wb')
    target_file.write.assert_called_with(chunk_data)
```

2. **test_optimization_when_server_is_source** - No changes needed (uses different code path)

**Acceptance Criteria:**
- ✅ Integration test updated to verify streaming
- ✅ Test verifies stat() call before transfer
- ✅ Test verifies open() calls with correct modes
- ✅ Test verifies write() called with chunk data
- ✅ Test passes with new implementation

**Verification:**
```bash
.venv/bin/pytest tests/test_beam_remote_to_remote_integration.py -v
```

---

### Task 4: Update Documentation

**Files to Update:**
1. `CLAUDE.md` - Main documentation
2. `scout_mcp/tools/CLAUDE.md` - Tool-specific docs

**Changes:**

**CLAUDE.md** (line 59):
```markdown
# Remote-to-Remote Transfers (auto-optimized when MCP server is an endpoint)
scout(beam_source="shart:/src/file.txt", beam_target="squirts:/dst/file.txt")
```

Add new section after line 59:
```markdown

### Transfer Implementation Details

**Remote-to-remote transfers use SFTP streaming:**
- Opens both source and target SFTP connections simultaneously
- Streams file data in 64KB chunks
- No temp files on MCP server (constant memory usage)
- Works for files of any size
- Automatic optimization when MCP server is source or target

**Example:**
```python
# Both hosts are remote - streams between them
scout(beam_source="shart:/data/large.db", beam_target="squirts:/backup/large.db")

# MCP server is on shart - optimized to direct upload
scout(beam_source="shart:/local/file.txt", beam_target="squirts:/remote/file.txt")

# MCP server is on squirts - optimized to direct download
scout(beam_source="shart:/remote/file.txt", beam_target="squirts:/local/file.txt")
```
```

**scout_mcp/tools/CLAUDE.md** (after line 63):
```markdown

### Transfer Methods

**Local ↔ Remote (beam parameter):**
- Uses `sftp.get()` or `sftp.put()` depending on direction
- Automatically detects direction based on local file existence

**Remote ↔ Remote (beam_source/beam_target):**
- Uses SFTP streaming with `sftp.open()` for reading and writing
- Streams in 64KB chunks without temp files
- Constant memory usage regardless of file size
- Optimizes to local → remote or remote → local when MCP server is an endpoint
```

**Acceptance Criteria:**
- ✅ CLAUDE.md updated with streaming implementation details
- ✅ Tool docs updated with transfer method explanations
- ✅ Examples show different optimization scenarios
- ✅ Clear explanation of streaming approach

---

### Task 5: Run Full Test Suite

**Command:**
```bash
cd /mnt/cache/code/scout_mcp
.venv/bin/pytest tests/ -v --tb=short
```

**Acceptance Criteria:**
- ✅ All existing tests pass
- ✅ No regressions in beam transfer functionality
- ✅ Integration tests verify streaming behavior
- ✅ Unit tests verify error handling

---

### Task 6: Commit Changes

**Git Workflow:**

```bash
cd /mnt/cache/code/scout_mcp

# Stage changes
git add scout_mcp/services/executors.py
git add tests/test_executors.py
git add tests/test_beam_remote_to_remote_integration.py
git add CLAUDE.md
git add scout_mcp/tools/CLAUDE.md

# Commit
git commit -m "refactor: use SFTP streaming for remote-to-remote beam transfers

- Replace temp file relay with direct SFTP streaming
- Stream in 64KB chunks for constant memory usage
- Remove tempfile dependency from beam_transfer_remote_to_remote()
- Update tests to verify streaming behavior
- Add transfer implementation docs
- Works for files of any size without disk I/O on MCP server"
```

**Acceptance Criteria:**
- ✅ All changes committed in single atomic commit
- ✅ Commit message follows conventional commits format
- ✅ Commit includes rationale for streaming approach

---

## Benefits of This Approach

### Performance
- **No disk I/O**: Streams data directly from source to target
- **Constant memory**: Uses fixed 64KB chunks regardless of file size
- **Parallel transfer**: Data flows directly between hosts (no relay bottleneck)

### Reliability
- **No temp files**: Eliminates temp file cleanup complexity
- **Works for huge files**: No disk space limitations on MCP server
- **Better error handling**: Clearer error messages for SFTP failures

### Code Quality
- **Simpler implementation**: Fewer lines of code, easier to understand
- **Native asyncssh**: Uses library's intended streaming API
- **Better testing**: Mocks are more accurate to actual SFTP behavior

## Testing Strategy

1. **Unit tests** verify:
   - Successful streaming transfer
   - Source file not found error
   - Write failure handling
   - Bytes transferred tracking

2. **Integration tests** verify:
   - Full flow with mocked SSH connections
   - Optimization when MCP server is source
   - Parameter validation

3. **Manual testing** (optional):
   ```bash
   # Test with real SSH hosts
   scout(beam_source="host1:/tmp/test.txt", beam_target="host2:/tmp/test.txt")
   ```

## Rollback Plan

If issues arise:
1. Revert commit: `git revert HEAD`
2. Original temp file implementation is preserved in git history
3. All tests should still pass with reverted code

## Estimated Effort

- **Task 1**: 15 minutes (function refactor)
- **Task 2**: 20 minutes (unit test updates)
- **Task 3**: 10 minutes (integration test updates)
- **Task 4**: 10 minutes (documentation)
- **Task 5**: 5 minutes (test suite run)
- **Task 6**: 5 minutes (commit)

**Total**: ~65 minutes

## Dependencies

- asyncssh library (already installed)
- Existing test infrastructure
- Git repository

## Success Criteria

✅ All tests pass
✅ No temp files created during remote-to-remote transfers
✅ Streaming approach verified in tests
✅ Documentation updated
✅ Commit message clear and descriptive
✅ Code is simpler and more maintainable than before

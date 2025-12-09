# Scout MCP: New Features Implementation Plan

## Overview

Add three new features to the `scout` tool while maintaining the existing single-tool-with-executors architecture:

1. **File Search** - Find files by pattern across remote hosts
2. **File Diff** - Compare files between hosts
3. **Multi-Host Broadcast** - Execute commands across multiple hosts concurrently

## Current Architecture Summary

```
scout_mcp/
├── tools/scout.py          # Single MCP tool entry point
├── services/executors.py   # SSH command implementations
├── utils/parser.py         # Target URI parsing
└── models/target.py        # ScoutTarget dataclass
```

**Key patterns:**
- `scout()` is the only tool - routes to executors based on parameters
- Executors are pure async functions taking `conn`, `path`, and operation-specific args
- `parse_target()` handles URI parsing, returns `ScoutTarget`
- Error handling: tools return error strings (never raise)
- All output is returned as formatted strings

---

## Feature 1: File Search (`find` parameter)

### API Design

```python
# Find files by pattern
scout("hostname:/path", find="*.py")              # Find Python files
scout("hostname:/path", find="config*", depth=3)  # Limit depth
scout("hostname:/path", find="*.log", type="f")   # Files only
```

### Implementation Tasks

#### Task 1.1: Add `find_files` executor
**File:** `scout_mcp/services/executors.py`

```python
async def find_files(
    conn: "asyncssh.SSHClientConnection",
    path: str,
    pattern: str,
    max_depth: int = 5,
    file_type: str | None = None,  # 'f' for files, 'd' for dirs
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
    """
```

**Shell command:**
```bash
find {path} -maxdepth {max_depth} -name {pattern} [-type {file_type}] 2>/dev/null | head -{max_results}
```

#### Task 1.2: Export `find_files` from services
**File:** `scout_mcp/services/__init__.py`

Add `find_files` to imports and `__all__`.

#### Task 1.3: Update `scout` tool signature
**File:** `scout_mcp/tools/scout.py`

Add parameters:
```python
async def scout(
    target: str,
    query: str | None = None,
    tree: bool = False,
    find: str | None = None,      # NEW: glob pattern
    depth: int = 5,               # NEW: max depth for find
) -> str:
```

#### Task 1.4: Add find routing logic
**File:** `scout_mcp/tools/scout.py`

After connection is established, before query handling:
```python
# If find pattern provided, search for files
if find:
    try:
        results = await find_files(
            conn,
            parsed.path,
            find,
            max_depth=depth,
        )
        if not results.strip():
            return f"No files matching '{find}' found in {parsed.path}"
        return results
    except Exception as e:
        return f"Error: Find failed: {e}"
```

#### Task 1.5: Add tests for `find_files` executor
**File:** `tests/test_executors.py`

```python
@pytest.mark.asyncio
async def test_find_files_returns_matches(mock_connection: AsyncMock) -> None:
    """find_files returns matching file paths."""
    mock_connection.run.return_value = MagicMock(
        stdout="/path/file1.py\n/path/subdir/file2.py", returncode=0
    )

    result = await find_files(mock_connection, "/path", "*.py")

    assert "file1.py" in result
    assert "file2.py" in result

@pytest.mark.asyncio
async def test_find_files_respects_depth(mock_connection: AsyncMock) -> None:
    """find_files limits search depth."""
    mock_connection.run.return_value = MagicMock(stdout="", returncode=0)

    await find_files(mock_connection, "/path", "*.py", max_depth=2)

    call_args = mock_connection.run.call_args[0][0]
    assert "-maxdepth 2" in call_args

@pytest.mark.asyncio
async def test_find_files_empty_results(mock_connection: AsyncMock) -> None:
    """find_files returns empty string when no matches."""
    mock_connection.run.return_value = MagicMock(stdout="", returncode=0)

    result = await find_files(mock_connection, "/path", "*.nonexistent")

    assert result == ""
```

#### Task 1.6: Add integration test for find via scout tool
**File:** `tests/test_integration.py`

Test that `scout("host:/path", find="*.py")` correctly routes to `find_files`.

---

## Feature 2: File Diff (`diff` parameter)

### API Design

```python
# Compare files between hosts
scout("host1:/etc/nginx.conf", diff="host2:/etc/nginx.conf")

# Compare file with inline content
scout("host1:/etc/hosts", diff_content="expected content here")
```

### Implementation Tasks

#### Task 2.1: Add `diff_files` executor
**File:** `scout_mcp/services/executors.py`

```python
async def diff_files(
    conn1: "asyncssh.SSHClientConnection",
    path1: str,
    conn2: "asyncssh.SSHClientConnection",
    path2: str,
    context_lines: int = 3,
) -> tuple[str, bool]:
    """Compare two files from potentially different hosts.

    Args:
        conn1: SSH connection for first file
        path1: Path to first file
        conn2: SSH connection for second file
        path2: Path to second file
        context_lines: Number of context lines in diff output

    Returns:
        Tuple of (diff output, files_are_identical).
        Empty diff output means files are identical.
    """
```

**Implementation approach:**
1. Read both files using `cat_file` executor
2. Use Python's `difflib.unified_diff` for comparison
3. Return formatted diff output

#### Task 2.2: Add `diff_with_content` executor
**File:** `scout_mcp/services/executors.py`

```python
async def diff_with_content(
    conn: "asyncssh.SSHClientConnection",
    path: str,
    expected_content: str,
    context_lines: int = 3,
) -> tuple[str, bool]:
    """Compare remote file with expected content.

    Args:
        conn: SSH connection
        path: Remote file path
        expected_content: Content to compare against
        context_lines: Number of context lines in diff output

    Returns:
        Tuple of (diff output, files_are_identical).
    """
```

#### Task 2.3: Export diff executors from services
**File:** `scout_mcp/services/__init__.py`

Add `diff_files` and `diff_with_content` to imports and `__all__`.

#### Task 2.4: Update `scout` tool signature
**File:** `scout_mcp/tools/scout.py`

Add parameters:
```python
async def scout(
    target: str,
    query: str | None = None,
    tree: bool = False,
    find: str | None = None,
    depth: int = 5,
    diff: str | None = None,           # NEW: "host2:/path" to compare
    diff_content: str | None = None,   # NEW: inline content to compare
) -> str:
```

#### Task 2.5: Add diff routing logic
**File:** `scout_mcp/tools/scout.py`

```python
# If diff target provided, compare files
if diff:
    try:
        # Parse the diff target
        diff_parsed = parse_target(diff)
        if diff_parsed.is_hosts_command:
            return "Error: diff target must be 'host:/path', not 'hosts'"

        # Get connection to second host
        diff_host = config.get_host(diff_parsed.host)
        if diff_host is None:
            return f"Error: Unknown diff host '{diff_parsed.host}'"

        diff_conn = await pool.get_connection(diff_host)

        diff_output, identical = await diff_files(
            conn, parsed.path,
            diff_conn, diff_parsed.path,
        )

        if identical:
            return f"Files are identical:\n  {parsed.host}:{parsed.path}\n  {diff_parsed.host}:{diff_parsed.path}"
        return diff_output

    except Exception as e:
        return f"Error: Diff failed: {e}"

# If diff_content provided, compare with inline content
if diff_content:
    try:
        diff_output, identical = await diff_with_content(
            conn, parsed.path, diff_content
        )

        if identical:
            return f"File matches expected content: {parsed.path}"
        return diff_output

    except Exception as e:
        return f"Error: Diff failed: {e}"
```

#### Task 2.6: Add tests for diff executors
**File:** `tests/test_executors.py`

```python
@pytest.mark.asyncio
async def test_diff_files_identical(mock_connection: AsyncMock) -> None:
    """diff_files returns empty diff for identical files."""
    mock_connection.run.return_value = MagicMock(
        stdout="same content", returncode=0
    )

    diff_output, identical = await diff_files(
        mock_connection, "/path1",
        mock_connection, "/path2",
    )

    assert identical is True
    assert diff_output == ""

@pytest.mark.asyncio
async def test_diff_files_different(mock_connection: AsyncMock) -> None:
    """diff_files returns unified diff for different files."""
    conn1, conn2 = AsyncMock(), AsyncMock()
    conn1.run.return_value = MagicMock(stdout="line1\nline2", returncode=0)
    conn2.run.return_value = MagicMock(stdout="line1\nline3", returncode=0)

    diff_output, identical = await diff_files(
        conn1, "/path1",
        conn2, "/path2",
    )

    assert identical is False
    assert "-line2" in diff_output or "line2" in diff_output
    assert "+line3" in diff_output or "line3" in diff_output

@pytest.mark.asyncio
async def test_diff_with_content_matches(mock_connection: AsyncMock) -> None:
    """diff_with_content detects matching content."""
    mock_connection.run.return_value = MagicMock(
        stdout="expected", returncode=0
    )

    diff_output, identical = await diff_with_content(
        mock_connection, "/path", "expected"
    )

    assert identical is True
```

---

## Feature 3: Multi-Host Broadcast (`targets` parameter)

### API Design

```python
# Execute command across multiple hosts
scout(
    targets=["host1:/etc/hosts", "host2:/etc/hosts", "host3:/etc/hosts"],
    query="cat"
)

# Read same path from multiple hosts
scout(targets=["web1:/var/log/nginx/error.log", "web2:/var/log/nginx/error.log"])
```

### Implementation Tasks

#### Task 3.1: Create new model for multi-target results
**File:** `scout_mcp/models/broadcast.py`

```python
from dataclasses import dataclass


@dataclass
class BroadcastResult:
    """Result from a single host in a broadcast operation."""

    host: str
    path: str
    output: str
    success: bool
    error: str | None = None
```

#### Task 3.2: Export new model
**File:** `scout_mcp/models/__init__.py`

Add `BroadcastResult` to imports and `__all__`.

#### Task 3.3: Add `broadcast_command` executor
**File:** `scout_mcp/services/executors.py`

```python
async def broadcast_read(
    pool: "ConnectionPool",
    config: "ScoutConfig",
    targets: list[tuple[str, str]],  # [(host, path), ...]
    max_file_size: int,
) -> list["BroadcastResult"]:
    """Read files/directories from multiple hosts concurrently.

    Args:
        pool: Connection pool
        config: Scout config for host lookup
        targets: List of (host_name, path) tuples
        max_file_size: Maximum file size to read

    Returns:
        List of BroadcastResult, one per target.
    """
```

**Implementation:**
- Use `asyncio.gather` for concurrent execution
- Each target gets its own connection from pool
- Capture success/failure per host
- Return all results (don't fail fast)

#### Task 3.4: Add `broadcast_command` executor
**File:** `scout_mcp/services/executors.py`

```python
async def broadcast_command(
    pool: "ConnectionPool",
    config: "ScoutConfig",
    targets: list[tuple[str, str]],  # [(host, path), ...]
    command: str,
    timeout: int,
) -> list["BroadcastResult"]:
    """Execute command on multiple hosts concurrently.

    Args:
        pool: Connection pool
        config: Scout config for host lookup
        targets: List of (host_name, path) tuples
        command: Shell command to execute
        timeout: Command timeout in seconds

    Returns:
        List of BroadcastResult, one per target.
    """
```

#### Task 3.5: Export broadcast executors
**File:** `scout_mcp/services/__init__.py`

Add `broadcast_read`, `broadcast_command` to imports and `__all__`.

#### Task 3.6: Update `scout` tool signature
**File:** `scout_mcp/tools/scout.py`

```python
async def scout(
    target: str = "",                    # Now optional when using targets
    targets: list[str] | None = None,    # NEW: ["host1:/path", "host2:/path"]
    query: str | None = None,
    tree: bool = False,
    find: str | None = None,
    depth: int = 5,
    diff: str | None = None,
    diff_content: str | None = None,
) -> str:
```

#### Task 3.7: Add broadcast routing logic
**File:** `scout_mcp/tools/scout.py`

At the top of the function, before single-target handling:

```python
# Handle multi-host broadcast
if targets:
    # Parse all targets
    parsed_targets: list[tuple[str, str]] = []
    for t in targets:
        try:
            p = parse_target(t)
            if p.is_hosts_command:
                return "Error: broadcast targets must be 'host:/path', not 'hosts'"
            parsed_targets.append((p.host, p.path))
        except ValueError as e:
            return f"Error parsing target '{t}': {e}"

    # Execute broadcast
    if query:
        results = await broadcast_command(
            pool, config, parsed_targets, query, config.command_timeout
        )
    else:
        results = await broadcast_read(
            pool, config, parsed_targets, config.max_file_size
        )

    # Format results
    return _format_broadcast_results(results)
```

#### Task 3.8: Add result formatter helper
**File:** `scout_mcp/tools/scout.py`

```python
def _format_broadcast_results(results: list["BroadcastResult"]) -> str:
    """Format broadcast results for display.

    Groups results by success/failure and formats with clear headers.
    """
    lines = []

    for r in results:
        header = f"═══ {r.host}:{r.path} "
        if r.success:
            header += "═" * (60 - len(header))
        else:
            header += f"[FAILED] " + "═" * (50 - len(header))

        lines.append(header)

        if r.success:
            lines.append(r.output)
        else:
            lines.append(f"Error: {r.error}")

        lines.append("")  # Blank line separator

    # Summary
    success_count = sum(1 for r in results if r.success)
    lines.append(f"─── {success_count}/{len(results)} hosts succeeded ───")

    return "\n".join(lines)
```

#### Task 3.9: Add tests for broadcast executors
**File:** `tests/test_executors.py`

```python
@pytest.mark.asyncio
async def test_broadcast_read_multiple_hosts() -> None:
    """broadcast_read fetches from multiple hosts concurrently."""
    # Setup mock pool and config
    mock_pool = AsyncMock()
    mock_config = MagicMock()

    # Mock connections for two hosts
    conn1, conn2 = AsyncMock(), AsyncMock()
    conn1.run.return_value = MagicMock(stdout="content1", returncode=0)
    conn2.run.return_value = MagicMock(stdout="content2", returncode=0)

    mock_pool.get_connection.side_effect = [conn1, conn2]
    mock_config.get_host.return_value = MagicMock()

    results = await broadcast_read(
        mock_pool,
        mock_config,
        [("host1", "/path1"), ("host2", "/path2")],
        max_file_size=1024,
    )

    assert len(results) == 2
    assert results[0].success
    assert results[1].success

@pytest.mark.asyncio
async def test_broadcast_handles_partial_failure() -> None:
    """broadcast_read returns results even when some hosts fail."""
    mock_pool = AsyncMock()
    mock_config = MagicMock()

    # First host succeeds, second fails
    conn1 = AsyncMock()
    conn1.run.return_value = MagicMock(stdout="content", returncode=0)

    mock_pool.get_connection.side_effect = [conn1, Exception("Connection failed")]
    mock_config.get_host.return_value = MagicMock()

    results = await broadcast_read(
        mock_pool,
        mock_config,
        [("host1", "/path1"), ("host2", "/path2")],
        max_file_size=1024,
    )

    assert len(results) == 2
    assert results[0].success
    assert not results[1].success
    assert "Connection failed" in results[1].error
```

---

## Updated Tool Signature Summary

Final `scout` tool signature after all features:

```python
async def scout(
    target: str = "",
    targets: list[str] | None = None,
    query: str | None = None,
    tree: bool = False,
    find: str | None = None,
    depth: int = 5,
    diff: str | None = None,
    diff_content: str | None = None,
) -> str:
    """Scout remote files and directories via SSH.

    Args:
        target: Either 'hosts' to list available hosts,
            or 'hostname:/path' to target a path.
        targets: List of targets for multi-host broadcast operations.
            When provided, executes on all hosts concurrently.
        query: Optional shell command to execute.
        tree: If True, show directory tree instead of ls -la.
        find: Glob pattern to search for files (e.g., "*.py").
        depth: Maximum depth for find operations (default: 5).
        diff: Another target to compare against (e.g., "host2:/path").
        diff_content: Expected content to compare file against.

    Examples:
        # Basic operations
        scout("hosts")                           # List available SSH hosts
        scout("dookie:/var/log/app.log")         # Cat a file
        scout("tootie:/etc/nginx", tree=True)    # Show directory tree
        scout("squirts:~/code", query="rg TODO") # Search for pattern

        # File search
        scout("host:/path", find="*.py")         # Find Python files
        scout("host:/path", find="*.log", depth=2)  # Limited depth

        # File diff
        scout("host1:/etc/nginx.conf", diff="host2:/etc/nginx.conf")

        # Multi-host broadcast
        scout(targets=["web1:/var/log/app.log", "web2:/var/log/app.log"])
        scout(targets=["host1:/etc", "host2:/etc"], query="ls -la")

    Returns:
        File contents, directory listing, command output, search results,
        diff output, or formatted multi-host results.
    """
```

---

## Implementation Order

### Phase 1: File Search (simplest, foundation)
1. Task 1.1: Add `find_files` executor
2. Task 1.2: Export from services
3. Task 1.3: Update scout signature
4. Task 1.4: Add routing logic
5. Task 1.5: Add executor tests
6. Task 1.6: Add integration test

### Phase 2: File Diff (builds on read capability)
1. Task 2.1: Add `diff_files` executor
2. Task 2.2: Add `diff_with_content` executor
3. Task 2.3: Export from services
4. Task 2.4: Update scout signature
5. Task 2.5: Add routing logic
6. Task 2.6: Add executor tests

### Phase 3: Multi-Host Broadcast (most complex)
1. Task 3.1: Create `BroadcastResult` model
2. Task 3.2: Export model
3. Task 3.3: Add `broadcast_read` executor
4. Task 3.4: Add `broadcast_command` executor
5. Task 3.5: Export from services
6. Task 3.6: Update scout signature
7. Task 3.7: Add routing logic
8. Task 3.8: Add result formatter
9. Task 3.9: Add executor tests

---

## Testing Strategy

1. **Unit tests** for each new executor (mock SSH connections)
2. **Integration tests** for routing logic in `scout()` tool
3. **Type checking** with `mypy scout_mcp/`
4. **Linting** with `ruff check scout_mcp/ tests/`

Run full test suite after each phase:
```bash
uv run pytest tests/ -v
uv run mypy scout_mcp/
uv run ruff check scout_mcp/ tests/
```

---

## Files Modified/Created Summary

### Modified Files
- `scout_mcp/services/executors.py` - Add 5 new executors
- `scout_mcp/services/__init__.py` - Export new executors
- `scout_mcp/tools/scout.py` - Add parameters and routing
- `scout_mcp/models/__init__.py` - Export BroadcastResult
- `tests/test_executors.py` - Add executor tests

### New Files
- `scout_mcp/models/broadcast.py` - BroadcastResult dataclass

---

## Risk Mitigation

1. **Concurrent connection limits**: Broadcast operations could open many connections. Mitigate by:
   - Reusing pooled connections where possible
   - Adding optional `max_concurrency` parameter later if needed

2. **Large diff outputs**: File diffs could be huge. Mitigate by:
   - Using `cat_file` with existing `max_file_size` limit
   - Adding optional `diff_lines` parameter to limit output later

3. **Find performance**: Deep searches could be slow. Mitigate by:
   - Default `max_depth=5`
   - Default `max_results=100`
   - Using `2>/dev/null` to suppress permission errors

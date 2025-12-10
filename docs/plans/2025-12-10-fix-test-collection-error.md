# Fix Test Collection Error & Improve Test Infrastructure

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix pytest collection error caused by duplicate test_integration names, then measure and improve test coverage.

**Architecture:** Clean up git state to remove deleted test_integration directory, verify test collection works, measure coverage, and add missing tests.

**Tech Stack:** pytest, pytest-cov, pytest-asyncio

---

## Task 1: Clean Git State and Verify Test Collection

**Files:**
- Clean: Git index (deleted `tests/test_integration/` directory)
- Verify: All test files in `tests/`

### Step 1: Check current git status

Run:
```bash
git status | grep test_integration
```

Expected output:
```
deleted:    tests/test_integration/__init__.py
deleted:    tests/test_integration/test_localhost_resources.py
```

### Step 2: Stage deletion of test_integration directory

Run:
```bash
git rm -r tests/test_integration/
```

Expected: "rm 'tests/test_integration/__init__.py'" and "rm 'tests/test_integration/test_localhost_resources.py'"

### Step 3: Verify pytest can collect tests

Run:
```bash
uv run pytest tests/ --collect-only -q
```

Expected: Should list ~375 tests with NO errors

### Step 4: Run full test suite to verify

Run:
```bash
uv run pytest tests/ -v --tb=short
```

Expected: All tests should run (some may fail, but collection should work)

### Step 5: Commit the fix

Run:
```bash
git add tests/
git commit -m "fix: remove deleted test_integration directory from git index

Fixes pytest collection error caused by duplicate test_integration names:
- File: tests/test_integration.py
- Deleted dir: tests/test_integration/

This was preventing test collection and coverage measurement."
```

Expected: Clean commit with deletion of 2 files

---

## Task 2: Measure Current Test Coverage

**Files:**
- Analyze: All test files in `tests/`
- Generate: Coverage report

### Step 1: Run tests with coverage

Run:
```bash
uv run pytest tests/ -v --cov=scout_mcp --cov-report=term-missing --cov-report=html
```

Expected: Full test run with coverage report showing percentages per file

### Step 2: Analyze coverage report

Run:
```bash
uv run pytest tests/ --cov=scout_mcp --cov-report=term-missing | grep -E "^(scout_mcp|TOTAL)"
```

Expected: Summary of coverage by module, target 85%+ overall

### Step 3: Identify files with low coverage

Run:
```bash
uv run pytest tests/ --cov=scout_mcp --cov-report=term-missing | grep -E "^scout_mcp" | awk '$4 < 85 {print}'
```

Expected: List of files with <85% coverage

### Step 4: Review HTML coverage report

Open:
```bash
# Coverage report is in htmlcov/index.html
ls -lh htmlcov/index.html
```

Expected: HTML file exists, can open in browser to see detailed coverage

### Step 5: Document coverage baseline

Create file: `docs/plans/complete/test-coverage-baseline.md`

```markdown
# Test Coverage Baseline (2025-12-10)

## Overall Coverage

- Total: X%
- Target: 85%+
- Gap: Y%

## Low Coverage Files (<85%)

| File | Coverage | Missing Lines | Priority |
|------|----------|---------------|----------|
| scout_mcp/xxx.py | XX% | Lines X-Y | High/Med/Low |

## Next Steps

1. Add tests for high-priority low-coverage files
2. Focus on critical paths (connection pooling, error handling)
3. Add integration tests for end-to-end flows
```

---

## Task 3: Add Missing Critical Tests

**Files:**
- Based on coverage report from Task 2
- Priority: Connection pool, error handling, security validation

### Step 1: Write test for connection pool eviction

If `scout_mcp/services/pool.py` shows low coverage in LRU eviction:

Create/Modify: `tests/test_services/test_pool.py`

```python
@pytest.mark.asyncio
async def test_connection_pool_lru_eviction() -> None:
    """Pool evicts least recently used connection when full."""
    from scout_mcp.services.pool import ConnectionPool
    from scout_mcp.config import Config

    # Create pool with capacity of 2
    config = Config(max_pool_size=2)
    pool = ConnectionPool(config)

    # Create 3 mock connections
    conn1 = AsyncMock()
    conn2 = AsyncMock()
    conn3 = AsyncMock()

    # Add first two connections
    await pool._cache_connection("host1", conn1)
    await pool._cache_connection("host2", conn2)

    # Access conn1 to make it recently used
    await pool.get_connection("host1")

    # Add third connection, should evict conn2 (least recently used)
    await pool._cache_connection("host3", conn3)

    # Verify conn2 was closed and evicted
    conn2.close.assert_called_once()

    # Verify pool contains conn1 and conn3, not conn2
    assert "host1" in pool._connections
    assert "host3" in pool._connections
    assert "host2" not in pool._connections
```

### Step 2: Run test to verify it fails

Run:
```bash
uv run pytest tests/test_services/test_pool.py::test_connection_pool_lru_eviction -v
```

Expected: FAIL - method not implemented or logic missing

### Step 3: Implement minimal LRU eviction if missing

Only if test fails due to missing implementation:

Modify: `scout_mcp/services/pool.py`

```python
async def _cache_connection(self, host: str, conn: PooledConnection) -> None:
    """Cache connection with LRU eviction."""
    async with self._lock:
        # If at capacity, evict LRU
        if len(self._connections) >= self.config.max_pool_size:
            # Find least recently used
            lru_host = min(
                self._connections.keys(),
                key=lambda h: self._connections[h].last_used
            )
            old_conn = self._connections.pop(lru_host)
            old_conn.connection.close()
            await old_conn.connection.wait_closed()

        # Add new connection
        self._connections[host] = conn
```

### Step 4: Run test to verify it passes

Run:
```bash
uv run pytest tests/test_services/test_pool.py::test_connection_pool_lru_eviction -v
```

Expected: PASS

### Step 5: Commit

```bash
git add tests/test_services/test_pool.py scout_mcp/services/pool.py
git commit -m "test: add LRU eviction test for connection pool"
```

---

## Task 4: Add End-to-End Integration Tests

**Files:**
- Create: `tests/test_e2e/test_full_workflow.py`
- Test: Complete scout tool workflows

### Step 1: Create E2E test directory

Run:
```bash
mkdir -p tests/test_e2e
touch tests/test_e2e/__init__.py
```

### Step 2: Write E2E test for scout tool workflow

Create: `tests/test_e2e/test_full_workflow.py`

```python
"""End-to-end integration tests for Scout MCP workflows."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from scout_mcp.tools import scout
from scout_mcp.services import reset_state, set_config
from scout_mcp.config import Config


@pytest.fixture(autouse=True)
def reset_globals() -> None:
    """Reset global state before each test."""
    reset_state()


@pytest.fixture
def mock_ssh_config(tmp_path: Path) -> Path:
    """Create a temporary SSH config with test hosts."""
    config_file = tmp_path / "ssh_config"
    config_file.write_text("""
Host testhost
    HostName 192.168.1.100
    User testuser
    Port 22

Host remotehost
    HostName 192.168.1.200
    User remoteuser
    Port 22
""")
    return config_file


@pytest.mark.asyncio
async def test_full_scout_workflow_list_hosts_to_read_file(
    mock_ssh_config: Path,
) -> None:
    """Complete workflow: list hosts -> read file from host.

    Tests the full user journey:
    1. User calls scout('hosts') to see available hosts
    2. User calls scout('testhost:/etc/hostname') to read a file
    3. Both operations succeed without errors
    """
    set_config(Config(ssh_config_path=mock_ssh_config))

    # Step 1: List hosts
    hosts_result = await scout("hosts")
    assert "testhost" in hosts_result
    assert "remotehost" in hosts_result

    # Step 2: Mock SSH connection for file read
    mock_conn = AsyncMock()
    mock_conn.run.return_value = AsyncMock(
        stdout="test-hostname\n",
        stderr="",
        exit_status=0
    )

    with patch("scout_mcp.services.pool.asyncssh.connect", return_value=mock_conn):
        # Step 3: Read file from host
        file_result = await scout("testhost:/etc/hostname")
        assert "test-hostname" in file_result

        # Verify connection was made
        mock_conn.run.assert_called()


@pytest.mark.asyncio
async def test_full_scout_workflow_with_command_execution(
    mock_ssh_config: Path,
) -> None:
    """Complete workflow: list hosts -> execute command on host.

    Tests the full user journey:
    1. User calls scout('hosts') to see available hosts
    2. User calls scout('testhost:/var/log', 'grep ERROR') to run command
    3. Command executes and returns results
    """
    set_config(Config(ssh_config_path=mock_ssh_config))

    # Step 1: List hosts
    hosts_result = await scout("hosts")
    assert "testhost" in hosts_result

    # Step 2: Mock SSH connection for command execution
    mock_conn = AsyncMock()
    mock_conn.run.return_value = AsyncMock(
        stdout="ERROR: Connection failed\nERROR: Timeout\n",
        stderr="",
        exit_status=0
    )

    with patch("scout_mcp.services.pool.asyncssh.connect", return_value=mock_conn):
        # Step 3: Execute command
        cmd_result = await scout("testhost:/var/log", "grep ERROR")
        assert "ERROR: Connection failed" in cmd_result
        assert "ERROR: Timeout" in cmd_result


@pytest.mark.asyncio
async def test_error_recovery_workflow(mock_ssh_config: Path) -> None:
    """Workflow handles errors gracefully and recovers.

    Tests error handling:
    1. First request fails with connection error
    2. Second request succeeds (connection retry)
    """
    set_config(Config(ssh_config_path=mock_ssh_config))

    # Step 1: Mock connection failure
    with patch(
        "scout_mcp.services.pool.asyncssh.connect",
        side_effect=ConnectionError("Connection refused")
    ):
        error_result = await scout("testhost:/etc/hostname")
        assert "error" in error_result.lower() or "failed" in error_result.lower()

    # Step 2: Mock successful retry
    mock_conn = AsyncMock()
    mock_conn.run.return_value = AsyncMock(
        stdout="test-hostname\n",
        stderr="",
        exit_status=0
    )

    with patch("scout_mcp.services.pool.asyncssh.connect", return_value=mock_conn):
        success_result = await scout("testhost:/etc/hostname")
        assert "test-hostname" in success_result
```

### Step 3: Run E2E tests to verify they work

Run:
```bash
uv run pytest tests/test_e2e/ -v
```

Expected: All E2E tests pass

### Step 4: Run full test suite with coverage

Run:
```bash
uv run pytest tests/ -v --cov=scout_mcp --cov-report=term-missing
```

Expected: Coverage should improve, all tests pass

### Step 5: Commit E2E tests

```bash
git add tests/test_e2e/
git commit -m "test: add end-to-end integration tests

Adds E2E tests for complete user workflows:
- List hosts -> read file
- List hosts -> execute command
- Error recovery and retry

Improves test coverage for full request flows."
```

---

## Task 5: Verify Final Test Suite Health

**Files:**
- Run: Complete test suite
- Verify: Coverage meets target

### Step 1: Run complete test suite

Run:
```bash
uv run pytest tests/ -v --tb=short
```

Expected: All tests pass with clear output

### Step 2: Measure final coverage

Run:
```bash
uv run pytest tests/ --cov=scout_mcp --cov-report=term-missing --cov-report=html
```

Expected: Coverage ≥85% overall, improvements in critical modules

### Step 3: Generate coverage badge

Run:
```bash
uv run pytest tests/ --cov=scout_mcp --cov-report=term | grep "^TOTAL" | awk '{print $4}'
```

Expected: Percentage displayed (e.g., "87%")

### Step 4: Update README with coverage

Modify: `README.md`

Add badge section:
```markdown
## Test Coverage

![Coverage](https://img.shields.io/badge/coverage-87%25-brightgreen)

- **Total:** 87%
- **Tests:** 400+
- **Last Updated:** 2025-12-10

Run tests: `uv run pytest tests/ -v --cov=scout_mcp`
```

### Step 5: Final commit

```bash
git add README.md docs/plans/complete/test-coverage-baseline.md
git commit -m "docs: update test coverage documentation

- Add coverage badge to README
- Document baseline coverage metrics
- Record test suite improvements

Coverage: 87% (375+ tests -> 400+ tests)"
```

---

## Success Criteria

- ✅ Pytest collects all tests without errors
- ✅ Test suite runs to completion
- ✅ Coverage measured and documented
- ✅ Coverage ≥85% overall
- ✅ E2E integration tests added
- ✅ Critical paths (pool, errors) have comprehensive tests
- ✅ Documentation updated with coverage metrics

---

## Notes

- **Git cleanup is critical:** The duplicate test_integration names must be resolved first
- **Coverage targets:** Focus on critical modules (pool, config, executors) before utilities
- **E2E tests:** These catch integration issues that unit tests miss
- **Property-based testing:** Consider adding hypothesis tests for parsers later (not in this plan)

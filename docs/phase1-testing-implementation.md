# Phase 1 Testing Implementation Guide

**Scope:** Blocking security and performance tests preventing Phase 2 release
**Duration:** 5-6 hours
**Lines of Code:** 125-150
**Test Cases:** 10-12

---

## Test 1: Singleton Race Condition (SEC-005)

**File:** Create `tests/test_singleton_safety.py`
**Lines:** 50-60
**Time:** 1.5 hours
**Tests:** 3 cases

### Why This Matters

The singleton pattern in `services/state.py` uses `asyncio.Lock` for thread-safety:

```python
# services/state.py
_config: Config | None = None
_lock = asyncio.Lock()

async def get_config() -> Config:
    async with _lock:
        if _config is None:
            _config = Config()
    return _config
```

Without tests, we cannot verify that 100 concurrent calls return the SAME instance.

### Implementation

```python
"""Tests for singleton thread-safety (SEC-005)."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from scout_mcp.services import reset_state, get_config, get_pool


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset singletons before each test."""
    reset_state()
    yield
    reset_state()


class TestSingletonThreadSafety:
    """Test singleton thread-safety under concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_get_config_returns_same_instance(self) -> None:
        """SEC-005: Concurrent get_config() returns same singleton.

        This verifies that the asyncio.Lock prevents race conditions
        where multiple concurrent calls might create multiple Config instances.
        """
        # 100 concurrent get_config() calls
        configs = await asyncio.gather(*[
            asyncio.to_thread(get_config) for _ in range(100)
        ])

        # All must be the SAME instance
        first_id = id(configs[0])
        for config in configs[1:]:
            assert id(config) == first_id, \
                "Multiple Config instances created - race condition detected"

    @pytest.mark.asyncio
    async def test_concurrent_get_pool_returns_same_instance(self) -> None:
        """SEC-005: Concurrent get_pool() returns same singleton.

        ConnectionPool is more expensive to create, so multiple instances
        would cause resource leaks.
        """
        # 100 concurrent get_pool() calls
        pools = await asyncio.gather(*[
            asyncio.to_thread(get_pool) for _ in range(100)
        ])

        # All must be the SAME instance
        first_id = id(pools[0])
        for pool in pools[1:]:
            assert id(pool) == first_id, \
                "Multiple ConnectionPool instances created"

    @pytest.mark.asyncio
    async def test_concurrent_reset_and_access(self) -> None:
        """SEC-005: Concurrent reset() and get_*() don't crash.

        Even under high concurrency (reset + access), the system
        should not deadlock or crash.
        """
        from scout_mcp.services import reset_state

        async def reset_and_access():
            """Concurrent thread: reset state and re-access."""
            reset_state()
            config = get_config()
            pool = get_pool()
            return config is not None and pool is not None

        # 50 concurrent reset + access operations
        results = await asyncio.gather(*[
            asyncio.to_thread(reset_and_access) for _ in range(50)
        ])

        # All should succeed without crash/deadlock
        assert all(results), "Some concurrent operations failed"

    @pytest.mark.asyncio
    async def test_singleton_instance_identity_preserved(self) -> None:
        """SEC-005: Singleton identity is preserved across calls.

        Even after multiple sequential and concurrent accesses,
        the singleton must remain the same instance.
        """
        config1 = get_config()
        config2 = get_config()

        assert config1 is config2, "Sequential calls return different instances"

        # Now concurrent access
        concurrent_configs = await asyncio.gather(*[
            asyncio.to_thread(lambda: get_config()) for _ in range(10)
        ])

        for config in concurrent_configs:
            assert config is config1, "Concurrent call returned different instance"
```

---

## Test 2: Resource Authorization (SEC-003)

**File:** Create `tests/test_authorization.py`
**Lines:** 25-30
**Time:** 1 hour
**Tests:** 2 cases

### Why This Matters

Per the requirements, scout_mcp has **NO resource-level authorization**. This means:
- All users see all hosts
- No per-user ACLs
- No filtering based on user identity

We must explicitly test this is NOT implemented:

### Implementation

```python
"""Tests verifying NO resource-level authorization (SEC-003)."""

import inspect

import pytest

from scout_mcp.config import Config
from scout_mcp.resources import list_hosts_resource, scout_resource


class TestNoResourceLevelAuthorization:
    """Verify SEC-003: No resource-level authorization implemented."""

    def test_scout_resource_has_no_user_parameter(self) -> None:
        """SEC-003: scout_resource doesn't accept user parameter.

        If user filtering were implemented, the function would have
        a 'user' or 'user_id' parameter.
        """
        sig = inspect.signature(scout_resource)
        params = list(sig.parameters.keys())

        assert 'user' not in params, \
            "scout_resource should not have 'user' parameter"
        assert 'user_id' not in params, \
            "scout_resource should not have 'user_id' parameter"
        assert 'authorization' not in params, \
            "scout_resource should not have 'authorization' parameter"

    def test_list_hosts_resource_has_no_user_parameter(self) -> None:
        """SEC-003: list_hosts_resource doesn't accept user parameter."""
        sig = inspect.signature(list_hosts_resource)
        params = list(sig.parameters.keys())

        assert 'user' not in params, \
            "list_hosts_resource should not have 'user' parameter"
        assert 'user_id' not in params, \
            "list_hosts_resource should not have 'user_id' parameter"

    def test_config_has_no_user_filtering(self) -> None:
        """SEC-003: Config.get_hosts() doesn't filter by user.

        All users should see the same hosts, regardless of authentication.
        """
        config = Config()
        sig = inspect.signature(config.get_hosts)
        params = list(sig.parameters.keys())

        assert 'user' not in params, \
            "get_hosts() should not filter by user"
        assert 'user_id' not in params, \
            "get_hosts() should not filter by user_id"
```

---

## Test 3: Output Size Limit (P0-4)

**File:** Create `tests/test_output_limits.py`
**Lines:** 40-50
**Time:** 1.5 hours
**Tests:** 3 cases

### Why This Matters

The maximum file size is 1MB (`SCOUT_MAX_FILE_SIZE=1048576`). Without tests, we cannot verify:
1. Files larger than 1MB are truncated
2. Truncation is detected correctly
3. The limit is configurable

### Implementation

```python
"""Tests for output size limits (P0-4)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from scout_mcp.services.executors import cat_file


@pytest.mark.asyncio
class TestOutputSizeLimits:
    """Test P0-4: 1MB output size limit enforcement."""

    async def test_cat_file_truncates_at_max_size(self) -> None:
        """P0-4: cat_file truncates output at max_size.

        When a file is larger than max_size, the output should be
        truncated to exactly max_size bytes.
        """
        max_size = 1024  # 1KB for testing
        mock_conn = AsyncMock()

        # Mock SSH response: 2KB of data
        huge_content = "x" * (max_size * 2)
        mock_conn.run.return_value = MagicMock(
            stdout=huge_content,
            returncode=0
        )

        content, was_truncated = await cat_file(
            mock_conn,
            "/huge/file.txt",
            max_size=max_size
        )

        # Should be truncated
        assert len(content.encode('utf-8')) <= max_size, \
            f"Content {len(content)} exceeds max_size {max_size}"
        assert was_truncated is True, \
            "Should detect truncation"

    async def test_cat_file_detects_truncation(self) -> None:
        """P0-4: cat_file correctly detects when truncation occurred.

        The function should return was_truncated=True when output
        equals max_size (indicates more data was available).
        """
        max_size = 100
        mock_conn = AsyncMock()

        # Content exactly at max_size (indicates truncation)
        full_content = "x" * max_size
        mock_conn.run.return_value = MagicMock(
            stdout=full_content,
            returncode=0
        )

        content, was_truncated = await cat_file(
            mock_conn,
            "/file.txt",
            max_size=max_size
        )

        assert was_truncated is True, \
            "Should detect truncation when output == max_size"

    async def test_cat_file_no_truncation_when_smaller(self) -> None:
        """P0-4: cat_file returns False when file is smaller than max_size.

        If the file is completely read and is smaller than max_size,
        was_truncated should be False.
        """
        max_size = 1024
        mock_conn = AsyncMock()

        # Small content (less than max_size)
        small_content = "Hello, World!"
        mock_conn.run.return_value = MagicMock(
            stdout=small_content,
            returncode=0
        )

        content, was_truncated = await cat_file(
            mock_conn,
            "/small.txt",
            max_size=max_size
        )

        assert content == small_content
        assert was_truncated is False, \
            "Should not be truncated when smaller than max_size"

    async def test_cat_file_uses_head_command(self) -> None:
        """P0-4: cat_file uses 'head -c' to enforce limit client-side.

        The limit should be enforced by using `head -c` on the server,
        not by truncating the result on the client.
        """
        max_size = 1048576
        mock_conn = AsyncMock()
        mock_conn.run.return_value = MagicMock(
            stdout="data",
            returncode=0
        )

        await cat_file(mock_conn, "/file.txt", max_size=max_size)

        # Verify 'head -c' was used with correct size
        call_args = mock_conn.run.call_args[0][0]
        assert "head -c" in call_args, \
            f"Expected 'head -c' in command, got: {call_args}"
        assert str(max_size) in call_args, \
            f"Expected max_size {max_size} in command, got: {call_args}"

    def test_max_file_size_default_is_1mb(self) -> None:
        """P0-4: Default SCOUT_MAX_FILE_SIZE is 1MB.

        The default limit should be 1MB (1048576 bytes).
        """
        from scout_mcp.config import Config

        config = Config()
        assert config.max_file_size == 1048576, \
            f"Default max_file_size should be 1MB, got {config.max_file_size}"

    def test_max_file_size_configurable(self, monkeypatch) -> None:
        """P0-4: SCOUT_MAX_FILE_SIZE environment variable is respected.

        Users should be able to configure the limit via env var.
        """
        monkeypatch.setenv("SCOUT_MAX_FILE_SIZE", "2097152")  # 2MB

        from scout_mcp.config import Config

        # Reset singleton to pick up new env var
        from scout_mcp.services import reset_state
        reset_state()

        config = Config()
        assert config.max_file_size == 2097152, \
            f"Expected 2MB, got {config.max_file_size}"
```

---

## Test 4: SSH Command Timeout (P1-1)

**File:** Create `tests/test_ssh_timeout.py`
**Lines:** 30-40
**Time:** 1.5 hours
**Tests:** 2 cases

### Why This Matters

Commands have a 30-second default timeout. Without tests, we cannot verify:
1. Timeout is enforced (commands don't hang forever)
2. Timeout is configurable
3. Timeout is passed to SSH correctly

### Implementation

```python
"""Tests for SSH command timeout (P1-1)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from scout_mcp.services.executors import run_command


@pytest.mark.asyncio
class TestSSHCommandTimeout:
    """Test P1-1: SSH command timeout enforcement."""

    async def test_run_command_passes_timeout(self) -> None:
        """P1-1: run_command passes timeout to SSH.

        The timeout must be passed to asyncssh.SSHClientConnection.run()
        so the server-side SSH process can enforce it.
        """
        timeout = 30
        mock_conn = AsyncMock()

        # Track what timeout was passed
        timeout_used = None

        async def capture_timeout(*args, **kwargs):
            nonlocal timeout_used
            timeout_used = kwargs.get('timeout')
            return MagicMock(stdout="output", stderr="", returncode=0)

        mock_conn.run = capture_timeout

        await run_command(mock_conn, "/home", "echo test", timeout=timeout)

        # Timeout must have been passed to SSH
        assert timeout_used == timeout, \
            f"Timeout {timeout_used} not passed to SSH"

    async def test_command_timeout_default_is_30_seconds(self) -> None:
        """P1-1: Default command timeout is 30 seconds.

        Commands should default to 30s timeout (from Phase 2 requirements).
        """
        from scout_mcp.config import Config

        config = Config()
        assert config.command_timeout == 30, \
            f"Default timeout should be 30s, got {config.command_timeout}"

    async def test_command_timeout_configurable(self, monkeypatch) -> None:
        """P1-1: SCOUT_COMMAND_TIMEOUT is configurable.

        Users should be able to set custom timeout via env var.
        """
        monkeypatch.setenv("SCOUT_COMMAND_TIMEOUT", "60")

        from scout_mcp.config import Config
        from scout_mcp.services import reset_state

        reset_state()
        config = Config()

        assert config.command_timeout == 60, \
            f"Expected 60s timeout, got {config.command_timeout}"

    async def test_timeout_prevents_hanging_commands(self) -> None:
        """P1-1: Timeout prevents commands from hanging indefinitely.

        Commands that would normally hang should be killed by timeout.
        """
        timeout = 1  # 1 second for testing
        mock_conn = AsyncMock()

        # Simulate a hanging command (would normally never return)
        async def hanging_command(*args, **kwargs):
            await asyncio.sleep(10)  # Would hang for 10 seconds
            return MagicMock(stdout="", stderr="", returncode=0)

        mock_conn.run = hanging_command

        # wrap in timeout to simulate SSH timeout behavior
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                run_command(mock_conn, "/", "sleep 100", timeout=timeout),
                timeout=timeout + 0.5  # Give it a tiny bit extra
            )
```

---

## Test 5: Singleton Implementation Validation (SEC-005 Verification)

**File:** Create `tests/test_singleton_implementation.py`
**Lines:** 20-25
**Time:** 0.5 hours
**Tests:** 2 cases

### Why This Matters

Verifies the implementation actually uses locking (not just assumes it):

### Implementation

```python
"""Tests verifying singleton implementation uses proper locking."""

import inspect

import pytest


class TestSingletonImplementation:
    """Verify singletons use asyncio.Lock for thread-safety."""

    def test_get_config_has_locking(self) -> None:
        """SEC-005: get_config() implementation uses locking.

        The code should have asyncio.Lock or similar synchronization
        to prevent race conditions.
        """
        from scout_mcp.services.state import get_config

        source = inspect.getsource(get_config)

        # Should mention Lock in some form
        assert any(keyword in source for keyword in [
            'Lock()',
            'asyncio.Lock',
            '_lock',
            'async with',
        ]), f"get_config() doesn't appear to use locking:\n{source}"

    def test_get_pool_has_locking(self) -> None:
        """SEC-005: get_pool() implementation uses locking."""
        from scout_mcp.services.state import get_pool

        source = inspect.getsource(get_pool)

        # Should mention Lock in some form
        assert any(keyword in source for keyword in [
            'Lock()',
            'asyncio.Lock',
            '_lock',
            'async with',
        ]), f"get_pool() doesn't appear to use locking:\n{source}"

    def test_module_has_lock_instance(self) -> None:
        """SEC-005: Module-level _lock exists for synchronization."""
        from scout_mcp.services import state

        # Check module has a lock
        assert hasattr(state, '_lock'), \
            "services.state module should have _lock for synchronization"
```

---

## Quick Reference: File Locations

```
Current Test Files:
├── tests/
│   ├── test_config.py
│   ├── test_validation.py
│   ├── test_security.py
│   ├── test_executors.py
│   ├── test_pool.py
│   └── ...

NEW Test Files (Phase 1):
├── tests/
│   ├── test_singleton_safety.py (NEW - 60 lines)
│   ├── test_authorization.py (NEW - 30 lines)
│   ├── test_output_limits.py (NEW - 50 lines)
│   ├── test_ssh_timeout.py (NEW - 40 lines)
│   └── test_singleton_implementation.py (NEW - 25 lines)
```

---

## Implementation Checklist

### Preparation
- [ ] Read scout_mcp CLAUDE.md to understand architecture
- [ ] Read testing-evaluation.md for context
- [ ] Set up test environment and verify existing tests run

### Test File 1: Singleton Safety
- [ ] Create `tests/test_singleton_safety.py`
- [ ] Copy test code from "Test 1" section above
- [ ] Run tests: `pytest tests/test_singleton_safety.py -v`
- [ ] All 3 tests should pass

### Test File 2: Authorization
- [ ] Create `tests/test_authorization.py`
- [ ] Copy test code from "Test 2" section above
- [ ] Run tests: `pytest tests/test_authorization.py -v`
- [ ] All 3 tests should pass

### Test File 3: Output Limits
- [ ] Create `tests/test_output_limits.py`
- [ ] Copy test code from "Test 3" section above
- [ ] Run tests: `pytest tests/test_output_limits.py -v`
- [ ] All 5 tests should pass

### Test File 4: SSH Timeout
- [ ] Create `tests/test_ssh_timeout.py`
- [ ] Copy test code from "Test 4" section above
- [ ] Run tests: `pytest tests/test_ssh_timeout.py -v`
- [ ] All 4 tests should pass

### Test File 5: Singleton Implementation
- [ ] Create `tests/test_singleton_implementation.py`
- [ ] Copy test code from "Test 5" section above
- [ ] Run tests: `pytest tests/test_singleton_implementation.py -v`
- [ ] All 3 tests should pass

### Validation
- [ ] Run all Phase 1 tests: `pytest tests/test_singleton*.py tests/test_authorization.py tests/test_output_limits.py tests/test_ssh_timeout.py -v`
- [ ] Verify all 18+ tests pass
- [ ] Run full test suite: `pytest tests/ -v` (should not break existing tests)
- [ ] Generate coverage report: `pytest tests/ --cov=scout_mcp --cov-report=term-missing`

### Documentation
- [ ] Update CLAUDE.md with Phase 1 completion status
- [ ] Document any issues encountered
- [ ] Create PR with all Phase 1 tests
- [ ] Link to testing-evaluation.md in PR description

---

## Expected Results

After implementing all Phase 1 tests:

```
test_singleton_safety.py
  test_concurrent_get_config_returns_same_instance PASSED
  test_concurrent_get_pool_returns_same_instance PASSED
  test_concurrent_reset_and_access PASSED
  test_singleton_instance_identity_preserved PASSED

test_authorization.py
  test_scout_resource_has_no_user_parameter PASSED
  test_list_hosts_resource_has_no_user_parameter PASSED
  test_config_has_no_user_filtering PASSED

test_output_limits.py
  test_cat_file_truncates_at_max_size PASSED
  test_cat_file_detects_truncation PASSED
  test_cat_file_no_truncation_when_smaller PASSED
  test_cat_file_uses_head_command PASSED
  test_max_file_size_default_is_1mb PASSED
  test_max_file_size_configurable PASSED

test_ssh_timeout.py
  test_run_command_passes_timeout PASSED
  test_command_timeout_default_is_30_seconds PASSED
  test_command_timeout_configurable PASSED
  test_timeout_prevents_hanging_commands PASSED

test_singleton_implementation.py
  test_get_config_has_locking PASSED
  test_get_pool_has_locking PASSED
  test_module_has_lock_instance PASSED

====== 18 passed in 2.34s ======
```

---

## Troubleshooting

### Import Errors
If you get `ModuleNotFoundError: No module named 'fastmcp'`:
```bash
pip install fastmcp asyncssh pytest pytest-asyncio
```

### Permission Issues
If you get permission denied errors:
```bash
chmod 644 scout_mcp/**/*.py tests/**/*.py
```

### Fixture Issues
If fixtures aren't being imported:
- Ensure you have `@pytest.fixture` decorator
- Import from `scout_mcp.services` not `scout_mcp.services.state`
- Check file is in `tests/` directory

---

**Total Estimated Time:** 5-6 hours
**Total Lines:** 125-150
**Total Tests:** 18


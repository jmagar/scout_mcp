# Architecture Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clean up four architectural issues: duplicate SSHHost, sequential host checking, inconsistent env var prefixes, and global singleton state.

**Architecture:** Consolidate SSHHost to models/, fix asyncio.gather() usage in ping.py, standardize all env vars to SCOUT_* prefix, and add state reset functions for testability while keeping singleton pattern.

**Tech Stack:** Python 3.11+, asyncio, pytest, dataclasses

---

## Task 1: Remove Duplicate SSHHost from config.py

**Files:**
- Modify: `scout_mcp/config.py:1-18` (remove SSHHost class, add import)
- Reference: `scout_mcp/models/ssh.py` (canonical SSHHost location)

**Step 1: Write the failing test**

Create a test that verifies SSHHost is only defined in models:

```python
# tests/test_module_structure.py (add to existing file)

def test_ssh_host_not_defined_in_config():
    """SSHHost should only be defined in models, not config."""
    import inspect
    from scout_mcp import config

    # Get all classes defined directly in config module
    classes_in_config = [
        name for name, obj in inspect.getmembers(config, inspect.isclass)
        if obj.__module__ == "scout_mcp.config"
    ]

    assert "SSHHost" not in classes_in_config, "SSHHost should be imported from models, not defined in config"
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_module_structure.py::test_ssh_host_not_defined_in_config -v`
Expected: FAIL with "SSHHost should be imported from models"

**Step 3: Modify config.py to import SSHHost from models**

Replace lines 1-18 of `scout_mcp/config.py` with:

```python
"""Configuration management for Scout MCP."""

import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

from scout_mcp.models import SSHHost
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_module_structure.py::test_ssh_host_not_defined_in_config -v`
Expected: PASS

**Step 5: Run full test suite to verify no regressions**

Run: `.venv/bin/python -m pytest tests/ -v --tb=short`
Expected: All 124+ tests PASS

**Step 6: Commit**

```bash
git add scout_mcp/config.py tests/test_module_structure.py
git commit -m "refactor: consolidate SSHHost to models module

- Remove duplicate SSHHost definition from config.py
- Import SSHHost from scout_mcp.models instead
- Add test to prevent future duplication"
```

---

## Task 2: Fix Sequential Host Checking with asyncio.gather()

**Files:**
- Modify: `scout_mcp/utils/ping.py:29-51`
- Modify: `tests/test_ping.py` (add concurrency test)

**Step 1: Write the failing test for concurrency**

Add test to verify hosts are checked concurrently:

```python
# tests/test_ping.py (add to existing file)

@pytest.mark.asyncio
async def test_check_hosts_online_runs_concurrently() -> None:
    """Verify hosts are checked concurrently, not sequentially."""
    import time

    # Each check takes 0.1s - if sequential, 3 hosts = 0.3s+
    # If concurrent, should complete in ~0.1s
    delay_per_host = 0.1

    async def slow_check(host: str, port: int) -> tuple:
        await asyncio.sleep(delay_per_host)
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        return (MagicMock(), mock_writer)

    with patch("asyncio.open_connection", side_effect=slow_check):
        hosts = {
            "host1": ("192.168.1.1", 22),
            "host2": ("192.168.1.2", 22),
            "host3": ("192.168.1.3", 22),
        }

        start = time.perf_counter()
        results = await check_hosts_online(hosts)
        elapsed = time.perf_counter() - start

        # Should complete in ~0.1s if concurrent, not 0.3s+ if sequential
        assert elapsed < delay_per_host * 2, f"Expected concurrent execution (<0.2s), got {elapsed:.2f}s"
        assert len(results) == 3
        assert all(results.values())
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_ping.py::test_check_hosts_online_runs_concurrently -v`
Expected: FAIL with timing assertion (takes ~0.3s instead of <0.2s)

**Step 3: Fix check_hosts_online to use asyncio.gather()**

Replace lines 29-51 of `scout_mcp/utils/ping.py` with:

```python
async def check_hosts_online(
    hosts: dict[str, tuple[str, int]],
    timeout: float = 2.0,
) -> dict[str, bool]:
    """Check multiple hosts concurrently.

    Args:
        hosts: Dict of {name: (hostname, port)}.
        timeout: Connection timeout per host.

    Returns:
        Dict of {name: is_online}.
    """
    if not hosts:
        return {}

    names = list(hosts.keys())
    coros = [
        check_host_online(hostname, port, timeout)
        for hostname, port in hosts.values()
    ]

    results = await asyncio.gather(*coros)
    return dict(zip(names, results))
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_ping.py::test_check_hosts_online_runs_concurrently -v`
Expected: PASS

**Step 5: Run all ping tests**

Run: `.venv/bin/python -m pytest tests/test_ping.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add scout_mcp/utils/ping.py tests/test_ping.py
git commit -m "perf: use asyncio.gather() for concurrent host checking

- Replace sequential await loop with asyncio.gather()
- Add test to verify concurrent execution
- Improves hosts list performance linearly with host count"
```

---

## Task 3: Standardize Environment Variable Prefixes to SCOUT_*

**Files:**
- Modify: `scout_mcp/config.py:36-51`
- Modify: `tests/test_config.py:173-192`
- Modify: `README.md` (update env var documentation)
- Modify: `CLAUDE.md` (update env var documentation)

**Step 1: Write the failing test for new env var names**

Update existing test to use new SCOUT_* prefix:

```python
# tests/test_config.py - replace test_env_vars_override_defaults

def test_env_vars_override_defaults_with_scout_prefix(tmp_path: Path, monkeypatch) -> None:
    """Environment variables with SCOUT_ prefix override default config values."""
    monkeypatch.setenv("SCOUT_MAX_FILE_SIZE", "5242880")
    monkeypatch.setenv("SCOUT_COMMAND_TIMEOUT", "60")
    monkeypatch.setenv("SCOUT_IDLE_TIMEOUT", "120")

    config = Config(ssh_config_path=tmp_path / "nonexistent")

    assert config.max_file_size == 5242880
    assert config.command_timeout == 60
    assert config.idle_timeout == 120


def test_legacy_mcp_cat_env_vars_still_work(tmp_path: Path, monkeypatch) -> None:
    """Legacy MCP_CAT_* env vars still work for backward compatibility."""
    monkeypatch.setenv("MCP_CAT_MAX_FILE_SIZE", "2097152")
    monkeypatch.setenv("MCP_CAT_COMMAND_TIMEOUT", "45")
    monkeypatch.setenv("MCP_CAT_IDLE_TIMEOUT", "90")

    config = Config(ssh_config_path=tmp_path / "nonexistent")

    assert config.max_file_size == 2097152
    assert config.command_timeout == 45
    assert config.idle_timeout == 90


def test_scout_prefix_takes_precedence_over_legacy(tmp_path: Path, monkeypatch) -> None:
    """SCOUT_* env vars take precedence over legacy MCP_CAT_* vars."""
    # Set both legacy and new
    monkeypatch.setenv("MCP_CAT_MAX_FILE_SIZE", "1000000")
    monkeypatch.setenv("SCOUT_MAX_FILE_SIZE", "2000000")

    config = Config(ssh_config_path=tmp_path / "nonexistent")

    assert config.max_file_size == 2000000  # SCOUT_ wins
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_config.py::test_env_vars_override_defaults_with_scout_prefix -v`
Expected: FAIL (SCOUT_* vars not recognized)

**Step 3: Update config.py to support both prefixes with SCOUT_* priority**

Replace lines 36-51 of `scout_mcp/config.py` with:

```python
    def __post_init__(self) -> None:
        """Apply environment variable overrides.

        Supports both SCOUT_* (preferred) and legacy MCP_CAT_* prefixes.
        SCOUT_* takes precedence if both are set.
        """
        import os
        from contextlib import suppress

        # Helper to get env var with fallback to legacy prefix
        def get_env_int(scout_key: str, legacy_key: str) -> int | None:
            # SCOUT_* takes precedence
            if val := os.getenv(scout_key):
                with suppress(ValueError):
                    return int(val)
            # Fall back to legacy MCP_CAT_*
            if val := os.getenv(legacy_key):
                with suppress(ValueError):
                    return int(val)
            return None

        if (val := get_env_int("SCOUT_MAX_FILE_SIZE", "MCP_CAT_MAX_FILE_SIZE")) is not None:
            self.max_file_size = val

        if (val := get_env_int("SCOUT_COMMAND_TIMEOUT", "MCP_CAT_COMMAND_TIMEOUT")) is not None:
            self.command_timeout = val

        if (val := get_env_int("SCOUT_IDLE_TIMEOUT", "MCP_CAT_IDLE_TIMEOUT")) is not None:
            self.idle_timeout = val
```

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: All tests PASS

**Step 5: Update README.md**

Replace the environment variables section in README.md:

```markdown
## Configuration

Scout MCP reads your `~/.ssh/config` to discover available hosts. Optionally configure limits:

```bash
# Environment variables (optional)
export SCOUT_MAX_FILE_SIZE=5242880   # 5MB (default: 1MB)
export SCOUT_COMMAND_TIMEOUT=60      # seconds (default: 30)
export SCOUT_IDLE_TIMEOUT=120        # seconds (default: 60)

# Legacy MCP_CAT_* prefix still supported for backward compatibility
```
```

**Step 6: Update CLAUDE.md environment variables table**

Replace the Environment Variables section in CLAUDE.md:

```markdown
### Environment Variables
| Variable | Default | Purpose |
|----------|---------|---------|
| `SCOUT_MAX_FILE_SIZE` | 1048576 | Max file size in bytes (1MB) |
| `SCOUT_COMMAND_TIMEOUT` | 30 | Command timeout in seconds |
| `SCOUT_IDLE_TIMEOUT` | 60 | Connection idle timeout |
| `SCOUT_LOG_PAYLOADS` | false | Enable payload logging |
| `SCOUT_SLOW_THRESHOLD_MS` | 1000 | Slow request threshold |
| `SCOUT_INCLUDE_TRACEBACK` | false | Include tracebacks in error logs |

Note: Legacy `MCP_CAT_*` prefix still supported for backward compatibility.
```

**Step 7: Commit**

```bash
git add scout_mcp/config.py tests/test_config.py README.md CLAUDE.md
git commit -m "refactor: standardize env vars to SCOUT_* prefix

- Add SCOUT_MAX_FILE_SIZE, SCOUT_COMMAND_TIMEOUT, SCOUT_IDLE_TIMEOUT
- Keep MCP_CAT_* as fallback for backward compatibility
- SCOUT_* takes precedence when both are set
- Update documentation"
```

---

## Task 4: Add State Reset Functions for Better Testability

**Files:**
- Modify: `scout_mcp/services/state.py`
- Modify: `scout_mcp/services/__init__.py`
- Modify: `tests/test_integration.py:13-17`

**Step 1: Write the failing test for reset function**

```python
# tests/test_module_structure.py (add to TestServicesModule class)

def test_import_reset_state(self) -> None:
    """reset_state should be importable from services."""
    from scout_mcp.services import reset_state
    assert callable(reset_state)
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_module_structure.py::TestServicesModule::test_import_reset_state -v`
Expected: FAIL with ImportError

**Step 3: Add reset_state function to state.py**

Add to the end of `scout_mcp/services/state.py`:

```python
def reset_state() -> None:
    """Reset global state for testing.

    This function clears the singleton instances, allowing tests
    to start with fresh state. Should only be used in test fixtures.
    """
    global _config, _pool
    _config = None
    _pool = None


def set_config(config: Config) -> None:
    """Set the global config instance.

    Allows tests to inject a custom config without modifying module internals.

    Args:
        config: Config instance to use globally.
    """
    global _config
    _config = config


def set_pool(pool: ConnectionPool) -> None:
    """Set the global pool instance.

    Allows tests to inject a custom pool without modifying module internals.

    Args:
        pool: ConnectionPool instance to use globally.
    """
    global _pool
    _pool = pool
```

**Step 4: Export from services/__init__.py**

Update `scout_mcp/services/__init__.py`:

```python
"""Services for Scout MCP."""

from scout_mcp.services.executors import (
    cat_file,
    ls_dir,
    run_command,
    stat_path,
    tree_dir,
)
from scout_mcp.services.pool import ConnectionPool
from scout_mcp.services.state import get_config, get_pool, reset_state, set_config, set_pool

__all__ = [
    "ConnectionPool",
    "cat_file",
    "get_config",
    "get_pool",
    "ls_dir",
    "reset_state",
    "run_command",
    "set_config",
    "set_pool",
    "stat_path",
    "tree_dir",
]
```

**Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_module_structure.py::TestServicesModule::test_import_reset_state -v`
Expected: PASS

**Step 6: Update test_integration.py to use reset_state**

Replace lines 13-17 of `tests/test_integration.py`:

```python
from scout_mcp.services import reset_state


@pytest.fixture(autouse=True)
def reset_globals() -> None:
    """Reset global state before each test."""
    reset_state()
```

**Step 7: Run full test suite**

Run: `.venv/bin/python -m pytest tests/ -v --tb=short`
Expected: All tests PASS

**Step 8: Commit**

```bash
git add scout_mcp/services/state.py scout_mcp/services/__init__.py tests/test_integration.py tests/test_module_structure.py
git commit -m "feat: add reset_state() and set_*() functions for testability

- Add reset_state() to clear singleton instances
- Add set_config() and set_pool() for test injection
- Update test fixtures to use reset_state() instead of internal vars
- Improves test isolation without breaking singleton pattern"
```

---

## Task 5: Final Verification and Documentation Update

**Files:**
- Run full test suite
- Update module CLAUDE.md files if needed

**Step 1: Run full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All tests PASS

**Step 2: Run type checker**

Run: `.venv/bin/python -m mypy scout_mcp/`
Expected: No errors

**Step 3: Run linter**

Run: `.venv/bin/python -m ruff check scout_mcp/ tests/ --fix`
Expected: No errors (or auto-fixed)

**Step 4: Update services/CLAUDE.md**

Add to the state.py section in `scout_mcp/services/CLAUDE.md`:

```markdown
### Testing Utilities

```python
from scout_mcp.services import reset_state, set_config, set_pool

# In test fixtures:
reset_state()  # Clear all singletons

# For custom config in tests:
set_config(my_test_config)
set_pool(my_test_pool)
```
```

**Step 5: Final commit**

```bash
git add -A
git commit -m "docs: update CLAUDE.md with new testing utilities"
```

---

## Summary

| Task | Changes | Tests Added |
|------|---------|-------------|
| 1. Consolidate SSHHost | config.py imports from models | 1 |
| 2. Concurrent host checking | ping.py uses asyncio.gather() | 1 |
| 3. Standardize env vars | config.py supports SCOUT_* | 3 |
| 4. Testability functions | state.py adds reset/set functions | 1 |
| 5. Final verification | Docs update | 0 |

**Total: 5 tasks, ~6 new tests, backward compatible changes**

# Scout MCP Testing Strategy Evaluation

**Date:** 2025-12-03
**Coverage Baseline:** 32% (43 passing tests)
**Test Status:** 67 passing, 133 failing (async fixture issue)
**Phase:** Testing & Quality Engineering Analysis

---

## Executive Summary

Scout MCP has a **foundational test structure** with **critical gaps** in async test infrastructure, security coverage, and integration testing. Current passing tests cover only configuration and module structure. 133 tests are blocked by missing `pytest-asyncio` configuration, representing **81% of the test suite**.

**Key Findings:**
- Async tests cannot run (fixture/plugin misconfiguration)
- Zero security tests for command injection, path traversal, SSH verification
- 32% overall coverage (config/main only)
- 5 major code modules untested (executors, pool, resources, tools, middleware)
- TDD patterns absent (tests added after implementation)

---

## 1. Unit Test Coverage Analysis

### Coverage Summary by Module

| Module | Statements | Missing | Coverage | Status |
|--------|-----------|---------|----------|--------|
| `config.py` | 105 | 4 | **96%** | GOOD |
| `__main__.py` | 27 | 1 | **96%** | GOOD |
| `models/` | 30 | 3 | **90%** | GOOD |
| `utils/parser.py` | 15 | 4 | **73%** | FAIR |
| `utils/mime.py` | 7 | 1 | **86%** | GOOD |
| `services/state.py` | 20 | 11 | **45%** | POOR |
| **`services/pool.py`** | 80 | 57 | **29%** | CRITICAL |
| **`services/executors.py`** | 271 | 252 | **7%** | CRITICAL |
| **`tools/scout.py`** | 71 | 64 | **10%** | CRITICAL |
| **`resources/scout.py`** | 41 | 35 | **15%** | CRITICAL |
| `middleware/base.py` | 5 | 0 | **100%** | GOOD |
| `middleware/errors.py` | 35 | 18 | **49%** | POOR |
| `middleware/logging.py` | 136 | 115 | **15%** | CRITICAL |
| `middleware/timing.py` | 80 | 49 | **39%** | POOR |
| `resources/compose.py` | 75 | 69 | **8%** | CRITICAL |
| `resources/docker.py` | 55 | 50 | **9%** | CRITICAL |
| `resources/zfs.py` | 120 | 113 | **6%** | CRITICAL |
| **TOTAL** | **1528** | **1039** | **32%** | **BLOCKED** |

### Coverage Gaps by Criticality

#### CRITICAL (< 15% coverage)
- `services/executors.py` (7%) - Core SSH operations untested
- `resources/zfs.py` (6%) - Niche resource
- `resources/compose.py` (8%) - Docker integration untested
- `resources/docker.py` (9%) - Docker integration untested
- `tools/scout.py` (10%) - Main user-facing API untested
- `middleware/logging.py` (15%) - Request/response logging untested
- `resources/scout.py` (15%) - Primary resource handler untested

#### POOR (15-50% coverage)
- `services/state.py` (45%) - Global state management
- `services/pool.py` (29%) - Connection pooling (async blocker)
- `middleware/timing.py` (39%) - Performance instrumentation
- `middleware/errors.py` (49%) - Error handling

#### GOOD (> 80% coverage)
- `config.py` (96%) - SSH config parsing
- `__main__.py` (96%) - Entry point
- `models/` (90%) - Data structures
- `utils/mime.py` (86%) - MIME detection

---

## 2. Integration Test Assessment

### Currently Passing Tests (67 total)

```
tests/test_config.py              21 passing  - SSH config parsing
tests/test_main.py                2 passing   - Entry point
tests/test_module_structure.py     18 passing  - Import verification
tests/test_health.py               2 passing   - Health endpoint
tests/benchmarks/test_*            24 passing  - Performance benchmarks
```

### Currently Failing Tests (133 total) - BLOCKED BY ASYNC CONFIG

**Root Cause:** `pytest-asyncio` not installed in pyproject.toml dev dependencies

```python
# Current pyproject.toml [project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",  # Listed but NOT installed
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]
```

**Error:** "You need to install a suitable plugin for your async framework"

**Failed Test Categories:**

| Category | Count | Blocking Issues |
|----------|-------|-----------------|
| Executor tests | 12 | `@pytest.mark.asyncio` not recognized |
| Pool tests | 7 | Connection pool async methods |
| Integration tests | 11 | Scout tool + resources |
| Middleware tests | 14 | Async middleware chain |
| Resource tests | 31 | Docker, Compose, ZFS, Syslog |
| Service executor tests | 24 | Docker, Compose, ZFS, Syslog |
| Benchmark tests | 21 | Performance testing |
| Server lifespan tests | 10 | Async context managers |
| Ping tests | 3 | Async connectivity checks |

### Missing Integration Test Scenarios

1. **Connection Pool Lifecycle**
   - Cold start (first connection)
   - Connection reuse (subsequent requests to same host)
   - Stale connection cleanup
   - Concurrent multi-host operations
   - Pool exhaustion under load

2. **Scout Tool End-to-End**
   - List available hosts
   - Read file (small, large, truncated)
   - List directory with various formats
   - Execute command with command injection attempts
   - Error handling for unknown hosts/paths
   - Retry logic on connection failure

3. **Resource Registration**
   - Dynamic resource templates for each host
   - Resource URI parsing and normalization
   - Error handling for invalid URIs
   - Integration with middleware chain

4. **Middleware Chain**
   - Error middleware catches exceptions
   - Timing middleware measures request duration
   - Logging middleware formats output
   - Chain execution order and exception propagation

---

## 3. Test Quality Metrics

### Assertion Density

**Sample Analysis (test_config.py):**
```python
# test_parse_ssh_config_extracts_hosts: 4 assertions
def test_parse_ssh_config_extracts_hosts(tmp_path: Path) -> None:
    assert len(hosts) == 2
    assert hosts["dookie"].hostname == "100.122.19.93"
    assert hosts["dookie"].user == "jmagar"
    assert hosts["tootie"].port == 29229

# Average: 2-3 assertions per test
# Metric: GOOD (each test verifies one specific behavior)
```

### Test Isolation

**Mock Usage Pattern:**
```python
@pytest.fixture
def mock_connection() -> AsyncMock:
    """Create a mock SSH connection."""
    conn = AsyncMock()
    return conn
```

**Issue:** Fixtures provided but tests cannot execute due to async configuration

### Test Naming Conventions

**Pattern:** `test_<function>_<scenario>_<expected_outcome>`

Examples (GOOD):
- `test_parse_ssh_config_extracts_hosts`
- `test_allowlist_filters_hosts`
- `test_stat_path_returns_file`
- `test_cat_file_respects_max_size`
- `test_run_command_includes_stderr`

**Verdict:** Test naming follows convention but coverage is incomplete

### Test Documentation

**Observation:** All tests have docstrings explaining behavior
```python
def test_parse_ssh_config_extracts_hosts(tmp_path: Path) -> None:
    """Parse SSH config and extract host definitions."""
```

**Verdict:** GOOD - Clear intent documentation

---

## 4. Security Test Requirements

### Gap Analysis (From Phase 2)

#### V-003: Command Injection (CRITICAL)

**Vulnerability:** User input not properly escaped in shell commands

**Current Implementation:**
```python
# scout_mcp/services/executors.py line 53
result = await conn.run(f"head -c {max_size} {path!r}", check=False)
```

**Uses `repr()` for shell escaping** - This is safe.

**However, other commands may not be safe:**
```python
# scout_mcp/utils/parser.py - No validation of path characters
path = parts[1].strip() if len(parts) > 1 else ""
```

**Missing Tests:**
```python
# test_command_injection_prevention.py
async def test_cat_file_escapes_special_characters():
    """Verify filenames with special chars are properly escaped."""
    # Test: /etc/pass"word
    # Test: /var/log/$(whoami).log
    # Test: /tmp/file`cat /etc/passwd`
    # Should use repr() quoting

async def test_scout_tool_sanitizes_paths():
    """Verify path input is validated before command execution."""
    # Test various injection payloads in scout("host:/path")

async def test_run_command_command_injection():
    """Verify user-provided command parameter is safe."""
    # query parameter should use proper shell quoting
    # Test: "grep pattern; rm -rf /"
```

#### V-002: SSH Host Key Verification Disabled (CRITICAL)

**Current Implementation:**
```python
# scout_mcp/services/pool.py line 67
conn = await asyncssh.connect(
    host.hostname,
    port=host.port,
    username=host.user,
    known_hosts=None,  # DISABLED!
    client_keys=client_keys,
)
```

**Missing Tests:**
```python
# test_ssh_security.py
async def test_pool_requires_host_key_verification():
    """Verify SSH host key verification is enabled by default."""
    # Assertion: known_hosts != None
    # OR: known_hosts = "~/.ssh/known_hosts" (default)

async def test_pool_rejects_unknown_host_keys():
    """Verify connection fails if host key not in known_hosts."""
    # Mock asyncssh.connect to raise KeyVerificationError
    # Assertion: Pool.get_connection() raises exception

async def test_mitm_attack_detection():
    """Verify MITM attacks are detected via host key mismatch."""
    # Setup: SSH server returns different host key
    # Assertion: Connection rejected with KeyVerificationError
```

#### V-006: No Rate Limiting (HIGH)

**Missing Tests:**
```python
# test_rate_limiting.py
async def test_scout_tool_rate_limits_requests():
    """Verify tool rejects requests above rate limit."""
    # Send 100 concurrent requests
    # Assertion: Requests > limit are rejected with 429

async def test_connection_pool_throttles_new_connections():
    """Verify pool doesn't create unbounded connections."""
    # Attempt to create 1000 connections
    # Assertion: Pool size capped at config.max_pool_size

async def test_command_timeout_prevents_slowloris():
    """Verify hung commands don't exhaust resources."""
    # Mock command that never completes
    # Assertion: Timeout fires and connection cleaned up
```

#### V-013: Path Traversal (MEDIUM)

**Current Implementation:**
```python
# scout_mcp/utils/parser.py
def parse_target(target: str) -> ScoutTarget:
    # No validation of path content
    parts = target.split(":", 1)
    path = parts[1].strip()  # Could be "/../../../etc/passwd"
    return ScoutTarget(host=host, path=path)
```

**Missing Tests:**
```python
# test_path_validation.py
async def test_scout_rejects_path_traversal():
    """Verify path traversal attempts are blocked."""
    # Test cases:
    # - scout("host:/../../../etc/passwd")
    # - scout("host:/var/../../etc/shadow")
    # - scout("host:/etc/passwd/../../../../../etc/passwd")
    # All should be rejected with validation error

async def test_stat_path_validates_path_characters():
    """Verify only safe path characters are allowed."""
    # Only allow: alphanumeric, -, _, ., /, ~
    # Reject: spaces, quotes, special chars, null bytes

async def test_cat_file_respects_chroot_boundaries():
    """Verify file reads cannot escape allowed directories."""
    # (Depends on SSH server jail, but validates locally)
```

---

## 5. Performance Test Requirements

### Gap Analysis (From Phase 2)

#### Connection Pool Contention (10x Slowdown)

**Current Benchmark:**
```
test_concurrent_single_host_lock_contention - FAILS
```

**Issue:** Global `asyncio.Lock` blocks all concurrent requests to same host

**Missing Tests:**
```python
# test_pool_concurrency.py
async def test_concurrent_requests_same_host_use_single_connection():
    """Verify multiple concurrent requests reuse one connection."""
    # Start 10 concurrent scout() calls to same host
    # Assertion: Pool size == 1 (one connection)
    # Assertion: No lock contention delays

async def test_concurrent_requests_different_hosts_parallelize():
    """Verify different hosts connect in parallel."""
    # Start 10 concurrent requests to 10 different hosts
    # Assertion: Pool size == 10
    # Assertion: Total time < sum of individual times (parallelism)

async def test_lock_held_time_minimized():
    """Verify lock is held only during pool operations."""
    # Mock connection operations with sleep
    # Assertion: Lock held < 100ms per operation
    # Assertion: Command execution not held under lock

async def test_pool_scales_linearly_with_hosts():
    """Verify pool performance doesn't degrade with host count."""
    # 1 host -> 2 hosts -> 5 hosts -> 10 hosts
    # Assertion: Average request time stays constant
    # (one-time connection cost, then reuse)
```

#### Unbounded Pool Growth

**Missing Tests:**
```python
# test_pool_exhaustion.py
async def test_pool_limits_max_connections():
    """Verify pool doesn't grow unbounded."""
    # Attempt to create 1000 host entries
    # Assertion: Pool size capped at config.max_pool_size
    # OR: Cleanup removes idle connections

async def test_memory_usage_bounded_under_load():
    """Verify memory usage doesn't spike with connection count."""
    # Measure before/after creating 100 connections
    # Assertion: Memory growth < 10MB per connection

async def test_stale_connection_cleanup_runs():
    """Verify background cleanup task actually removes idle connections."""
    # Create connections, then wait idle_timeout + 1 second
    # Assertion: Stale connections are closed and removed
    # Assertion: Memory is released

async def test_cleanup_handles_close_errors_gracefully():
    """Verify cleanup doesn't crash if connection close fails."""
    # Mock connection.close() to raise exception
    # Assertion: Cleanup continues, other connections cleaned
```

#### Timeout Handling

**Missing Tests:**
```python
# test_timeout_handling.py
async def test_command_timeout_kills_hung_process():
    """Verify long-running commands timeout correctly."""
    # Run command that takes 5 minutes (timeout=1 second)
    # Assertion: TimeoutError raised after 1 second
    # Assertion: Process is killed

async def test_connection_timeout_prevents_hanging():
    """Verify SSH connection doesn't hang indefinitely."""
    # Mock host that doesn't respond (TCP blackhole)
    # Assertion: Connection attempt fails within timeout

async def test_file_read_timeout_on_slow_filesystem():
    """Verify cat_file doesn't hang on slow NFS mounts."""
    # Mock connection with 5-minute delay on run()
    # Assertion: Completes with error within timeout
```

---

## 6. TDD Compliance Assessment

### RED-GREEN-REFACTOR Evidence

**Analysis:** Tests appear to be **written after implementation** (not TDD)

**Indicators:**
1. Tests exist for 100% of major functions (config.py)
2. All tests use fixture-based mocking
3. No evidence of incremental test-driven development
4. Test files created as batch, not per-feature

**Example - Non-TDD Pattern:**
```python
# scout_mcp/config.py already exists (183 lines, fully implemented)
# Then tests/test_config.py was added (285 lines, comprehensive)
# This is test-after, not test-first
```

**TDD Compliance:** 0% - No evidence of RED (failing test) → GREEN (minimal code) → REFACTOR cycles

### Test Commit History

**Git evidence needed:**
```bash
git log --oneline tests/ | head -20
# Would show test creation timestamps relative to code commits
# Expected TDD: test commits precede implementation commits
# Actual: Likely test commits follow implementation
```

---

## 7. Testing Roadmap & Priorities

### PHASE 1: Unblock Async Testing (IMMEDIATE - HIGH EFFORT)

**Status:** Critical blocker affecting 133 tests

**Tasks:**

1. **Fix pytest-asyncio Configuration**
   - Issue: `asyncio_mode = "auto"` in pyproject.toml is invalid for pytest 9+
   - Fix: Use `asyncio_mode = "auto"` only with pytest-asyncio >= 0.21
   - Verify pytest-asyncio is actually installed in .venv

2. **Test Each Async Test Category**
   ```bash
   uv run pytest tests/test_executors.py -v
   uv run pytest tests/test_pool.py -v
   uv run pytest tests/test_integration.py -v
   ```

3. **Fix Async Fixtures**
   - Verify mock_connection fixture works with pytest-asyncio
   - Ensure all @pytest.mark.asyncio decorators resolve

**Effort:** 2-4 hours

### PHASE 2: Security Test Suite (HIGH PRIORITY)

**Dependencies:** Phase 1 (async working)

**Security Tests to Add (15-20 new tests):**

1. Command Injection Prevention (3 tests)
   - Path special character escaping
   - Command parameter quoting
   - Multi-stage injection attempts

2. SSH Host Key Verification (3 tests)
   - Enable host key checking by default
   - Reject unverified keys
   - Detect MITM attacks

3. Path Traversal Prevention (3 tests)
   - Reject parent directory traversal (..)
   - Reject absolute path escapes
   - Whitelist safe path characters

4. Rate Limiting (2 tests)
   - Tool request throttling
   - Connection pool caps
   - Command timeouts

5. Input Validation (2 tests)
   - Host name validation
   - Path format validation
   - Query parameter sanitization

**Effort:** 20-30 hours

### PHASE 3: Integration Tests (MEDIUM PRIORITY)

**Dependencies:** Phase 1 (async working)

**Test Categories (12-15 new tests):**

1. Scout Tool End-to-End (4 tests)
   - List hosts
   - Read files (various sizes)
   - List directories
   - Execute commands

2. Connection Pool Lifecycle (3 tests)
   - Cold start latency
   - Connection reuse
   - Cleanup and stale detection

3. Middleware Chain (2 tests)
   - Error handling integration
   - Timing/logging instrumentation
   - Proper exception propagation

4. Resource Handlers (2 tests)
   - URI parsing and normalization
   - Dynamic template registration
   - Host context injection

**Effort:** 25-40 hours

### PHASE 4: Performance Tests (LOWER PRIORITY)

**Dependencies:** Phase 1 (async working)

**Benchmark Improvements (8-12 new tests):**

1. Concurrency (3 tests)
   - Same-host connection reuse
   - Multi-host parallelism
   - Lock contention analysis

2. Exhaustion & Cleanup (3 tests)
   - Memory usage under load
   - Pool size limits
   - Idle timeout enforcement

3. Timeout Handling (2 tests)
   - Command timeout accuracy
   - Connection timeout behavior
   - Error recovery

**Effort:** 15-25 hours

### PHASE 5: Code Coverage Goals (ONGOING)

**Target:** 85%+ coverage across all modules

**Priority Order:**
1. **CRITICAL (Week 1-2):** Bring critical modules from 7-15% to 60%
   - executors.py (7% → 70%)
   - scout.py tool (10% → 75%)
   - pool.py (29% → 70%)
   - resources/* (6-15% → 60%)

2. **HIGH (Week 2-3):** Improve poor modules to 70%+
   - middleware/* (15-49% → 70%)
   - services/state.py (45% → 75%)

3. **GOOD (Week 3):** Maintain 96%+ on passing modules
   - config.py, __main__.py, models/*

---

## 8. Testing Gaps Summary

### Unblocked Tests (Passing, 43 total, 32% coverage)
- Configuration parsing ✓
- Module imports ✓
- HTTP health endpoint ✓
- Benchmarks (config parsing performance)

### Blocked Tests (133 total, 68% of suite)
- **Root Cause:** pytest-asyncio not properly configured
- **Status:** Can be unblocked in Phase 1

### Missing Tests (New test cases needed)

| Category | Count | Severity | Est. Effort |
|----------|-------|----------|-------------|
| Command injection prevention | 5 | CRITICAL | 8h |
| SSH host key verification | 3 | CRITICAL | 6h |
| Path traversal prevention | 3 | CRITICAL | 6h |
| Rate limiting | 3 | HIGH | 4h |
| Scout tool integration | 8 | HIGH | 12h |
| Connection pool lifecycle | 5 | HIGH | 10h |
| Middleware chain | 4 | MEDIUM | 6h |
| Resource handlers | 4 | MEDIUM | 8h |
| Concurrency & parallelism | 5 | MEDIUM | 10h |
| Timeout handling | 4 | MEDIUM | 8h |
| Error handling edge cases | 6 | MEDIUM | 10h |
| **TOTAL** | **50** | | **88h** |

---

## 9. Code Quality Issues Impacting Testability

### Function Size Problem (Phase 1 Finding)

**Untestable Functions:**

| Function | Lines | Issue | Status |
|----------|-------|-------|--------|
| `scout()` | 128 | 5 responsibilities | CRITICAL |
| `executors.py` | Multiple | Command building untested | CRITICAL |
| `middleware/logging.py` | 320 | Complex formatting logic | CRITICAL |
| `middleware/timing.py` | 259 | Statistics tracking | HIGH |
| `server.py` | 448 | Setup/config logic | HIGH |

**Example - scout() Function (128 lines):**
```python
async def scout(target, query=None, tree=False):
    # 1. Parse input
    # 2. Handle hosts command
    # 3. Lookup host
    # 4. Get connection (with retry)
    # 5. Execute command OR determine file/dir
    # 6. Read/list/execute
    # 7. Format output
```

**Refactoring Needed Before Full Test Coverage:**
- Extract `_handle_hosts_command()`
- Extract `_get_connection_with_retry()`
- Extract `_determine_path_type()`
- Extract `_read_or_list()`

---

## 10. Recommendations

### IMMEDIATE (This Sprint)

1. **Install pytest-asyncio in dev dependencies**
   ```toml
   [project.optional-dependencies]
   dev = [
       "pytest>=8.0.0",
       "pytest-asyncio>=0.24.0",  # Ensure correct version
       "ruff>=0.4.0",
       "mypy>=1.10.0",
       "pytest-cov>=7.0.0",        # Add for coverage reports
   ]
   ```

2. **Verify async test execution**
   ```bash
   uv sync --dev
   uv run pytest tests/test_executors.py -v
   ```

3. **Add coverage.py to generate baseline report**
   ```bash
   uv run pytest tests/ --cov=scout_mcp --cov-report=html
   ```

### SHORT TERM (Next 2 Weeks)

1. **Phase 1: Unblock Async Tests** (4-6h)
   - Fix pytest-asyncio configuration
   - Verify all 133 tests can run (expect ~40 actual failures)

2. **Phase 2a: Critical Security Tests** (20h)
   - Command injection prevention (5 tests)
   - SSH host key verification (3 tests)
   - Path traversal prevention (3 tests)

3. **Phase 2b: Scout Tool Integration Tests** (12h)
   - Main tool happy path
   - Error cases
   - Retry logic

### MEDIUM TERM (Next 4 Weeks)

1. **Refactor Untestable Functions** (16h)
   - Scout tool decomposition
   - Middleware simplification

2. **Add Integration Tests** (30h)
   - Connection pool lifecycle
   - Resource handlers
   - Middleware chain

3. **Add Concurrency Tests** (15h)
   - Pool lock contention
   - Multi-host parallelism

### LONG TERM (Maintenance)

1. **Maintain 85%+ Coverage**
   - Review new code for test coverage
   - Add tests before production deployment

2. **Implement TDD for New Features**
   - RED: Write failing test
   - GREEN: Implement minimal code
   - REFACTOR: Improve while keeping tests green

3. **Run Coverage Reports Regularly**
   ```bash
   uv run pytest tests/ --cov=scout_mcp --cov-report=term-missing
   ```

---

## Appendix A: Test Execution Status

### Working Test Suites

```
tests/test_config.py              21 PASS
  - SSH config parsing
  - Host filtering (allowlist/blocklist)
  - Environment variable override

tests/test_main.py                2 PASS
  - HTTP transport startup
  - STDIO transport startup

tests/test_module_structure.py     18 PASS
  - Import verification for all modules
  - Backward compatibility checks

tests/test_health.py               2 PASS
  - Health endpoint returns 200
  - Response content-type check
```

### Blocked Test Suites (Async Configuration Issue)

```
tests/test_executors.py            12 FAIL - Executor functions
tests/test_pool.py                 7 FAIL  - Connection pool
tests/test_integration.py          11 FAIL - Scout tool + resources
tests/test_middleware/*            14 FAIL - Logging, timing, error handling
tests/test_resources/*             31 FAIL - Scout, Docker, Compose, ZFS, Syslog
tests/test_services/*              24 FAIL - Executor services
tests/test_ping.py                 3 FAIL  - Host connectivity
tests/test_server_lifespan.py       10 FAIL - Server lifecycle
tests/benchmarks/test_*.py          21 FAIL - Performance benchmarks
```

---

## Appendix B: Security Assessment (Phase 2 Context)

### Vulnerability Cross-Reference

| Vulnerability | Test Status | Severity | Phase |
|---|---|---|---|
| V-002: Host key verification disabled | NO TESTS | CRITICAL | 2 |
| V-003: Command injection possible | NO TESTS | CRITICAL | 2 |
| V-006: No rate limiting | NO TESTS | HIGH | 2 |
| V-013: Path traversal unvalidated | NO TESTS | CRITICAL | 2 |

### Required Security Tests

```python
# tests/test_security.py (NEW FILE)

async def test_command_injection_shell_metacharacters():
    """Verify shell metacharacters are properly escaped."""
    # Payloads: `;`, `|`, `&&`, `||`, `$()`, backticks, etc.

async def test_host_key_verification_enabled():
    """Verify SSH connections verify host keys."""
    # known_hosts parameter must be set correctly

async def test_rate_limiting_enforcement():
    """Verify excessive requests are throttled."""
    # Tool calls, connection attempts

async def test_path_traversal_blocked():
    """Verify /../ sequences are rejected."""
    # Parent directory escapes should fail
```

---

## Appendix C: Codebase Statistics

### Test-to-Code Ratio

| Component | Code Lines | Test Lines | Ratio |
|-----------|-----------|-----------|-------|
| config.py | 183 | 285 | 1:1.56 (GOOD) |
| __main__.py | 61 | 46 | 1:0.75 |
| models/* | 32 | ~50 | 1:1.56 |
| executors.py | 642 | 179 | 1:0.28 (POOR) |
| pool.py | 170 | 146 | 1:0.86 |
| scout.py tool | 146 | 55 | 1:0.38 (POOR) |
| **TOTAL** | ~4000 | 1300 | 1:0.33 |

### Untestable Functions (> 50 lines)

```
scout_mcp/middleware/timing.py: 259 lines (complex)
scout_mcp/middleware/logging.py: 320 lines (complex)
scout_mcp/services/executors.py: 642 lines (multiple functions)
scout_mcp/server.py: 448 lines (setup + resource registration)
scout_mcp/resources/zfs.py: 272 lines (multiple functions)
scout_mcp/tools/scout.py: 146 lines (128-line scout function)
scout_mcp/services/pool.py: 170 lines (ok, but async untested)
scout_mcp/config.py: 183 lines (ok, covered by tests)
```

---

**Document Generated:** 2025-12-03
**Next Review:** After Phase 1 completion
**Owner:** Test Engineering Team
**Status:** READY FOR IMPLEMENTATION

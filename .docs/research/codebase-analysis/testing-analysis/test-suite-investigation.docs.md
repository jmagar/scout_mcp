# Scout MCP Test Suite Investigation

## Summary

Scout MCP has a comprehensive test suite with 121+ tests across 31 test files, achieving ~81% code coverage. The test organization is excellent, with clear separation between unit, integration, and performance tests. Tests use modern async patterns (pytest-asyncio auto mode), extensive mocking (AsyncMock for SSH), and follow consistent fixture patterns. Key strengths: middleware testing, dynamic resource testing, and performance benchmarking suite. Coverage gaps exist primarily in error handling edge cases and some resource implementations.

## Key Test Files by Category

### Core Functionality Tests
- `/mnt/cache/code/scout_mcp/tests/test_config.py` - SSH config parsing, environment variables, transport configuration (21 tests)
- `/mnt/cache/code/scout_mcp/tests/test_pool.py` - Connection pool lifecycle, reuse, idle timeout (9 tests)
- `/mnt/cache/code/scout_mcp/tests/test_executors.py` - SSH command execution (cat, ls, stat, run_command, tree) (12 tests)
- `/mnt/cache/code/scout_mcp/tests/test_scout.py` - URI parsing and target validation (7 tests)

### Integration Tests
- `/mnt/cache/code/scout_mcp/tests/test_integration.py` - End-to-end tool/resource flows with mocked SSH (14 tests)
- `/mnt/cache/code/scout_mcp/tests/test_server_lifespan.py` - Dynamic resource registration, lifespan hooks (9 tests)
- `/mnt/cache/code/scout_mcp/tests/test_main.py` - Entry point for HTTP/STDIO transport modes (2 tests)

### Middleware Tests
- `/mnt/cache/code/scout_mcp/tests/test_middleware/test_base.py` - Middleware base class (2 tests)
- `/mnt/cache/code/scout_mcp/tests/test_middleware/test_errors.py` - Error handling, stats tracking, callbacks (7 tests)
- `/mnt/cache/code/scout_mcp/tests/test_middleware/test_logging.py` - Request/response logging, payload truncation (18 tests)
- `/mnt/cache/code/scout_mcp/tests/test_middleware/test_timing.py` - Duration tracking, slow request warnings (7 tests)
- `/mnt/cache/code/scout_mcp/tests/test_middleware/test_integration.py` - Middleware stack configuration (3 tests)

### Resource-Specific Tests
- `/mnt/cache/code/scout_mcp/tests/test_resources/test_hosts.py` - Host listing with dynamic schemes (2 tests)
- `/mnt/cache/code/scout_mcp/tests/test_resources/test_docker.py` - Docker container logs and listing (6 tests)
- `/mnt/cache/code/scout_mcp/tests/test_resources/test_compose.py` - Docker Compose operations
- `/mnt/cache/code/scout_mcp/tests/test_resources/test_syslog.py` - System log reading (2 tests)
- `/mnt/cache/code/scout_mcp/tests/test_resources/test_zfs.py` - ZFS pool/dataset management

### Service Executor Tests
- `/mnt/cache/code/scout_mcp/tests/test_services/test_docker_executors.py` - Docker CLI wrappers (7 tests)
- `/mnt/cache/code/scout_mcp/tests/test_services/test_compose_executors.py` - Compose CLI wrappers (6 tests)
- `/mnt/cache/code/scout_mcp/tests/test_services/test_zfs_executors.py` - ZFS CLI wrappers (6 tests)
- `/mnt/cache/code/scout_mcp/tests/test_services/test_syslog_executors.py` - Syslog reading (3 tests)

### Infrastructure Tests
- `/mnt/cache/code/scout_mcp/tests/test_health.py` - HTTP health endpoint (2 tests)
- `/mnt/cache/code/scout_mcp/tests/test_ping.py` - Host connectivity checking with concurrency (4 tests)
- `/mnt/cache/code/scout_mcp/tests/test_module_structure.py` - Import structure, backward compatibility (17 tests)

### Performance Benchmarks
- `/mnt/cache/code/scout_mcp/tests/benchmarks/test_connection_pool.py` - Pool performance metrics
- `/mnt/cache/code/scout_mcp/tests/benchmarks/test_ssh_operations.py` - SSH command latency
- `/mnt/cache/code/scout_mcp/tests/benchmarks/test_config_parsing.py` - Config parsing speed
- `/mnt/cache/code/scout_mcp/tests/benchmarks/test_uri_parsing.py` - URI parsing overhead
- `/mnt/cache/code/scout_mcp/tests/benchmarks/test_end_to_end.py` - Full request flow
- `/mnt/cache/code/scout_mcp/tests/benchmarks/profile_cpu.py` - CPU profiling script
- `/mnt/cache/code/scout_mcp/tests/benchmarks/profile_memory.py` - Memory profiling script

## Test Organization Patterns

### 1. File Structure
```
tests/
├── test_*.py              # Core unit tests (11 files)
├── test_middleware/       # Middleware layer tests (5 files)
├── test_resources/        # Resource handler tests (5 files)
├── test_services/         # Service executor tests (4 files)
└── benchmarks/            # Performance tests (7 files)
```

**Pattern**: Tests mirror source code structure (`scout_mcp/middleware/` → `tests/test_middleware/`)

### 2. Fixture Patterns

**Common Fixtures**:
```python
@pytest.fixture
def mock_ssh_host() -> SSHHost:
    """Create a mock SSH host."""
    return SSHHost(name="testhost", hostname="192.168.1.100", user="testuser", port=22)

@pytest.fixture
def mock_ssh_config(tmp_path: Path) -> Path:
    """Create a temporary SSH config."""
    config_file = tmp_path / "ssh_config"
    config_file.write_text("""Host testhost\n    HostName 192.168.1.100""")
    return config_file

@pytest.fixture(autouse=True)
def reset_globals() -> None:
    """Reset global state before each test."""
    reset_state()
```

**Patterns Observed**:
- Extensive use of `tmp_path` for file-based testing
- `autouse=True` fixtures for state management
- Mock objects created per-test (no shared state)
- Fixtures return concrete objects, not mocks (better type safety)

### 3. Mocking Strategies

**SSH Connection Mocking**:
```python
mock_conn = AsyncMock()
mock_conn.is_closed = False
mock_conn.run.return_value = MagicMock(stdout="output", returncode=0)

with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
    mock_connect.return_value = mock_conn
    # ... test code
```

**Key Patterns**:
- `AsyncMock` for async SSH operations (not regular `Mock`)
- `MagicMock` for synchronous return values
- `patch` used at module import level (`"asyncssh.connect"`)
- `side_effect` for sequences: `[result1, result2]` or exceptions
- Connection state tracked via `is_closed` attribute

**Pool Mocking**:
```python
mock_pool = AsyncMock()
mock_pool.get_connection = AsyncMock(return_value=mock_conn)
mock_pool.remove_connection = AsyncMock()

with patch("scout_mcp.resources.docker.get_pool", return_value=mock_pool):
    # ... test code
```

**Pattern**: Mock singleton getters (`get_config`, `get_pool`) rather than instances

### 4. Test Class Organization

**Classes Used for Grouping**:
```python
class TestTransportConfig:
    """Tests for transport configuration."""

    def test_default_transport_is_http(self, tmp_path: Path) -> None:
        ...

    def test_transport_from_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        ...
```

**Pattern**: Classes group related functionality (no inheritance, pure organization)

### 5. Async Test Patterns

**Decorator Usage**:
```python
@pytest.mark.asyncio
async def test_scout_cat_file(mock_ssh_config: Path) -> None:
    """scout with file path cats the file."""
    # ... async test code
```

**Configuration**: `asyncio_mode = "auto"` in `pyproject.toml` enables automatic async test detection

**Await Pattern**:
```python
result = await scout("testhost:/etc/hosts")
assert "file contents" in result
```

## Test Implementation Quality

### Strengths

1. **Excellent Naming**
   - Tests follow `test_<component>_<behavior>` pattern
   - Docstrings describe intent: "scout with invalid target returns error"
   - Clear assertion messages

2. **Comprehensive Middleware Testing**
   - Error handling tested with stats tracking
   - Logging tested with payload truncation
   - Timing tested with slow request warnings
   - Integration tests verify middleware stack order

3. **Mock Realism**
   - SSH commands return realistic output formats
   - Docker commands use actual Docker CLI output
   - ZFS commands match real `zfs` tool output

4. **State Management**
   - `reset_state()` fixture ensures test isolation
   - No shared global state between tests
   - Temp files cleaned up via `tmp_path` fixture

5. **Error Testing**
   - Invalid inputs tested (empty host, empty path)
   - Missing resources tested (unknown host, path not found)
   - Connection failures tested with retry logic

6. **Dynamic Resource Testing**
   - Tests verify resource templates registered dynamically
   - Tests check URI scheme generation per host
   - Tests validate metadata (name, description)

### Weaknesses/Gaps

1. **Limited Edge Cases**
   - Binary file handling not tested
   - Extremely large files (>1MB) edge cases
   - Unicode/special characters in paths not thoroughly tested
   - Symlink handling not covered

2. **Concurrency Testing**
   - Only `test_ping.py` tests concurrent operations thoroughly
   - Connection pool race conditions not fully tested
   - No stress tests for connection exhaustion

3. **Security Testing**
   - Path traversal attempts not tested
   - Command injection scenarios not covered
   - SSH key permission issues not tested

4. **Resource Error Handling**
   - Not all resource types test connection failures
   - Partial output scenarios not covered
   - Timeout scenarios rarely tested

5. **Integration Gaps**
   - No tests with real SSH server (all mocked)
   - HTTP transport not integration-tested
   - Middleware interaction edge cases limited

## Mocking Patterns Deep Dive

### Pattern 1: AsyncMock for SSH

```python
mock_conn = AsyncMock()
mock_conn.run.side_effect = [
    MagicMock(stdout="regular file", returncode=0),  # First call
    MagicMock(stdout="file contents", returncode=0),  # Second call
]
```

**Why**: Tests sequential commands (stat then cat) without real SSH

### Pattern 2: Connection State Tracking

```python
mock_conn.is_closed = False  # Simulate open connection
# Later...
mock_conn.is_closed = True  # Simulate closed connection
```

**Why**: Tests pool behavior on stale connections

### Pattern 3: Pool Singleton Mocking

```python
with patch("scout_mcp.resources.docker.get_pool", return_value=mock_pool):
    # get_pool() now returns mock_pool
```

**Why**: Avoids complex pool instantiation in tests

### Pattern 4: Config Mocking via set_config

```python
from scout_mcp.services import set_config
set_config(Config(ssh_config_path=mock_ssh_config))
```

**Why**: Injects test config without environment variable manipulation

### Pattern 5: Environment Variable Mocking

```python
def test_env_vars_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCOUT_MAX_FILE_SIZE", "5242880")
    config = Config()
    assert config.max_file_size == 5242880
```

**Why**: Tests environment-based configuration safely

## Fixture Usage Analysis

### Shared Fixtures (used across multiple files)

1. **mock_ssh_config**: Temp SSH config file
   - Used in: test_integration.py, test_server_lifespan.py, test_resources/
   - Pattern: Creates realistic SSH config with 2-3 hosts

2. **mock_ssh_host**: SSHHost instance
   - Used in: test_pool.py, test_executors.py
   - Pattern: Provides consistent test host

3. **reset_globals**: State reset
   - Used in: test_integration.py (autouse)
   - Pattern: Ensures singleton state cleared

### Specialized Fixtures

1. **mock_context**: Middleware context
   - Used in: test_middleware/*.py
   - Pattern: Different contexts for tools/resources

2. **mock_connection**: SSH connection
   - Used in: test_executors.py
   - Pattern: Pre-configured AsyncMock

3. **client**: TestClient for HTTP
   - Used in: test_health.py
   - Pattern: Starlette TestClient for HTTP endpoints

## Test Assertions Quality

### Strong Assertions

```python
# Specific value checks
assert hosts["dookie"].hostname == "100.122.19.93"
assert hosts["dookie"].port == 22

# Multiple related assertions
assert len(hosts) == 2
assert "dookie" in hosts
assert "production" not in hosts

# Error message validation
with pytest.raises(ResourceError, match="Unknown host 'unknown'"):
    await scout_resource("unknownhost", "etc/hosts")
```

### Weak Assertions (few instances)

```python
# Overly broad checks
assert "test" in result  # Could match unintended strings

# Mock call verification without arg checking
mock_logger.info.assert_called()  # Doesn't verify what was logged
```

**Overall**: 90%+ of assertions are specific and valuable

## Async Testing Approaches

### Approach 1: pytest-asyncio with auto mode

**Configuration**: `asyncio_mode = "auto"` in pyproject.toml

**Pattern**:
```python
@pytest.mark.asyncio
async def test_async_operation() -> None:
    result = await async_function()
    assert result == expected
```

**Benefits**: Clean syntax, automatic event loop management

### Approach 2: AsyncMock for awaitable returns

```python
call_next = AsyncMock(return_value="result")
await middleware.on_message(context, call_next)
```

**Pattern**: AsyncMock for functions that return awaitables

### Approach 3: Time-sensitive async tests

```python
async def test_concurrent_execution() -> None:
    start = time.perf_counter()
    results = await check_hosts_online(hosts)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.2, "Should be concurrent, not sequential"
```

**Pattern**: Validates concurrency by measuring wall-clock time

## Coverage Gaps

Based on test file analysis, these areas likely have lower coverage:

1. **Connection Pool Edge Cases**
   - Max pool size enforcement (not tested)
   - Connection leak detection
   - Rapid connect/disconnect cycles

2. **Resource Error Paths**
   - Network timeouts during resource read
   - Partial response handling
   - Malformed SSH output parsing

3. **Middleware Edge Cases**
   - Middleware exception propagation
   - Nested middleware error handling
   - Middleware initialization failures

4. **Transport Layer**
   - HTTP transport under load
   - STDIO transport edge cases
   - Transport switching at runtime

5. **Security Scenarios**
   - Path traversal attempts (../../../etc/passwd)
   - Command injection in queries
   - SSH key permission failures
   - Identity file not found scenarios

## Benchmark Suite Analysis

The `/mnt/cache/code/scout_mcp/tests/benchmarks/` directory contains a sophisticated performance testing framework:

### Benchmark Categories

1. **Connection Pool** (`test_connection_pool.py`)
   - Cold start latency: 10.47ms
   - Warm lookup: 0.02ms
   - Lock contention analysis
   - Memory footprint per connection

2. **SSH Operations** (`test_ssh_operations.py`)
   - stat_path: 1.10ms
   - cat_file: 1.13ms
   - Large file transfer: 93.46 MB/s

3. **Config Parsing** (`test_config_parsing.py`)
   - 100 hosts: 1.67ms (59,913 hosts/s)
   - 1000 hosts: 10.16ms (98,460 hosts/s)

4. **URI Parsing** (`test_uri_parsing.py`)
   - Standard: 0.0011ms (<0.01% overhead)

5. **End-to-End** (`test_end_to_end.py`)
   - Cold request: 16.10ms
   - Warm request: 10.62ms
   - Throughput: 2,186 req/s (single host)

### Profiling Tools

- **CPU Profiling**: `profile_cpu.py` - cProfile with top functions analysis
- **Memory Profiling**: `profile_memory.py` - Memory growth tracking

### Benchmark Quality

**Strengths**:
- Statistical analysis (mean, P95, P99)
- Realistic workloads
- Clear performance targets
- Comprehensive README.md with results

**Limitations**:
- No CI integration yet
- No historical trend tracking
- No comparison against baseline

## Integration vs Unit Test Separation

### Unit Tests (Isolated)
- **Files**: test_config.py, test_pool.py, test_executors.py, test_scout.py
- **Characteristics**: Mock all external dependencies, test single function/class
- **Example**: `test_pool.py` mocks asyncssh.connect entirely

### Integration Tests (Multi-component)
- **Files**: test_integration.py, test_server_lifespan.py, test_middleware/test_integration.py
- **Characteristics**: Test interactions between components, mock only SSH
- **Example**: test_integration.py tests tool → pool → executor flow

### End-to-End Tests (Mocked SSH)
- **Files**: test_integration.py (scout tool tests)
- **Characteristics**: Full request cycle, realistic SSH responses
- **Example**: `test_scout_cat_file` tests complete file read flow

**Note**: No tests use real SSH (all mocked). This is appropriate for CI/CD but limits real-world validation.

## Test Execution Metrics

- **Total Tests**: 121 (from pytest collection)
- **Test Files**: 31 Python files
- **Coverage**: ~81% (documented in CLAUDE.md)
- **Async Tests**: ~60% use `@pytest.mark.asyncio`
- **Fixture Usage**: ~40 unique fixtures across all tests

## Key Patterns to Follow

When adding new tests, follow these established patterns:

1. **Naming**: `test_<component>_<specific_behavior>`
2. **Docstrings**: Single-line description of what's tested
3. **Fixtures**: Use `tmp_path` for files, `mock_ssh_config` for SSH config
4. **Mocking**: AsyncMock for async, MagicMock for sync returns
5. **State Reset**: Use `reset_state()` or autouse fixture
6. **Assertions**: Specific value checks with descriptive messages
7. **Error Tests**: Use `pytest.raises(ErrorType, match="substring")`
8. **Async**: Use `@pytest.mark.asyncio` with `await`

## Next Steps for Test Improvements

1. **Add Real SSH Integration Tests**
   - Create Docker container with SSH server
   - Test against real openssh-server
   - Validate actual SSH behavior

2. **Expand Edge Case Coverage**
   - Binary files
   - Unicode filenames
   - Symlinks
   - Large directory listings

3. **Security Testing Suite**
   - Path traversal attempts
   - Command injection
   - Permission denial scenarios

4. **Benchmark CI Integration**
   - Add GitHub Actions workflow
   - Track performance trends
   - Alert on regressions

5. **Concurrency Stress Tests**
   - 1000+ concurrent connections
   - Connection pool exhaustion
   - Race condition detection

6. **Coverage Goal: 90%+**
   - Focus on error handlers
   - Add resource edge cases
   - Test middleware combinations

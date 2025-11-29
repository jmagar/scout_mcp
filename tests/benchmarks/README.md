# Scout MCP Performance Benchmarks

Comprehensive performance benchmarking suite for scout_mcp FastMCP server.

## Quick Start

```bash
# Run all benchmarks
python -m pytest benchmarks/ -v -s

# Run specific benchmark suite
python -m pytest benchmarks/test_connection_pool.py -v -s
python -m pytest benchmarks/test_ssh_operations.py -v -s
python -m pytest benchmarks/test_config_parsing.py -v -s
python -m pytest benchmarks/test_uri_parsing.py -v -s
python -m pytest benchmarks/test_end_to_end.py -v -s

# CPU profiling
python benchmarks/profile_cpu.py

# Memory profiling
python benchmarks/profile_memory.py
```

## Benchmark Suites

### 1. Connection Pool (`test_connection_pool.py`)

Tests connection pooling performance, lock contention, and resource usage.

**Key Tests:**
- `test_cold_start_latency` - First connection establishment
- `test_warm_connection_latency` - Cached connection retrieval
- `test_concurrent_single_host_lock_contention` - Lock contention under load
- `test_concurrent_multi_host_parallelism` - Parallel connection creation
- `test_pool_memory_footprint` - Memory usage scaling
- `test_cleanup_task_overhead` - Background cleanup impact
- `test_stale_connection_detection` - Connection failover

**Results:**
```
Cold start: 10.47ms
Warm lookup: 0.02ms
Lock contention (100 req): 1.70ms avg, 2.60ms P95
Multi-host (10): 104ms (BOTTLENECK - should be 15ms)
Memory (100 conns): 7.9 KB
```

---

### 2. SSH Operations (`test_ssh_operations.py`)

Tests SSH command execution performance and overhead.

**Key Tests:**
- `test_stat_path_latency` - File type detection
- `test_cat_file_latency` - File reading
- `test_ls_dir_latency` - Directory listing
- `test_run_command_latency` - Arbitrary command execution
- `test_large_file_transfer` - 1MB file transfer
- `test_concurrent_operations` - Concurrent SSH ops

**Results:**
```
stat_path: 1.10ms (13% overhead)
cat_file: 1.13ms (13% overhead)
ls_dir: 1.13ms (13% overhead)
Large file (1MB): 93.46 MB/s (7% overhead)
```

---

### 3. Configuration Parsing (`test_config_parsing.py`)

Tests SSH config parsing and caching performance.

**Key Tests:**
- `test_ssh_config_parsing_cold` - Initial parse (100 hosts)
- `test_ssh_config_parsing_cached` - Cached access
- `test_large_ssh_config_parsing` - Large config (1000 hosts)
- `test_host_lookup_performance` - Individual host lookup
- `test_allowlist_filtering_performance` - Filter performance
- `test_regex_parsing_overhead` - Regex overhead analysis

**Results:**
```
Parse 100 hosts: 1.67ms (59,913 hosts/s)
Parse 1000 hosts: 10.16ms (98,460 hosts/s)
Cached access: 0.011ms avg, 0.013ms P95
```

---

### 4. URI Parsing (`test_uri_parsing.py`)

Tests URI parsing performance and edge cases.

**Key Tests:**
- `test_uri_parsing_latency` - Standard URI parsing
- `test_hosts_command_parsing` - Special 'hosts' command
- `test_long_path_parsing` - Long path handling
- `test_error_case_performance` - Invalid URI handling

**Results:**
```
URI parsing: 0.0011ms avg (<0.01% overhead)
Long paths (305 chars): 0.0007ms
Error cases: 0.0004ms
```

---

### 5. End-to-End (`test_end_to_end.py`)

Tests full request flow from API to SSH.

**Key Tests:**
- `test_full_request_latency_cold` - Cold start request
- `test_full_request_latency_warm` - Warm request
- `test_concurrent_requests_same_host` - Concurrent same host
- `test_concurrent_requests_different_hosts` - Concurrent multi-host
- `test_mixed_operation_workload` - Mixed operations
- `test_hosts_command_performance` - Hosts listing

**Results:**
```
Cold start: 16.10ms
Warm request: 10.62ms avg, 10.99ms P95
Single-host (50 conc): 2,186 req/s
Multi-host (10 conc): 149 req/s (BOTTLENECK)
Hosts command: 0.01ms
```

---

## Profiling Tools

### CPU Profiling

```bash
python benchmarks/profile_cpu.py
```

**Output:**
- Top 30 functions by cumulative time
- Top 20 functions by internal time
- Call counts
- Full profile saved to `.cache/cpu_profile.txt`

**Findings:**
- Most time in `asyncio.sleep()` (mock network)
- Lock operations: <1% of total time
- No CPU bottlenecks (I/O bound)

---

### Memory Profiling

```bash
python benchmarks/profile_memory.py
```

**Output:**
- Memory growth after pool creation
- Memory growth after 100 connections
- Memory growth after 1000 reuses
- Top memory consumers
- Leak detection

**Findings:**
- Peak memory: 0.07 MB (100 connections)
- Per-connection: ~80 bytes
- No memory leaks detected

---

## Performance Metrics

### Summary Table

| Component | Metric | Value | Status |
|-----------|--------|-------|--------|
| Pool | Cold start | 10.47ms | ✅ Good |
| Pool | Warm lookup | 0.02ms | ✅ Excellent |
| Pool | Lock contention | 1.70ms avg | ⚠️ Moderate |
| Pool | Multi-host | 104ms | ❌ Critical |
| Pool | Memory (100 conns) | 7.9 KB | ✅ Excellent |
| SSH | stat_path | 1.10ms | ✅ Good |
| SSH | cat_file | 1.13ms | ✅ Good |
| SSH | Large file (1MB) | 93.46 MB/s | ✅ Good |
| Config | Parse 100 hosts | 1.67ms | ✅ Good |
| Config | Cached access | 0.011ms | ✅ Excellent |
| URI | Parsing | 0.0011ms | ✅ Excellent |
| E2E | Cold request | 16.10ms | ✅ Good |
| E2E | Warm request | 10.62ms | ✅ Good |

---

## Known Issues

### Critical Bottlenecks

1. **Global Lock Serialization** (`pool.py:44`)
   - Impact: 10x slowdown on parallel connections
   - Test: `test_concurrent_multi_host_parallelism` (FAILS)
   - Expected: 15ms, Actual: 104ms

2. **No Connection Pool Limits** (`pool.py:35`)
   - Impact: Memory exhaustion under load
   - Test: No limit enforcement in pool initialization

3. **No Request Concurrency Limits** (`server.py:36`)
   - Impact: DoS vulnerability
   - Test: No backpressure mechanism

---

## Interpreting Results

### Good Performance

```
[PERF] Metric: X.XXms
```

If value is:
- <1ms: ✅ Excellent (negligible overhead)
- 1-10ms: ✅ Good (acceptable for network operations)
- 10-50ms: ⚠️ Moderate (check if expected)
- >50ms: ❌ Poor (investigate bottleneck)

### Throughput

```
Throughput: X,XXX req/s
```

Target thresholds:
- >1000 req/s: ✅ Excellent
- 500-1000 req/s: ✅ Good
- 100-500 req/s: ⚠️ Moderate
- <100 req/s: ❌ Poor

### Memory

```
Memory: X.XX MB
```

Target per 100 connections:
- <1 MB: ✅ Excellent
- 1-10 MB: ✅ Good
- 10-50 MB: ⚠️ Moderate
- >50 MB: ❌ Poor

---

## Adding New Benchmarks

### Template

```python
import pytest
import time
import statistics

@pytest.mark.asyncio
async def test_my_benchmark() -> None:
    """Benchmark description."""
    latencies = []

    for _ in range(100):
        start = time.perf_counter()
        # ... operation to benchmark ...
        latencies.append(time.perf_counter() - start)

    avg = statistics.mean(latencies) * 1000
    p95 = statistics.quantiles(latencies, n=20)[18] * 1000

    print(f"\n[PERF] My benchmark (n=100):")
    print(f"  Avg: {avg:.2f}ms")
    print(f"  P95: {p95:.2f}ms")

    assert avg < TARGET_MS, "Performance regression"
```

---

## CI Integration

Add to `.github/workflows/benchmark.yml`:

```yaml
name: Benchmarks
on: [push, pull_request]

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -e .[dev]
      - run: python -m pytest benchmarks/ -v
      - run: python benchmarks/profile_cpu.py
      - run: python benchmarks/profile_memory.py
```

---

## References

- Full analysis: `.docs/performance-analysis.md`
- Executive summary: `.docs/performance-summary.md`
- Bottleneck visualization: `.docs/performance-bottlenecks.md`

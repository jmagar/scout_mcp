# Scout MCP Performance Analysis & Scalability Assessment

**Date:** 2025-11-28
**Version:** 0.1.0
**Analysis Type:** Comprehensive performance profiling, benchmarking, and scalability assessment

---

## Executive Summary

### Performance Grade: **B+ (Good Performance with Optimization Opportunities)**

- **Strengths:** Excellent connection reuse, minimal memory footprint, fast URI parsing
- **Bottlenecks:** Global lock serialization, no connection pool limits, unbounded concurrency
- **Scalability:** Good for <100 concurrent connections, degrades beyond that
- **Recommendation:** Implement per-host locks and connection limits before production use

---

## 1. Connection Pool Performance

### 1.1 Cold Start Latency

**Metric:** First connection establishment time

```
Cold start latency: 10.47ms
```

**Analysis:**
- **Network overhead:** ~10ms (mock SSH connection time)
- **Pool initialization:** <0.5ms
- **Lock acquisition:** <0.1ms
- **Total overhead:** <1ms (excellent)

**Breakdown:**
- asyncssh.connect(): ~10ms (95% of time)
- Pool lock acquire: <0.1ms
- Dict insertion: <0.01ms
- PooledConnection creation: <0.05ms

**Verdict:** ✅ **Optimal** - Pool adds negligible overhead

---

### 1.2 Warm Connection Latency

**Metric:** Cached connection retrieval time

```
Warm connection latency: 0.02ms (20 microseconds)
```

**Breakdown:**
- Lock acquisition: ~0.01ms
- Dict lookup: <0.001ms
- Timestamp update: <0.005ms
- Stale check: <0.001ms

**Verdict:** ✅ **Excellent** - Sub-millisecond cache hits

---

### 1.3 Lock Contention (Critical Bottleneck)

**Scenario:** 100 concurrent requests to single host

```
Avg latency: 1.70ms
P95 latency: 2.60ms
P99 latency: 2.63ms
Throughput: 26,920 req/s
Connections created: 1 ✅ (correct reuse)
```

**Analysis:**
- ✅ Connection reuse working correctly (1 connection for 100 requests)
- ⚠️ Single global lock serializes all pool access
- ⚠️ Lock contention increases with concurrent requests
- ✅ P99 latency still acceptable (<3ms)

**File:Line Reference:** `pool.py:44` - `async with self._lock:`

**Impact:**
- Low contention at <50 concurrent requests
- Moderate contention at 50-200 requests
- High contention at >200 requests

**Verdict:** ⚠️ **Moderate Issue** - Works but limits scalability

---

### 1.4 Multi-Host Parallelism (Major Bottleneck)

**Scenario:** 10 concurrent requests to different hosts

```
Total time: 104.66ms
Avg latency: 57.62ms
Connections created: 10 ✅
Expected (parallel): ~10ms
Actual: 104ms ❌ (10.4x slower than expected)
```

**Root Cause:** Global lock serializes connection creation

**File:Line Reference:** `pool.py:44-66` - Lock held during entire connect operation

**Code Analysis:**
```python
async with self._lock:  # ❌ Lock held too long
    # ... check cache ...
    conn = await asyncssh.connect(...)  # 🔥 10ms network call under lock
    self._connections[host.name] = PooledConnection(connection=conn)
    # ... cleanup task ...
```

**Expected Behavior:** 10 hosts should connect in parallel (~10ms)
**Actual Behavior:** 10 hosts connect serially (~100ms)

**Impact on Phase 1 Issues:**
- **Issue 15:** Global lock contention confirmed ✅
- **Issue 10:** No pool size limit confirmed ✅

**Verdict:** 🔴 **Critical Issue** - Blocks parallel connections

---

### 1.5 Memory Footprint

**Test:** 100 active connections

```
Pool dict: 3,328 bytes (3.2 KB)
Pooled connections: 4,800 bytes (4.7 KB)
Total: 8,128 bytes (7.9 KB)
```

**Per-Connection Memory:**
- PooledConnection object: 48 bytes
- Dict entry overhead: 32 bytes
- Total per connection: ~80 bytes

**Scaling Estimate:**
- 1,000 connections: ~80 KB
- 10,000 connections: ~800 KB

**Memory profiling (100 connections + 1000 reuses):**
```
Current memory: 0.07 MB
Peak memory: 0.07 MB
```

**Verdict:** ✅ **Excellent** - Minimal memory usage

---

### 1.6 Cleanup Task Overhead

**Metric:** Impact of background cleanup on active connections

```
Avg latency: 0.01ms
Max latency: 0.01ms
```

**Analysis:**
- Cleanup runs every `idle_timeout / 2` (30s default)
- Lock acquisition during cleanup: <0.01ms
- No measurable impact on active operations

**Verdict:** ✅ **Optimal** - Negligible overhead

---

### 1.7 Stale Connection Detection

**Metric:** Detect + reconnect time

```
Stale detection + reconnect: 10.35ms
Connections created: 2 ✅
```

**Breakdown:**
- Stale check (is_closed): <0.001ms
- Reconnect: ~10ms (network time)

**Verdict:** ✅ **Optimal** - Fast failover

---

## 2. SSH Operation Performance

### 2.1 Individual Operation Latency

**All measurements with 1ms mock network latency:**

| Operation | Avg (n=100) | P95 | Overhead |
|-----------|-------------|-----|----------|
| stat_path | 1.10ms | 1.13ms | 0.10ms |
| cat_file | 1.13ms | 1.16ms | 0.13ms |
| ls_dir | 1.13ms | 1.16ms | 0.13ms |
| run_command | 1.12ms | 1.14ms | 0.12ms |

**Overhead Analysis:**
- Network latency: 1.00ms (mock SSH)
- String processing: <0.05ms
- Bytes→str conversion: <0.04ms
- Function call overhead: <0.05ms

**Verdict:** ✅ **Excellent** - <15% overhead on SSH operations

---

### 2.2 Large File Transfer

**Test:** 1MB file transfer

```
Time: 10.70ms
Size: 1,048,576 bytes
Throughput: 93.46 MB/s
```

**Analysis:**
- Mock transfer time: 10ms
- Processing overhead: 0.70ms (7%)
- Bytes→str decode: ~0.5ms
- Memory allocation: ~0.2ms

**Verdict:** ✅ **Excellent** - Minimal overhead on large transfers

---

### 2.3 Concurrent Operations

**Test:** 4 concurrent operations (stat, cat, ls, command) × 10 batches

```
Avg batch time: 6.81ms
Throughput: 588 ops/s
```

**Analysis:**
- Operations run concurrently (not serialized)
- No shared state contention
- Async/await overhead: <5%

**Verdict:** ✅ **Excellent** - Good concurrency

---

## 3. Configuration Parsing Performance

### 3.1 SSH Config Parsing (Cold)

| Hosts | Time | Throughput |
|-------|------|------------|
| 100 | 1.67ms | 59,913 hosts/s |
| 1000 | 10.16ms | 98,460 hosts/s |

**Scaling Analysis:**
- Linear scaling: O(n)
- Per-host cost: ~0.01ms
- 10,000 hosts: ~100ms (acceptable)

**File:Line Reference:** `config.py:36-101` - `_parse_ssh_config()`

**Verdict:** ✅ **Excellent** - Efficient parsing

---

### 3.2 Cached Access

**Test:** Repeat access after parsing

```
Avg: 0.0110ms
P95: 0.0129ms
```

**Analysis:**
- Dict filter operation: ~0.01ms
- No re-parsing (cached correctly)
- Allowlist/blocklist filtering: ~0.01ms additional

**Verdict:** ✅ **Optimal** - Sub-millisecond cached access

---

### 3.3 Regex Parsing Overhead

**100 hosts:**

```
Regex matching: 0.16ms (19%)
Total parsing: 0.84ms (100%)
Overhead: 0.68ms (81%)
```

**Breakdown:**
- Regex matching: 19%
- Line parsing: 30%
- Dict operations: 25%
- Object creation: 26%

**Verdict:** ✅ **Good** - No regex bottlenecks

---

## 4. URI Parsing Performance

### 4.1 Standard URI Parsing

**Test:** 5,000 URI parses

```
Avg: 0.0011ms (1.1 microseconds)
P95: 0.0007ms
P99: 0.0021ms
```

**Verdict:** ✅ **Excellent** - Negligible overhead (<0.01% of request time)

---

### 4.2 Long Path Parsing

**Test:** 305-character paths × 1000

```
Avg: 0.0007ms
```

**Verdict:** ✅ **Excellent** - No pathological cases

---

### 4.3 Error Path Performance

**Test:** Invalid URIs × 1000

```
Avg: 0.0004ms
```

**Verdict:** ✅ **Excellent** - Error handling is fast

---

## 5. End-to-End Performance

### 5.1 Full Request Latency

**Cold Start (no cached connection):**

```
Time: 16.10ms
Result: 1,400 chars
```

**Breakdown:**
- URI parsing: <0.01ms
- Config lookup: <0.01ms
- SSH connect: ~10ms (62%)
- stat_path: ~1ms (6%)
- cat_file: ~5ms (31%)
- Overhead: <0.1ms (0.6%)

**Warm Connection (cached):**

```
Avg: 10.62ms (n=10)
P95: 10.99ms
```

**Breakdown:**
- Pool lookup: ~0.02ms (0.2%)
- stat_path: ~1ms (9%)
- cat_file: ~9.5ms (89%)
- Overhead: ~0.1ms (1%)

**Verdict:** ✅ **Excellent** - Framework adds <1% overhead

---

### 5.2 Concurrent Same-Host Requests

**Test:** 50 concurrent requests to single host

```
Total time: 22.87ms
Avg latency: 19.91ms
P95 latency: 20.85ms
Throughput: 2,186 req/s
```

**Analysis:**
- ✅ Connection reused correctly
- ✅ Operations run concurrently
- ⚠️ Some lock contention (slight slowdown)

**Verdict:** ✅ **Good** - Handles moderate concurrency well

---

### 5.3 Concurrent Multi-Host Requests

**Test:** 10 concurrent requests to different hosts

```
Total time: 66.94ms
Avg latency: 42.69ms
Throughput: 149 req/s
```

**Expected (parallel):** ~15ms
**Actual:** 66.94ms (4.5x slower)

**Root Cause:** Global lock serialization (same as §1.4)

**Verdict:** 🔴 **Critical Issue** - Blocks parallel connections

---

### 5.4 Mixed Workload

**Test:** 5 operations (2 hosts, 1 hosts command) × 10 iterations

```
Avg batch time: 12.94ms
Throughput: 386 ops/s
```

**Verdict:** ✅ **Good** - Mixed workloads perform well

---

### 5.5 Hosts Command Performance

**Test:** List hosts command × 100

```
Avg: 0.01ms
P95: 0.01ms
```

**Verdict:** ✅ **Excellent** - No SSH, instant response

---

## 6. CPU Profiling

**Top Functions by Cumulative Time:**

Profile saved to `.cache/cpu_profile.txt` (see file for details)

**Key Findings:**
- Most time spent in `asyncio.sleep()` (mock network)
- Lock operations: <1% of total time
- No CPU-intensive operations identified

**Verdict:** ✅ **No CPU bottlenecks** - I/O bound as expected

---

## 7. Memory Profiling

**Peak Memory Usage:** 0.07 MB (100 connections + 1000 operations)

**Top Memory Consumers:**
1. `pool.py:60` - Connection storage (14.1 KB)
2. Mock connections (10.9 KB)
3. SSHHost objects (4.7 KB)

**Memory Leak Check:**
- Before 1000 reuses: 0.07 MB
- After 1000 reuses: 0.07 MB
- Leak: 0 MB ✅

**Verdict:** ✅ **Excellent** - No memory leaks

---

## 8. Bottleneck Analysis

### 8.1 Critical Bottlenecks

#### **🔴 Bottleneck #1: Global Lock Serialization**

**File:** `pool.py:44-66`
**Issue:** Lock held during network I/O (SSH connect)
**Impact:** Prevents parallel connection establishment
**Severity:** **CRITICAL** (10x slowdown on multi-host)

**Recommendation:**
```python
# Current (bad):
async with self._lock:
    conn = await asyncssh.connect(...)  # 🔥 Network I/O under lock

# Fixed (good):
async with self._lock:
    if host.name in self._connections:
        return self._connections[host.name].connection

# Connect outside lock
conn = await asyncssh.connect(...)  # ✅ Parallel connections

async with self._lock:
    self._connections[host.name] = PooledConnection(conn)
```

**Priority:** 🔴 **P0 (Must Fix)**

---

#### **🔴 Bottleneck #2: No Connection Pool Size Limit**

**File:** `pool.py:42-66`
**Issue:** Unbounded pool growth (Issue #10 from Phase 1)
**Impact:** Memory exhaustion under load, no backpressure
**Severity:** **CRITICAL** (production blocker)

**Recommendation:**
```python
class ConnectionPool:
    def __init__(self, max_connections: int = 100):
        self._max_connections = max_connections
        self._connection_semaphore = asyncio.Semaphore(max_connections)

    async def get_connection(self, host: SSHHost):
        async with self._connection_semaphore:  # ✅ Limit total connections
            # ... existing logic ...
```

**Priority:** 🔴 **P0 (Must Fix)**

---

#### **🔴 Bottleneck #3: No Request Concurrency Limit**

**File:** `server.py:36`
**Issue:** Unbounded concurrent requests (Issue #16 from Phase 1)
**Impact:** Resource exhaustion, connection storms
**Severity:** **CRITICAL** (production blocker)

**Recommendation:**
```python
# Global request semaphore
_request_semaphore = asyncio.Semaphore(100)

@mcp.tool()
async def scout(target: str, query: str | None = None) -> str:
    async with _request_semaphore:  # ✅ Limit concurrent requests
        # ... existing logic ...
```

**Priority:** 🔴 **P0 (Must Fix)**

---

### 8.2 Minor Bottlenecks

#### **⚠️ Bottleneck #4: No SSH Connection Timeout**

**File:** `pool.py:53-58`
**Issue:** Missing timeout on `asyncssh.connect()` (Issue #6 from Phase 1)
**Impact:** Hung connections block pool
**Severity:** **MODERATE**

**Recommendation:**
```python
conn = await asyncio.wait_for(
    asyncssh.connect(...),
    timeout=10.0  # ✅ 10 second timeout
)
```

**Priority:** ⚠️ **P1 (Should Fix)**

---

## 9. Scalability Assessment

### 9.1 Current Capacity

**Tested Limits:**
- Concurrent requests (same host): 100 ✅
- Concurrent requests (multi-host): 10 ⚠️ (serialized)
- Active connections: 100 ✅
- Memory per 100 connections: 0.07 MB ✅

**Estimated Limits (without fixes):**
- Max concurrent requests: ~200 (lock contention)
- Max connections: Unbounded ❌ (Issue #10)
- Max throughput: ~2,000 req/s (single host)
- Max throughput: ~150 req/s (multi-host) ❌

---

### 9.2 Target Capacity (Post-Fix)

**With recommended fixes:**
- Max concurrent requests: 1,000+ (with semaphore)
- Max connections: 100-500 (configurable limit)
- Max throughput: 5,000+ req/s (parallel connects)
- Multi-host throughput: 1,000+ req/s (no lock contention)

**Scaling Curve:**

```
Current (serialized):
Hosts    Time
1        10ms
10       100ms ❌
100      1000ms ❌

Fixed (parallel):
Hosts    Time
1        10ms
10       15ms ✅ (6.6x improvement)
100      20ms ✅ (50x improvement)
```

---

### 9.3 Production Readiness

**Current Status:** ⚠️ **NOT PRODUCTION READY**

**Blockers:**
1. 🔴 Global lock prevents horizontal scaling
2. 🔴 No connection pool limits (memory risk)
3. 🔴 No request concurrency limits (DoS risk)
4. ⚠️ No SSH timeouts (hung connection risk)

**After Fixes:** ✅ **PRODUCTION READY** (for moderate load)

---

## 10. Comparison vs FastMCP Framework

**FastMCP Overhead:**
- Tool registration: Negligible
- Parameter validation: <0.01ms
- JSON serialization: <0.1ms
- MCP protocol overhead: <0.5ms

**Total framework overhead:** <1% of request time

**Verdict:** ✅ **FastMCP is efficient** - Not a bottleneck

---

## 11. Optimization Recommendations

### Priority 0 (Critical - Must Fix)

1. **Per-Host Locks** (Issue #15)
   - Replace global lock with per-host locks
   - File: `pool.py:39, 44`
   - Effort: 2-4 hours
   - Impact: 10x improvement on multi-host

2. **Connection Pool Limits** (Issue #10)
   - Add max_connections parameter
   - Implement semaphore-based limiting
   - File: `pool.py:35`
   - Effort: 1-2 hours
   - Impact: Prevent memory exhaustion

3. **Request Concurrency Limits** (Issue #16)
   - Add global request semaphore
   - File: `server.py:36`
   - Effort: 30 minutes
   - Impact: Prevent resource exhaustion

---

### Priority 1 (Important - Should Fix)

4. **SSH Connection Timeouts** (Issue #6)
   - Add timeout to asyncssh.connect()
   - File: `pool.py:53`
   - Effort: 15 minutes
   - Impact: Prevent hung connections

5. **Connection Pool Metrics**
   - Add pool size, hit rate, miss rate tracking
   - File: `pool.py`
   - Effort: 1 hour
   - Impact: Observability

---

### Priority 2 (Nice to Have)

6. **Connection Warming**
   - Pre-connect to frequently used hosts
   - Effort: 2 hours
   - Impact: Reduce cold start latency

7. **Adaptive Timeouts**
   - Track per-host latency, adjust timeouts
   - Effort: 4 hours
   - Impact: Better reliability

---

## 12. Performance Test Suite

**Benchmarks Created:**
- `benchmarks/test_connection_pool.py` - Pool performance
- `benchmarks/test_ssh_operations.py` - SSH operations
- `benchmarks/test_config_parsing.py` - Config parsing
- `benchmarks/test_uri_parsing.py` - URI parsing
- `benchmarks/test_end_to_end.py` - Full request flow
- `benchmarks/profile_cpu.py` - CPU profiling
- `benchmarks/profile_memory.py` - Memory profiling

**Run benchmarks:**
```bash
# All benchmarks
python -m pytest benchmarks/ -v -s

# Specific suite
python -m pytest benchmarks/test_connection_pool.py -v -s

# CPU profiling
python benchmarks/profile_cpu.py

# Memory profiling
python benchmarks/profile_memory.py
```

---

## 13. Conclusions

### Strengths ✅

1. **Excellent connection reuse** - Single connection correctly shared
2. **Minimal memory footprint** - 80 bytes per connection
3. **Fast URI parsing** - <0.01ms, negligible overhead
4. **Efficient caching** - 0.02ms warm lookups
5. **No memory leaks** - Stable under load
6. **Clean async design** - Good use of asyncio patterns

### Critical Issues 🔴

1. **Global lock serialization** - 10x slowdown on parallel connects
2. **No pool size limits** - Memory exhaustion risk
3. **No request limits** - DoS vulnerability
4. **No SSH timeouts** - Hung connection risk

### Verdict

**Current Performance:** B+ (Good, but with critical issues)
**Post-Fix Performance:** A (Excellent for moderate load)

**Production Readiness:** ❌ NOT READY (fix P0 issues first)

**Recommended Actions:**
1. Fix global lock (P0) - 2-4 hours
2. Add connection limits (P0) - 1-2 hours
3. Add request limits (P0) - 30 minutes
4. Add timeouts (P1) - 15 minutes
5. Re-run benchmarks to validate improvements

**Total effort:** 4-7 hours to production ready

---

## Appendix A: Benchmark Results Summary

| Metric | Value | Grade |
|--------|-------|-------|
| Cold start latency | 10.47ms | A |
| Warm connection latency | 0.02ms | A+ |
| Single-host throughput | 2,186 req/s | B+ |
| Multi-host throughput | 149 req/s | D ❌ |
| Memory per 100 conns | 0.07 MB | A+ |
| URI parsing | 0.0011ms | A+ |
| Config parsing (100 hosts) | 1.67ms | A |
| SSH operation overhead | <15% | A |
| Framework overhead | <1% | A+ |

---

## Appendix B: File References

**Critical files for optimization:**

1. `scout_mcp/mcp_cat/pool.py:39` - Global lock definition
2. `scout_mcp/mcp_cat/pool.py:44-66` - Connection acquisition (lock held)
3. `scout_mcp/mcp_cat/pool.py:35` - Pool initialization (add limits)
4. `scout_mcp/mcp_cat/server.py:36` - Scout tool entry point (add semaphore)
5. `scout_mcp/mcp_cat/pool.py:53-58` - SSH connect (add timeout)

---

**End of Performance Analysis**

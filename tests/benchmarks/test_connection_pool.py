"""Connection pool performance benchmarks."""

import asyncio
import statistics
import time
from typing import Any

import pytest

from scout_mcp.models import SSHHost
from scout_mcp.services.pool import ConnectionPool


class MockSSHConnection:
    """Mock SSH connection for testing."""

    def __init__(self, delay: float = 0.001) -> None:
        """Initialize mock connection."""
        self._delay = delay
        self._closed = False

    @property
    def is_closed(self) -> bool:
        """Check if connection is closed."""
        return self._closed

    def close(self) -> None:
        """Close connection."""
        self._closed = True

    async def run(self, command: str, check: bool = True) -> Any:
        """Mock command execution."""
        await asyncio.sleep(self._delay)
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()


class MockAsyncSSH:
    """Mock asyncssh module."""

    def __init__(self, delay: float = 0.001) -> None:
        """Initialize mock."""
        self._delay = delay
        self._connection_count = 0

    async def connect(self, *args: Any, **kwargs: Any) -> MockSSHConnection:
        """Mock SSH connection."""
        self._connection_count += 1
        await asyncio.sleep(self._delay)
        return MockSSHConnection(self._delay)


@pytest.fixture
def mock_host() -> SSHHost:
    """Create test SSH host."""
    return SSHHost(
        name="test-host",
        hostname="localhost",
        user="test",
        port=22,
    )


@pytest.mark.asyncio
async def test_cold_start_latency(
    mock_host: SSHHost,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Benchmark cold start connection time."""
    mock_ssh = MockAsyncSSH(delay=0.01)
    monkeypatch.setattr("scout_mcp.services.pool.asyncssh", mock_ssh)

    pool = ConnectionPool()

    start = time.perf_counter()
    await pool.get_connection(mock_host)
    elapsed = time.perf_counter() - start

    print(f"\n[PERF] Cold start latency: {elapsed * 1000:.2f}ms")
    assert elapsed < 0.05, "Cold start should complete in <50ms"


@pytest.mark.asyncio
async def test_warm_connection_latency(
    mock_host: SSHHost,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Benchmark warm connection retrieval time."""
    mock_ssh = MockAsyncSSH(delay=0.01)
    monkeypatch.setattr("scout_mcp.services.pool.asyncssh", mock_ssh)

    pool = ConnectionPool()

    # Prime the pool
    await pool.get_connection(mock_host)

    # Measure warm retrieval
    start = time.perf_counter()
    await pool.get_connection(mock_host)
    elapsed = time.perf_counter() - start

    print(f"\n[PERF] Warm connection latency: {elapsed * 1000:.2f}ms")
    assert elapsed < 0.001, "Warm retrieval should be <1ms (lock + dict lookup)"


@pytest.mark.asyncio
async def test_concurrent_single_host_lock_contention(
    mock_host: SSHHost,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Measure lock contention with concurrent requests to same host."""
    mock_ssh = MockAsyncSSH(delay=0.001)
    monkeypatch.setattr("scout_mcp.services.pool.asyncssh", mock_ssh)

    pool = ConnectionPool()
    num_requests = 100

    async def get_conn() -> float:
        start = time.perf_counter()
        await pool.get_connection(mock_host)
        return time.perf_counter() - start

    # Run concurrent requests
    start_total = time.perf_counter()
    results = await asyncio.gather(*[get_conn() for _ in range(num_requests)])
    elapsed_total = time.perf_counter() - start_total

    avg_latency = statistics.mean(results) * 1000
    p95_latency = statistics.quantiles(results, n=20)[18] * 1000
    p99_latency = statistics.quantiles(results, n=100)[98] * 1000
    throughput = num_requests / elapsed_total

    print(f"\n[PERF] Concurrent single-host (n={num_requests}):")
    print(f"  Avg latency: {avg_latency:.2f}ms")
    print(f"  P95 latency: {p95_latency:.2f}ms")
    print(f"  P99 latency: {p99_latency:.2f}ms")
    print(f"  Throughput: {throughput:.0f} req/s")
    print(f"  Connections created: {mock_ssh._connection_count}")

    # Should reuse single connection
    assert mock_ssh._connection_count == 1, "Should create only 1 connection"


@pytest.mark.asyncio
async def test_concurrent_multi_host_parallelism(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Measure parallelism with concurrent requests to different hosts."""
    mock_ssh = MockAsyncSSH(delay=0.01)
    monkeypatch.setattr("scout_mcp.services.pool.asyncssh", mock_ssh)

    pool = ConnectionPool()
    num_hosts = 10

    hosts = [
        SSHHost(
            name=f"host-{i}",
            hostname="localhost",
            user="test",
            port=22 + i,
        )
        for i in range(num_hosts)
    ]

    async def get_conn(host: SSHHost) -> float:
        start = time.perf_counter()
        await pool.get_connection(host)
        return time.perf_counter() - start

    # Run concurrent requests to different hosts
    start_total = time.perf_counter()
    results = await asyncio.gather(*[get_conn(host) for host in hosts])
    elapsed_total = time.perf_counter() - start_total

    avg_latency = statistics.mean(results) * 1000

    print(f"\n[PERF] Concurrent multi-host (n={num_hosts}):")
    print(f"  Total time: {elapsed_total * 1000:.2f}ms")
    print(f"  Avg latency: {avg_latency:.2f}ms")
    print(f"  Connections created: {mock_ssh._connection_count}")

    # Should create connections in parallel
    assert mock_ssh._connection_count == num_hosts
    # With 10ms connection time, serial would be ~100ms
    # Parallel should be faster, but system load can cause variance
    assert elapsed_total < 0.2, "Should create connections in parallel (<200ms)"


@pytest.mark.asyncio
async def test_pool_memory_footprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Measure connection pool memory usage."""
    import sys

    mock_ssh = MockAsyncSSH(delay=0.001)
    monkeypatch.setattr("scout_mcp.services.pool.asyncssh", mock_ssh)

    pool = ConnectionPool()

    # Create connections to 100 hosts
    hosts = [
        SSHHost(
            name=f"host-{i}",
            hostname="localhost",
            user="test",
            port=22,
        )
        for i in range(100)
    ]

    for host in hosts:
        await pool.get_connection(host)

    # Measure pool size
    pool_size = sys.getsizeof(pool._connections)
    pooled_conn_size = sum(sys.getsizeof(pc) for pc in pool._connections.values())
    total_size = pool_size + pooled_conn_size

    print("\n[PERF] Memory footprint (100 connections):")
    print(f"  Pool dict: {pool_size} bytes")
    print(f"  Pooled connections: {pooled_conn_size} bytes")
    print(f"  Total: {total_size} bytes ({total_size / 1024:.1f} KB)")


@pytest.mark.asyncio
async def test_cleanup_task_overhead(
    mock_host: SSHHost,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Measure cleanup task impact on active connections."""
    mock_ssh = MockAsyncSSH(delay=0.001)
    monkeypatch.setattr("scout_mcp.services.pool.asyncssh", mock_ssh)

    pool = ConnectionPool(idle_timeout=1)

    # Create connection to start cleanup task
    await pool.get_connection(mock_host)

    # Measure latency during cleanup cycles
    latencies = []
    for _ in range(10):
        await asyncio.sleep(0.6)  # Wait for cleanup cycle
        start = time.perf_counter()
        await pool.get_connection(mock_host)
        latencies.append(time.perf_counter() - start)

    avg_latency = statistics.mean(latencies) * 1000
    max_latency = max(latencies) * 1000

    print("\n[PERF] Cleanup task overhead:")
    print(f"  Avg latency: {avg_latency:.2f}ms")
    print(f"  Max latency: {max_latency:.2f}ms")

    # Cleanup shouldn't block operations
    assert max_latency < 5.0, "Cleanup should not block pool access >5ms"


@pytest.mark.asyncio
async def test_stale_connection_detection(
    mock_host: SSHHost,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Benchmark stale connection detection performance."""
    mock_ssh = MockAsyncSSH(delay=0.01)
    monkeypatch.setattr("scout_mcp.services.pool.asyncssh", mock_ssh)

    pool = ConnectionPool()

    # Create connection
    conn = await pool.get_connection(mock_host)

    # Close it to make stale
    conn.close()

    # Measure stale detection + reconnect
    start = time.perf_counter()
    await pool.get_connection(mock_host)
    elapsed = time.perf_counter() - start

    print(f"\n[PERF] Stale connection detection + reconnect: {elapsed * 1000:.2f}ms")

    # Should detect stale and reconnect
    assert mock_ssh._connection_count == 2, "Should create new connection"
    assert elapsed < 0.05, "Stale detection + reconnect should be <50ms"

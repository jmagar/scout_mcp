"""SSH operation performance benchmarks."""

import asyncio
import statistics
import time

import pytest

from scout_mcp.services.executors import cat_file, ls_dir, run_command, stat_path


class MockSSHResult:
    """Mock SSH command result."""

    def __init__(self, returncode: int, stdout: str, stderr: str = "") -> None:
        """Initialize mock result."""
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class MockSSHConnection:
    """Mock SSH connection for benchmarking."""

    def __init__(self, latency: float = 0.001) -> None:
        """Initialize mock connection."""
        self._latency = latency
        self._command_count = 0

    async def run(self, command: str, check: bool = True) -> MockSSHResult:
        """Mock command execution."""
        self._command_count += 1
        await asyncio.sleep(self._latency)

        # Return different outputs based on command
        if "stat" in command:
            return MockSSHResult(0, "regular file")
        elif "head" in command:
            return MockSSHResult(0, "file contents" * 100)
        elif "ls" in command:
            return MockSSHResult(
                0, "-rw-r--r-- 1 user group 1234 Jan 1 file.txt\n" * 50
            )
        elif "timeout" in command:
            return MockSSHResult(0, "command output")
        else:
            return MockSSHResult(0, "")


@pytest.mark.asyncio
async def test_stat_path_latency() -> None:
    """Benchmark stat_path operation."""
    conn = MockSSHConnection(latency=0.001)

    latencies = []
    for _ in range(100):
        start = time.perf_counter()
        await stat_path(conn, "/test/path")
        latencies.append(time.perf_counter() - start)

    avg = statistics.mean(latencies) * 1000
    p95 = statistics.quantiles(latencies, n=20)[18] * 1000

    print("\n[PERF] stat_path (n=100):")
    print(f"  Avg: {avg:.2f}ms")
    print(f"  P95: {p95:.2f}ms")
    print(f"  Commands executed: {conn._command_count}")


@pytest.mark.asyncio
async def test_cat_file_latency() -> None:
    """Benchmark cat_file operation."""
    conn = MockSSHConnection(latency=0.001)

    latencies = []
    for _ in range(100):
        start = time.perf_counter()
        _, _ = await cat_file(conn, "/test/file.txt", max_size=1048576)
        latencies.append(time.perf_counter() - start)

    avg = statistics.mean(latencies) * 1000
    p95 = statistics.quantiles(latencies, n=20)[18] * 1000

    print("\n[PERF] cat_file (n=100):")
    print(f"  Avg: {avg:.2f}ms")
    print(f"  P95: {p95:.2f}ms")


@pytest.mark.asyncio
async def test_ls_dir_latency() -> None:
    """Benchmark ls_dir operation."""
    conn = MockSSHConnection(latency=0.001)

    latencies = []
    for _ in range(100):
        start = time.perf_counter()
        await ls_dir(conn, "/test/dir")
        latencies.append(time.perf_counter() - start)

    avg = statistics.mean(latencies) * 1000
    p95 = statistics.quantiles(latencies, n=20)[18] * 1000

    print("\n[PERF] ls_dir (n=100):")
    print(f"  Avg: {avg:.2f}ms")
    print(f"  P95: {p95:.2f}ms")


@pytest.mark.asyncio
async def test_run_command_latency() -> None:
    """Benchmark run_command operation."""
    conn = MockSSHConnection(latency=0.001)

    latencies = []
    for _ in range(100):
        start = time.perf_counter()
        await run_command(conn, "/test/dir", "grep pattern file", timeout=30)
        latencies.append(time.perf_counter() - start)

    avg = statistics.mean(latencies) * 1000
    p95 = statistics.quantiles(latencies, n=20)[18] * 1000

    print("\n[PERF] run_command (n=100):")
    print(f"  Avg: {avg:.2f}ms")
    print(f"  P95: {p95:.2f}ms")


@pytest.mark.asyncio
async def test_large_file_transfer() -> None:
    """Benchmark large file transfer (1MB limit)."""

    class LargeFileConnection:
        async def run(self, command: str, check: bool = True) -> MockSSHResult:
            await asyncio.sleep(0.01)  # Simulate network transfer
            # Return 1MB of data
            return MockSSHResult(0, "x" * 1048576)

    conn = LargeFileConnection()

    start = time.perf_counter()
    content, was_truncated = await cat_file(conn, "/large/file.bin", max_size=1048576)
    elapsed = time.perf_counter() - start

    print("\n[PERF] Large file transfer (1MB):")
    print(f"  Time: {elapsed * 1000:.2f}ms")
    print(f"  Size: {len(content)} bytes")
    print(f"  Truncated: {was_truncated}")
    print(f"  Throughput: {len(content) / elapsed / 1024 / 1024:.2f} MB/s")


@pytest.mark.asyncio
async def test_output_processing_overhead() -> None:
    """Measure overhead of output processing (bytes->str conversion)."""

    class BytesConnection:
        async def run(self, command: str, check: bool = True) -> MockSSHResult:
            await asyncio.sleep(0.0)
            # Return bytes instead of str
            result = MockSSHResult(0, "")
            result.stdout = b"output" * 1000  # type: ignore[assignment]
            return result

    conn = BytesConnection()

    start = time.perf_counter()
    _, _ = await cat_file(conn, "/test/file", max_size=1048576)
    elapsed = time.perf_counter() - start

    print("\n[PERF] Output processing (bytes->str):")
    print(f"  Time: {elapsed * 1000:.2f}ms")


@pytest.mark.asyncio
async def test_concurrent_operations() -> None:
    """Benchmark concurrent SSH operations."""
    conn = MockSSHConnection(latency=0.005)

    async def mixed_operations() -> float:
        start = time.perf_counter()
        await asyncio.gather(
            stat_path(conn, "/test/file"),
            cat_file(conn, "/test/file", max_size=1048576),
            ls_dir(conn, "/test/dir"),
            run_command(conn, "/test", "grep pattern file", timeout=30),
        )
        return time.perf_counter() - start

    results = await asyncio.gather(*[mixed_operations() for _ in range(10)])

    avg = statistics.mean(results) * 1000
    throughput = 40 / sum(results)  # 4 ops * 10 iterations

    print("\n[PERF] Concurrent mixed operations (n=10 batches):")
    print(f"  Avg batch time: {avg:.2f}ms")
    print(f"  Throughput: {throughput:.0f} ops/s")

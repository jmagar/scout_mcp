"""End-to-end performance benchmarks."""

import asyncio
import statistics
import time
from pathlib import Path
from typing import Any

import pytest

import scout_mcp.services.state as state_module
from scout_mcp.config import Config
from scout_mcp.tools import scout


class MockSSHResult:
    """Mock SSH result."""

    def __init__(self, returncode: int, stdout: str, stderr: str = "") -> None:
        """Initialize mock result."""
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class MockSSHConnection:
    """Mock SSH connection."""

    def __init__(self, latency: float = 0.005) -> None:
        """Initialize mock connection."""
        self._latency = latency
        self.is_closed = False

    async def run(self, command: str, check: bool = True) -> MockSSHResult:
        """Mock command execution."""
        await asyncio.sleep(self._latency)

        if "stat" in command:
            return MockSSHResult(0, "regular file")
        elif "head" in command:
            return MockSSHResult(0, "file contents\n" * 100)
        elif "ls" in command:
            return MockSSHResult(0, "-rw-r--r-- 1 user group 1234 file.txt\n" * 50)
        else:
            return MockSSHResult(0, "output")

    def close(self) -> None:
        """Close connection."""
        self.is_closed = True


@pytest.fixture
def temp_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    """Create test config."""
    config_path = tmp_path / "ssh_config"
    lines = []
    for i in range(10):
        lines.append(f"Host host-{i}")
        lines.append("    HostName localhost")
        lines.append("    User test")
        lines.append(f"    Port {2200 + i}")
        lines.append("")

    config_path.write_text("\n".join(lines))

    # Create config
    config = Config.from_ssh_config(ssh_config_path=config_path)

    # Mock asyncssh
    async def mock_connect(*args: Any, **kwargs: Any) -> MockSSHConnection:
        await asyncio.sleep(0.005)
        return MockSSHConnection()

    import scout_mcp.services.pool as pool_module

    monkeypatch.setattr(
        pool_module, "asyncssh", type("", (), {"connect": mock_connect})()
    )

    return config


@pytest.mark.asyncio
async def test_full_request_latency_cold(
    temp_config: Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Benchmark full request latency (cold start)."""
    # Reset global state
    state_module._config = temp_config
    state_module._pool = None

    start = time.perf_counter()
    result = await scout("host-0:/test/file.txt")
    elapsed = time.perf_counter() - start

    print("\n[PERF] Full request (cold start):")
    print(f"  Time: {elapsed * 1000:.2f}ms")
    print(f"  Result length: {len(result)} chars")

    # Components: URI parse + config lookup + SSH connect + stat + cat
    assert "file contents" in result


@pytest.mark.asyncio
async def test_full_request_latency_warm(
    temp_config: Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Benchmark full request latency (warm connection)."""
    state_module._config = temp_config
    state_module._pool = None

    # Prime the pool
    await scout("host-0:/test/file.txt")

    # Measure warm request
    latencies = []
    for _ in range(10):
        start = time.perf_counter()
        await scout("host-0:/test/file.txt")
        latencies.append(time.perf_counter() - start)

    avg = statistics.mean(latencies) * 1000
    p95 = (
        statistics.quantiles(latencies, n=20)[18] * 1000
        if len(latencies) >= 20
        else max(latencies) * 1000
    )

    print("\n[PERF] Full request (warm connection, n=10):")
    print(f"  Avg: {avg:.2f}ms")
    print(f"  P95: {p95:.2f}ms")


@pytest.mark.asyncio
async def test_concurrent_requests_same_host(
    temp_config: Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Benchmark concurrent requests to same host."""
    state_module._config = temp_config
    state_module._pool = None

    num_requests = 50

    async def make_request() -> float:
        start = time.perf_counter()
        await scout("host-0:/test/file.txt")
        return time.perf_counter() - start

    start_total = time.perf_counter()
    results = await asyncio.gather(*[make_request() for _ in range(num_requests)])
    elapsed_total = time.perf_counter() - start_total

    avg = statistics.mean(results) * 1000
    p95 = statistics.quantiles(results, n=20)[18] * 1000
    throughput = num_requests / elapsed_total

    print(f"\n[PERF] Concurrent requests same host (n={num_requests}):")
    print(f"  Total time: {elapsed_total * 1000:.2f}ms")
    print(f"  Avg latency: {avg:.2f}ms")
    print(f"  P95 latency: {p95:.2f}ms")
    print(f"  Throughput: {throughput:.0f} req/s")


@pytest.mark.asyncio
async def test_concurrent_requests_different_hosts(
    temp_config: Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Benchmark concurrent requests to different hosts."""
    state_module._config = temp_config
    state_module._pool = None

    num_hosts = 10

    async def make_request(host_id: int) -> float:
        start = time.perf_counter()
        await scout(f"host-{host_id}:/test/file.txt")
        return time.perf_counter() - start

    start_total = time.perf_counter()
    results = await asyncio.gather(*[make_request(i) for i in range(num_hosts)])
    elapsed_total = time.perf_counter() - start_total

    avg = statistics.mean(results) * 1000
    throughput = num_hosts / elapsed_total

    print(f"\n[PERF] Concurrent requests different hosts (n={num_hosts}):")
    print(f"  Total time: {elapsed_total * 1000:.2f}ms")
    print(f"  Avg latency: {avg:.2f}ms")
    print(f"  Throughput: {throughput:.0f} req/s")


@pytest.mark.asyncio
async def test_mixed_operation_workload(
    temp_config: Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Benchmark mixed operation workload."""
    state_module._config = temp_config
    state_module._pool = None

    operations = [
        "host-0:/test/file.txt",  # cat file
        "host-1:/test/dir",  # ls dir
        "host-2:/test/file.log",  # cat file
        "host-3:/etc",  # ls dir
        "hosts",  # list hosts
    ]

    async def run_workload() -> float:
        start = time.perf_counter()
        await asyncio.gather(*[scout(op) for op in operations])
        return time.perf_counter() - start

    results = []
    for _ in range(10):
        results.append(await run_workload())

    avg = statistics.mean(results) * 1000
    throughput = len(operations) * len(results) / sum(results)

    print("\n[PERF] Mixed workload (5 ops x 10 iterations):")
    print(f"  Avg batch time: {avg:.2f}ms")
    print(f"  Throughput: {throughput:.0f} ops/s")


@pytest.mark.asyncio
async def test_hosts_command_performance(
    temp_config: Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Benchmark 'hosts' command performance."""
    state_module._config = temp_config
    state_module._pool = None

    latencies = []
    for _ in range(100):
        start = time.perf_counter()
        await scout("hosts")
        latencies.append(time.perf_counter() - start)

    avg = statistics.mean(latencies) * 1000
    p95 = statistics.quantiles(latencies, n=20)[18] * 1000

    print("\n[PERF] 'hosts' command (n=100):")
    print(f"  Avg: {avg:.2f}ms")
    print(f"  P95: {p95:.2f}ms")

    # Hosts command should be very fast (no SSH)
    assert avg < 5.0, "Hosts command should be <5ms"

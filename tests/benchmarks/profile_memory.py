"""Memory profiling with tracemalloc."""

import asyncio
import tracemalloc

from scout_mcp.models import SSHHost
from scout_mcp.pool import ConnectionPool


class MockSSHConnection:
    """Mock SSH connection."""

    def __init__(self) -> None:
        """Initialize mock connection."""
        self.is_closed = False
        self._buffer = b"x" * 1024  # 1KB buffer

    async def run(self, command: str, check: bool = True) -> object:
        """Mock command execution."""
        await asyncio.sleep(0.001)
        return type(
            "Result", (), {"returncode": 0, "stdout": "output" * 100, "stderr": ""}
        )()

    def close(self) -> None:
        """Close connection."""
        self.is_closed = True


async def mock_connect(*args, **kwargs) -> MockSSHConnection:  # type: ignore[no-untyped-def]
    """Mock SSH connect."""
    await asyncio.sleep(0.001)
    return MockSSHConnection()


async def profile_memory() -> None:
    """Profile memory usage."""
    # Monkey patch asyncssh
    import mcp_cat.pool

    mcp_cat.pool.asyncssh = type("", (), {"connect": mock_connect})()  # type: ignore[attr-defined]

    tracemalloc.start()

    # Baseline
    snapshot1 = tracemalloc.take_snapshot()

    # Create pool
    pool = ConnectionPool()
    snapshot2 = tracemalloc.take_snapshot()

    # Create 100 connections
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

    snapshot3 = tracemalloc.take_snapshot()

    # Reuse connections 1000 times
    for _ in range(1000):
        await pool.get_connection(hosts[0])

    snapshot4 = tracemalloc.take_snapshot()

    # Analyze differences
    print("\n" + "=" * 80)
    print("MEMORY USAGE ANALYSIS")
    print("=" * 80)

    print("\n### Pool Creation ###")
    stats = snapshot2.compare_to(snapshot1, "lineno")
    for stat in stats[:10]:
        print(stat)

    print("\n### After 100 Connections ###")
    stats = snapshot3.compare_to(snapshot2, "lineno")
    for stat in stats[:10]:
        print(stat)

    print("\n### After 1000 Reuses ###")
    stats = snapshot4.compare_to(snapshot3, "lineno")
    for stat in stats[:10]:
        print(stat)

    # Top consumers
    print("\n### Top Memory Consumers (Final) ###")
    top_stats = snapshot4.statistics("lineno")
    for stat in top_stats[:20]:
        print(stat)

    # Summary
    current, peak = tracemalloc.get_traced_memory()
    print("\n### Summary ###")
    print(f"Current memory: {current / 1024 / 1024:.2f} MB")
    print(f"Peak memory: {peak / 1024 / 1024:.2f} MB")

    tracemalloc.stop()


def main() -> None:
    """Run memory profiling."""
    asyncio.run(profile_memory())


if __name__ == "__main__":
    main()

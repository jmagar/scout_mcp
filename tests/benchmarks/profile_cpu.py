"""CPU profiling with cProfile and analysis."""

import asyncio
import cProfile
import pstats
from io import StringIO
from pathlib import Path

from scout_mcp.models import SSHHost
from scout_mcp.pool import ConnectionPool


class MockSSHConnection:
    """Mock SSH connection."""

    def __init__(self) -> None:
        """Initialize mock connection."""
        self.is_closed = False

    async def run(self, command: str, check: bool = True) -> object:
        """Mock command execution."""
        await asyncio.sleep(0.001)
        return type("Result", (), {"returncode": 0, "stdout": "output", "stderr": ""})()

    def close(self) -> None:
        """Close connection."""
        self.is_closed = True


async def mock_connect(*args, **kwargs) -> MockSSHConnection:  # type: ignore[no-untyped-def]
    """Mock SSH connect."""
    await asyncio.sleep(0.005)
    return MockSSHConnection()


async def profile_connection_pool() -> None:
    """Profile connection pool operations."""
    # Monkey patch asyncssh
    import mcp_cat.pool

    mcp_cat.pool.asyncssh = type("", (), {"connect": mock_connect})()  # type: ignore[attr-defined]

    pool = ConnectionPool()
    hosts = [
        SSHHost(
            name=f"host-{i}",
            hostname="localhost",
            user="test",
            port=22,
        )
        for i in range(10)
    ]

    # Profile concurrent connections
    await asyncio.gather(*[pool.get_connection(host) for host in hosts])

    # Profile warm connections
    for _ in range(100):
        await pool.get_connection(hosts[0])


def main() -> None:
    """Run CPU profiling."""
    profiler = cProfile.Profile()
    profiler.enable()

    asyncio.run(profile_connection_pool())

    profiler.disable()

    # Print stats
    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.strip_dirs()
    stats.sort_stats("cumulative")

    print("\n" + "=" * 80)
    print("TOP 30 FUNCTIONS BY CUMULATIVE TIME")
    print("=" * 80)
    stats.print_stats(30)

    print("\n" + "=" * 80)
    print("TOP 20 FUNCTIONS BY INTERNAL TIME")
    print("=" * 80)
    stats.sort_stats("time")
    stats.print_stats(20)

    print("\n" + "=" * 80)
    print("CALL COUNTS (TOP 20)")
    print("=" * 80)
    stats.sort_stats("calls")
    stats.print_stats(20)

    # Save to file
    output_file = Path(".cache/cpu_profile.txt")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        stats.stream = f
        stats.sort_stats("cumulative")
        stats.print_stats()

    print(f"\nFull profile saved to: {output_file}")


if __name__ == "__main__":
    main()

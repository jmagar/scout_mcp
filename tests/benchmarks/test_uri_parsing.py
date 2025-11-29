"""URI parsing performance benchmarks."""

import contextlib
import statistics
import time

from scout_mcp.utils.parser import parse_target


def test_uri_parsing_latency() -> None:
    """Benchmark URI parsing performance."""
    test_uris = [
        "host:/path/to/file",
        "server:/var/log/app.log",
        "db:/etc/postgresql/postgresql.conf",
        "web:/var/www/html/index.html",
        "api:/opt/app/config.json",
    ]

    latencies = []
    for _ in range(1000):
        for uri in test_uris:
            start = time.perf_counter()
            parse_target(uri)
            latencies.append(time.perf_counter() - start)

    avg = statistics.mean(latencies) * 1000
    p95 = statistics.quantiles(latencies, n=20)[18] * 1000
    p99 = statistics.quantiles(latencies, n=100)[98] * 1000

    print("\n[PERF] URI parsing (n=5000):")
    print(f"  Avg: {avg:.4f}ms")
    print(f"  P95: {p95:.4f}ms")
    print(f"  P99: {p99:.4f}ms")

    # URI parsing should be <0.01ms
    assert avg < 0.01, "URI parsing should be <0.01ms"


def test_hosts_command_parsing() -> None:
    """Benchmark 'hosts' command parsing."""
    latencies = []
    for _ in range(1000):
        start = time.perf_counter()
        parse_target("hosts")
        latencies.append(time.perf_counter() - start)

    avg = statistics.mean(latencies) * 1000

    print("\n[PERF] 'hosts' command parsing (n=1000):")
    print(f"  Avg: {avg:.4f}ms")

    assert avg < 0.01


def test_long_path_parsing() -> None:
    """Benchmark parsing of long paths."""
    long_path = "host:" + "/very/long/path" * 20

    latencies = []
    for _ in range(1000):
        start = time.perf_counter()
        parse_target(long_path)
        latencies.append(time.perf_counter() - start)

    avg = statistics.mean(latencies) * 1000

    print("\n[PERF] Long path parsing (n=1000):")
    print(f"  Path length: {len(long_path)} chars")
    print(f"  Avg: {avg:.4f}ms")


def test_error_case_performance() -> None:
    """Benchmark error path (invalid URI)."""
    latencies = []
    for _ in range(1000):
        start = time.perf_counter()
        with contextlib.suppress(ValueError):
            parse_target("invalid-uri")
        latencies.append(time.perf_counter() - start)

    avg = statistics.mean(latencies) * 1000

    print("\n[PERF] Error case (invalid URI, n=1000):")
    print(f"  Avg: {avg:.4f}ms")

    # Error path should not be significantly slower
    assert avg < 0.01

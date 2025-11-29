"""Configuration parsing performance benchmarks."""

import statistics
import time
from pathlib import Path

import pytest

from scout_mcp.config import Config


@pytest.fixture
def temp_ssh_config(tmp_path: Path) -> Path:
    """Create temporary SSH config file."""
    config_path = tmp_path / "ssh_config"

    # Generate config with 100 hosts
    lines = []
    for i in range(100):
        lines.append(f"Host host-{i}")
        lines.append(f"    HostName 192.168.1.{i}")
        lines.append(f"    User user{i}")
        lines.append(f"    Port {2200 + i}")
        lines.append(f"    IdentityFile ~/.ssh/id_{i}")
        lines.append("")

    config_path.write_text("\n".join(lines))
    return config_path


@pytest.fixture
def large_ssh_config(tmp_path: Path) -> Path:
    """Create large SSH config file (1000 hosts)."""
    config_path = tmp_path / "ssh_config_large"

    lines = []
    for i in range(1000):
        lines.append(f"Host host-{i}")
        lines.append(f"    HostName server-{i}.example.com")
        lines.append("    User deploy")
        lines.append("    Port 22")
        lines.append("")

    config_path.write_text("\n".join(lines))
    return config_path


def test_ssh_config_parsing_cold(temp_ssh_config: Path) -> None:
    """Benchmark cold SSH config parsing."""
    config = Config(ssh_config_path=temp_ssh_config)

    start = time.perf_counter()
    hosts = config.get_hosts()
    elapsed = time.perf_counter() - start

    print("\n[PERF] SSH config parsing (100 hosts, cold):")
    print(f"  Time: {elapsed * 1000:.2f}ms")
    print(f"  Hosts parsed: {len(hosts)}")
    print(f"  Throughput: {len(hosts) / elapsed:.0f} hosts/s")

    assert len(hosts) == 100


def test_ssh_config_parsing_cached(temp_ssh_config: Path) -> None:
    """Benchmark cached SSH config access."""
    config = Config(ssh_config_path=temp_ssh_config)

    # Prime the cache
    config.get_hosts()

    # Measure cached access
    latencies = []
    for _ in range(100):
        start = time.perf_counter()
        config.get_hosts()
        latencies.append(time.perf_counter() - start)

    avg = statistics.mean(latencies) * 1000
    p95 = statistics.quantiles(latencies, n=20)[18] * 1000

    print("\n[PERF] SSH config access (cached, n=100):")
    print(f"  Avg: {avg:.4f}ms")
    print(f"  P95: {p95:.4f}ms")

    # Cached access should be <1ms
    assert avg < 1.0, "Cached access should be <1ms"


def test_large_ssh_config_parsing(large_ssh_config: Path) -> None:
    """Benchmark large SSH config parsing (1000 hosts)."""
    config = Config(ssh_config_path=large_ssh_config)

    start = time.perf_counter()
    hosts = config.get_hosts()
    elapsed = time.perf_counter() - start

    print("\n[PERF] SSH config parsing (1000 hosts):")
    print(f"  Time: {elapsed * 1000:.2f}ms")
    print(f"  Hosts parsed: {len(hosts)}")
    print(f"  Throughput: {len(hosts) / elapsed:.0f} hosts/s")

    assert len(hosts) == 1000


def test_host_lookup_performance(temp_ssh_config: Path) -> None:
    """Benchmark individual host lookup."""
    config = Config(ssh_config_path=temp_ssh_config)

    # Prime the cache
    config.get_hosts()

    # Measure individual lookups
    latencies = []
    for i in range(100):
        start = time.perf_counter()
        config.get_host(f"host-{i % 10}")
        latencies.append(time.perf_counter() - start)

    avg = statistics.mean(latencies) * 1000
    p95 = statistics.quantiles(latencies, n=20)[18] * 1000

    print("\n[PERF] Individual host lookup (n=100):")
    print(f"  Avg: {avg:.4f}ms")
    print(f"  P95: {p95:.4f}ms")


def test_allowlist_filtering_performance(temp_ssh_config: Path) -> None:
    """Benchmark allowlist filtering."""
    config = Config(
        ssh_config_path=temp_ssh_config,
        allowlist=["host-1*", "host-2*"],
    )

    start = time.perf_counter()
    hosts = config.get_hosts()
    elapsed = time.perf_counter() - start

    print("\n[PERF] Allowlist filtering (100 hosts):")
    print(f"  Time: {elapsed * 1000:.2f}ms")
    print(f"  Filtered to: {len(hosts)} hosts")


def test_blocklist_filtering_performance(temp_ssh_config: Path) -> None:
    """Benchmark blocklist filtering."""
    config = Config(
        ssh_config_path=temp_ssh_config,
        blocklist=["host-9*"],
    )

    start = time.perf_counter()
    hosts = config.get_hosts()
    elapsed = time.perf_counter() - start

    print("\n[PERF] Blocklist filtering (100 hosts):")
    print(f"  Time: {elapsed * 1000:.2f}ms")
    print(f"  Filtered to: {len(hosts)} hosts")


def test_regex_parsing_overhead(temp_ssh_config: Path) -> None:
    """Measure regex parsing overhead in config parsing."""
    import re

    config_text = temp_ssh_config.read_text()

    # Measure raw regex matching
    start = time.perf_counter()
    host_matches = list(re.finditer(r"^Host\s+(\S+)", config_text, re.MULTILINE))
    regex_time = time.perf_counter() - start

    # Measure full parsing
    config = Config(ssh_config_path=temp_ssh_config)
    start = time.perf_counter()
    config.get_hosts()
    total_time = time.perf_counter() - start

    print("\n[PERF] Regex parsing overhead:")
    print(f"  Regex matching: {regex_time * 1000:.2f}ms")
    print(f"  Total parsing: {total_time * 1000:.2f}ms")
    print(f"  Overhead: {(total_time - regex_time) * 1000:.2f}ms")
    print(f"  Host matches: {len(host_matches)}")

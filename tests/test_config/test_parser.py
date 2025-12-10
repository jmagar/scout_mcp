"""Tests for SSHConfigParser."""

from pathlib import Path

import pytest

from scout_mcp.config.parser import SSHConfigParser
from scout_mcp.models import SSHHost


@pytest.fixture
def sample_ssh_config(tmp_path: Path) -> Path:
    """Create sample SSH config file."""
    config = tmp_path / "ssh_config"
    config.write_text("""
Host test-host
    HostName 192.168.1.100
    User admin
    Port 2222
    IdentityFile ~/.ssh/test_key

Host *
    User root
""")
    return config


def test_parse_ssh_config(sample_ssh_config: Path) -> None:
    """Verify parser extracts hosts from SSH config."""
    parser = SSHConfigParser(sample_ssh_config)
    hosts = parser.parse()

    assert "test-host" in hosts
    assert hosts["test-host"].hostname == "192.168.1.100"
    assert hosts["test-host"].user == "admin"
    assert hosts["test-host"].port == 2222


def test_parse_respects_allowlist(sample_ssh_config: Path) -> None:
    """Verify parser filters by allowlist."""
    parser = SSHConfigParser(
        sample_ssh_config,
        allowlist=["test-host"],
    )
    hosts = parser.parse()

    assert len(hosts) == 1
    assert "test-host" in hosts


def test_parse_respects_blocklist(tmp_path: Path) -> None:
    """Verify parser filters by blocklist."""
    ssh_config = tmp_path / "ssh_config"
    ssh_config.write_text("""
Host allowed
    HostName 192.168.1.1
    User admin

Host blocked
    HostName 192.168.1.2
    User root
""")
    parser = SSHConfigParser(
        ssh_config,
        blocklist=["blocked"],
    )
    hosts = parser.parse()

    assert "allowed" in hosts
    assert "blocked" not in hosts


def test_parse_missing_config_returns_empty(tmp_path: Path) -> None:
    """Parser returns empty dict for missing config file."""
    parser = SSHConfigParser(tmp_path / "nonexistent")
    hosts = parser.parse()

    assert len(hosts) == 0


def test_parse_empty_config_returns_empty(tmp_path: Path) -> None:
    """Parser returns empty dict for empty config file."""
    ssh_config = tmp_path / "ssh_config"
    ssh_config.write_text("")
    parser = SSHConfigParser(ssh_config)
    hosts = parser.parse()

    assert len(hosts) == 0


def test_parse_skips_wildcard_hosts(tmp_path: Path) -> None:
    """Parser skips Host * directives."""
    ssh_config = tmp_path / "ssh_config"
    ssh_config.write_text("""
Host *
    User root

Host real-host
    HostName 192.168.1.1
    User admin
""")
    parser = SSHConfigParser(ssh_config)
    hosts = parser.parse()

    assert "*" not in hosts
    assert "real-host" in hosts


def test_parse_expands_tilde_in_identity_file(tmp_path: Path) -> None:
    """Parser expands ~ in IdentityFile paths."""
    ssh_config = tmp_path / "ssh_config"
    ssh_config.write_text("""
Host test
    HostName 192.168.1.1
    User admin
    IdentityFile ~/.ssh/id_rsa
""")
    parser = SSHConfigParser(ssh_config)
    hosts = parser.parse()

    assert "test" in hosts
    # Identity file should be expanded
    assert hosts["test"].identity_file is not None
    assert not hosts["test"].identity_file.startswith("~")


def test_parse_handles_missing_hostname(tmp_path: Path) -> None:
    """Parser skips hosts without HostName."""
    ssh_config = tmp_path / "ssh_config"
    ssh_config.write_text("""
Host incomplete
    User admin

Host complete
    HostName 192.168.1.1
    User admin
""")
    parser = SSHConfigParser(ssh_config)
    hosts = parser.parse()

    assert "incomplete" not in hosts
    assert "complete" in hosts


def test_parse_defaults_to_home_ssh_config() -> None:
    """Parser defaults to ~/.ssh/config when no path provided."""
    parser = SSHConfigParser()
    expected_path = Path.home() / ".ssh" / "config"
    assert parser.config_path == expected_path

"""Tests for configuration module."""

import pytest
from pathlib import Path
from mcp_cat.config import Config, SSHHost


def test_parse_ssh_config_extracts_hosts(tmp_path: Path) -> None:
    """Parse SSH config and extract host definitions."""
    ssh_config = tmp_path / "config"
    ssh_config.write_text("""
Host dookie
    HostName 100.122.19.93
    User jmagar
    IdentityFile ~/.ssh/id_ed25519

Host tootie
    HostName 100.120.242.29
    User root
    Port 29229
""")

    config = Config(ssh_config_path=ssh_config)
    hosts = config.get_hosts()

    assert len(hosts) == 2
    assert hosts["dookie"].hostname == "100.122.19.93"
    assert hosts["dookie"].user == "jmagar"
    assert hosts["dookie"].port == 22  # default
    assert hosts["tootie"].port == 29229


def test_allowlist_filters_hosts(tmp_path: Path) -> None:
    """Allowlist restricts which hosts are available."""
    ssh_config = tmp_path / "config"
    ssh_config.write_text("""
Host dookie
    HostName 100.122.19.93
    User jmagar

Host tootie
    HostName 100.120.242.29
    User root

Host production
    HostName 10.0.0.1
    User deploy
""")

    config = Config(
        ssh_config_path=ssh_config,
        allowlist=["dookie", "tootie"]
    )
    hosts = config.get_hosts()

    assert "dookie" in hosts
    assert "tootie" in hosts
    assert "production" not in hosts


def test_blocklist_filters_hosts(tmp_path: Path) -> None:
    """Blocklist excludes specific hosts."""
    ssh_config = tmp_path / "config"
    ssh_config.write_text("""
Host dookie
    HostName 100.122.19.93
    User jmagar

Host production
    HostName 10.0.0.1
    User deploy
""")

    config = Config(
        ssh_config_path=ssh_config,
        blocklist=["production"]
    )
    hosts = config.get_hosts()

    assert "dookie" in hosts
    assert "production" not in hosts


def test_get_host_returns_none_for_unknown() -> None:
    """get_host returns None for unknown host."""
    config = Config()
    assert config.get_host("nonexistent") is None

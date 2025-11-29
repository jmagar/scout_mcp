"""Tests for configuration module."""

from pathlib import Path

from scout_mcp.config import Config


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

    config = Config(ssh_config_path=ssh_config, allowlist=["dookie", "tootie"])
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

    config = Config(ssh_config_path=ssh_config, blocklist=["production"])
    hosts = config.get_hosts()

    assert "dookie" in hosts
    assert "production" not in hosts


def test_get_host_returns_none_for_unknown() -> None:
    """get_host returns None for unknown host."""
    config = Config()
    assert config.get_host("nonexistent") is None


def test_empty_ssh_config(tmp_path: Path) -> None:
    """Empty SSH config file returns no hosts."""
    ssh_config = tmp_path / "config"
    ssh_config.write_text("")

    config = Config(ssh_config_path=ssh_config)
    hosts = config.get_hosts()

    assert len(hosts) == 0


def test_ssh_config_with_comments_only(tmp_path: Path) -> None:
    """SSH config with only comments returns no hosts."""
    ssh_config = tmp_path / "config"
    ssh_config.write_text("""
# This is a comment
# Another comment

# Yet another comment
""")

    config = Config(ssh_config_path=ssh_config)
    hosts = config.get_hosts()

    assert len(hosts) == 0


def test_host_without_hostname_is_skipped(tmp_path: Path) -> None:
    """Host without HostName directive is skipped."""
    ssh_config = tmp_path / "config"
    ssh_config.write_text("""
Host incomplete
    User jmagar
    Port 22

Host complete
    HostName 192.168.1.1
    User admin
""")

    config = Config(ssh_config_path=ssh_config)
    hosts = config.get_hosts()

    assert len(hosts) == 1
    assert "incomplete" not in hosts
    assert "complete" in hosts
    assert hosts["complete"].hostname == "192.168.1.1"


def test_invalid_port_defaults_to_22(tmp_path: Path) -> None:
    """Invalid port number defaults to 22."""
    ssh_config = tmp_path / "config"
    ssh_config.write_text("""
Host badport
    HostName 192.168.1.1
    User admin
    Port invalid

Host stringport
    HostName 192.168.1.2
    User admin
    Port abc123
""")

    config = Config(ssh_config_path=ssh_config)
    hosts = config.get_hosts()

    assert len(hosts) == 2
    assert hosts["badport"].port == 22
    assert hosts["stringport"].port == 22


def test_unreadable_config_file_treated_as_empty(tmp_path: Path) -> None:
    """Unreadable config file is treated as empty."""
    ssh_config = tmp_path / "config"
    ssh_config.write_text("Host test\n    HostName 192.168.1.1")
    # Make file unreadable
    ssh_config.chmod(0o000)

    try:
        config = Config(ssh_config_path=ssh_config)
        hosts = config.get_hosts()
        # Should return empty dict for unreadable file
        assert len(hosts) == 0
    finally:
        # Restore permissions for cleanup
        ssh_config.chmod(0o644)


def test_env_vars_override_defaults(tmp_path: Path, monkeypatch) -> None:
    """Environment variables override default config values."""
    monkeypatch.setenv("MCP_CAT_MAX_FILE_SIZE", "5242880")
    monkeypatch.setenv("MCP_CAT_COMMAND_TIMEOUT", "60")
    monkeypatch.setenv("MCP_CAT_IDLE_TIMEOUT", "120")

    config = Config(ssh_config_path=tmp_path / "nonexistent")

    assert config.max_file_size == 5242880
    assert config.command_timeout == 60
    assert config.idle_timeout == 120


def test_invalid_env_var_uses_default(tmp_path: Path, monkeypatch) -> None:
    """Invalid environment variable values fall back to defaults."""
    monkeypatch.setenv("MCP_CAT_MAX_FILE_SIZE", "not_a_number")

    config = Config(ssh_config_path=tmp_path / "nonexistent")

    assert config.max_file_size == 1_048_576  # default

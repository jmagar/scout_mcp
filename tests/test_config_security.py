"""Security tests for SSH host key verification configuration.

Tests the fail-closed security behavior of known_hosts_path property.
"""

import logging
import os
from pathlib import Path

import pytest

from scout_mcp.config import Config


@pytest.fixture
def temp_ssh_config(tmp_path: Path) -> Path:
    """Create a temporary SSH config file."""
    ssh_config = tmp_path / "config"
    ssh_config.write_text(
        """
Host testhost
    HostName 192.168.1.100
    User testuser
"""
    )
    return ssh_config


@pytest.fixture
def temp_known_hosts(tmp_path: Path) -> Path:
    """Create a temporary known_hosts file."""
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("192.168.1.100 ssh-rsa AAAAB3NzaC1yc2E...\n")
    return known_hosts


def test_missing_known_hosts_raises_error(
    temp_ssh_config: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that missing default known_hosts raises FileNotFoundError."""
    # Create config without known_hosts file
    monkeypatch.setenv("SCOUT_SSH_CONFIG", str(temp_ssh_config))
    # Mock home directory to point to temp directory without known_hosts
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    config = Config.from_env()

    # Accessing known_hosts_path should raise FileNotFoundError
    with pytest.raises(FileNotFoundError) as exc_info:
        _ = config.known_hosts_path

    # Verify error message contains remediation steps
    error_msg = str(exc_info.value)
    assert "SSH host key verification required" in error_msg
    assert "~/.ssh/known_hosts not found" in error_msg
    assert "ssh-keyscan" in error_msg
    assert "SCOUT_KNOWN_HOSTS=none" in error_msg
    assert "SECURITY.md" in error_msg


def test_known_hosts_none_disables_with_warning(
    temp_ssh_config: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that SCOUT_KNOWN_HOSTS=none disables verification with critical warning."""
    monkeypatch.setenv("SCOUT_SSH_CONFIG", str(temp_ssh_config))
    monkeypatch.setenv("SCOUT_KNOWN_HOSTS", "none")

    # Start capturing logs BEFORE creating config
    with caplog.at_level(logging.CRITICAL):
        config = Config.from_env()
        result = config.known_hosts_path

        # Should return None (verification disabled)
        assert result is None

        # Should log critical warning
        assert len(caplog.records) >= 1
        # Filter for the known_hosts warning (ignore other CRITICAL logs)
        security_warnings = [
            r
            for r in caplog.records
            if "DISABLED" in r.message and "SCOUT_KNOWN_HOSTS" in r.message
        ]
        assert len(security_warnings) == 1
        assert security_warnings[0].levelname == "CRITICAL"
        assert "man-in-the-middle" in security_warnings[0].message
        assert "SECURITY.md" in security_warnings[0].message


def test_custom_path_works_when_exists(
    temp_ssh_config: Path, temp_known_hosts: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that custom known_hosts path works when file exists."""
    monkeypatch.setenv("SCOUT_SSH_CONFIG", str(temp_ssh_config))
    monkeypatch.setenv("SCOUT_KNOWN_HOSTS", str(temp_known_hosts))

    config = Config.from_env()
    result = config.known_hosts_path

    # Should return the custom path
    assert result == str(temp_known_hosts)


def test_custom_path_raises_when_missing(
    temp_ssh_config: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that custom known_hosts path raises error when file doesn't exist."""
    nonexistent_path = tmp_path / "nonexistent" / "known_hosts"
    monkeypatch.setenv("SCOUT_SSH_CONFIG", str(temp_ssh_config))
    monkeypatch.setenv("SCOUT_KNOWN_HOSTS", str(nonexistent_path))

    config = Config.from_env()

    # Should raise FileNotFoundError
    with pytest.raises(FileNotFoundError) as exc_info:
        _ = config.known_hosts_path

    # Verify error message contains the custom path
    error_msg = str(exc_info.value)
    assert str(nonexistent_path) in error_msg
    assert "specified known_hosts file not found" in error_msg
    assert "touch" in error_msg
    assert "unset SCOUT_KNOWN_HOSTS" in error_msg


def test_default_path_works_when_exists(
    temp_ssh_config: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that default known_hosts path works when file exists."""
    # Create .ssh/known_hosts in temp directory
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    known_hosts = ssh_dir / "known_hosts"
    known_hosts.write_text("192.168.1.100 ssh-rsa AAAAB3NzaC1yc2E...\n")

    monkeypatch.setenv("SCOUT_SSH_CONFIG", str(temp_ssh_config))
    # Mock home directory to point to temp directory
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    config = Config.from_env()
    result = config.known_hosts_path

    # Should return the default path
    assert result == str(known_hosts)


def test_case_insensitive_none_value(
    temp_ssh_config: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that various case forms of 'none' all disable verification."""
    test_cases = ["NONE", "None", "NoNe", "nOnE"]

    for none_value in test_cases:
        caplog.clear()
        monkeypatch.setenv("SCOUT_SSH_CONFIG", str(temp_ssh_config))
        monkeypatch.setenv("SCOUT_KNOWN_HOSTS", none_value)

        with caplog.at_level(logging.CRITICAL):
            config = Config.from_env()
            result = config.known_hosts_path

            # All should return None and log warning
            assert result is None, f"Failed for value: {none_value}"
            security_warnings = [
                r
                for r in caplog.records
                if "DISABLED" in r.message and "SCOUT_KNOWN_HOSTS" in r.message
            ]
            msg = f"No warning logged for value: {none_value}"
            assert len(security_warnings) >= 1, msg
            assert security_warnings[0].levelname == "CRITICAL"


def test_tilde_expansion_in_custom_path(
    temp_ssh_config: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that tilde expansion works in custom paths."""
    # Create custom known_hosts in temp directory
    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    known_hosts = custom_dir / "known_hosts"
    known_hosts.write_text("192.168.1.100 ssh-rsa AAAAB3NzaC1yc2E...\n")

    # Mock expanduser to return our temp path
    original_expanduser = os.path.expanduser

    def mock_expanduser(path: str) -> str:
        if path.startswith("~/"):
            return str(tmp_path / path[2:])
        return original_expanduser(path)

    monkeypatch.setattr("os.path.expanduser", mock_expanduser)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCOUT_SSH_CONFIG", str(temp_ssh_config))
    monkeypatch.setenv("SCOUT_KNOWN_HOSTS", "~/custom/known_hosts")

    config = Config.from_env()
    result = config.known_hosts_path

    # Should expand tilde and return the path
    assert result == str(known_hosts)


def test_whitespace_stripped_from_env_var(
    temp_ssh_config: Path, temp_known_hosts: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that whitespace is stripped from SCOUT_KNOWN_HOSTS value."""
    monkeypatch.setenv("SCOUT_SSH_CONFIG", str(temp_ssh_config))
    monkeypatch.setenv("SCOUT_KNOWN_HOSTS", f"  {temp_known_hosts}  ")

    config = Config.from_env()
    result = config.known_hosts_path

    # Should strip whitespace and work correctly
    assert result == str(temp_known_hosts)


def test_empty_string_env_var_uses_default(
    temp_ssh_config: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that empty SCOUT_KNOWN_HOSTS falls back to default behavior."""
    # Create default known_hosts
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    known_hosts = ssh_dir / "known_hosts"
    known_hosts.write_text("192.168.1.100 ssh-rsa AAAAB3NzaC1yc2E...\n")

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCOUT_SSH_CONFIG", str(temp_ssh_config))
    monkeypatch.setenv("SCOUT_KNOWN_HOSTS", "")

    config = Config.from_env()
    result = config.known_hosts_path

    # Should use default path
    assert result == str(known_hosts)


def test_property_caching_behavior(
    temp_ssh_config: Path, temp_known_hosts: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that known_hosts_path is evaluated each time (no caching)."""
    monkeypatch.setenv("SCOUT_SSH_CONFIG", str(temp_ssh_config))
    monkeypatch.setenv("SCOUT_KNOWN_HOSTS", str(temp_known_hosts))

    config = Config.from_env()

    # First access
    result1 = config.known_hosts_path
    assert result1 == str(temp_known_hosts)

    # Change environment variable
    monkeypatch.setenv("SCOUT_KNOWN_HOSTS", "none")

    # Second access should reflect the change (no caching)
    result2 = config.known_hosts_path
    assert result2 is None


def test_multiple_config_instances_independent(
    temp_ssh_config: Path, temp_known_hosts: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that multiple Config instances behave independently."""
    monkeypatch.setenv("SCOUT_SSH_CONFIG", str(temp_ssh_config))
    monkeypatch.setenv("SCOUT_KNOWN_HOSTS", str(temp_known_hosts))

    config1 = Config.from_env()
    result1 = config1.known_hosts_path

    # Change environment for second instance
    monkeypatch.setenv("SCOUT_KNOWN_HOSTS", "none")
    config2 = Config.from_env()
    result2 = config2.known_hosts_path

    # Both should reflect their environment at access time
    assert result1 == str(temp_known_hosts)
    assert result2 is None

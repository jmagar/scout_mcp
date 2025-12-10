"""Tests for HostKeyVerifier."""

from pathlib import Path

import pytest

from scout_mcp.config.host_keys import HostKeyVerifier


def test_verifier_uses_default_known_hosts_path() -> None:
    """Verifier defaults to ~/.ssh/known_hosts."""
    # Create the file so it doesn't error
    known_hosts = Path.home() / ".ssh" / "known_hosts"
    known_hosts.parent.mkdir(parents=True, exist_ok=True)
    if not known_hosts.exists():
        known_hosts.touch()
        created = True
    else:
        created = False

    try:
        verifier = HostKeyVerifier()
        assert verifier.get_known_hosts_path() == str(known_hosts)
    finally:
        if created:
            known_hosts.unlink()


def test_verifier_uses_custom_path(tmp_path: Path) -> None:
    """Verifier accepts custom known_hosts path."""
    custom = tmp_path / "my_known_hosts"
    custom.touch()

    verifier = HostKeyVerifier(known_hosts_path=str(custom))
    assert verifier.get_known_hosts_path() == str(custom)


def test_verifier_disabled_with_none() -> None:
    """Verifier can be disabled with 'none' path."""
    verifier = HostKeyVerifier(known_hosts_path="none")
    assert verifier.get_known_hosts_path() is None
    assert not verifier.is_enabled()


def test_verifier_raises_on_missing_file_strict_mode(tmp_path: Path) -> None:
    """Verifier raises if file missing in strict mode."""
    missing = tmp_path / "nonexistent"
    with pytest.raises(FileNotFoundError, match="known_hosts file not found"):
        HostKeyVerifier(known_hosts_path=str(missing), strict_checking=True)


def test_verifier_allows_missing_file_non_strict(tmp_path: Path) -> None:
    """Verifier allows missing file in non-strict mode."""
    missing = tmp_path / "nonexistent"
    verifier = HostKeyVerifier(known_hosts_path=str(missing), strict_checking=False)
    # Should disable verification when file missing in non-strict mode
    assert verifier.get_known_hosts_path() is None


def test_verifier_is_enabled_when_path_set(tmp_path: Path) -> None:
    """Verifier is enabled when path is set."""
    custom = tmp_path / "known_hosts"
    custom.touch()

    verifier = HostKeyVerifier(known_hosts_path=str(custom))
    assert verifier.is_enabled()


def test_verifier_is_disabled_when_path_none() -> None:
    """Verifier is disabled when path is None."""
    verifier = HostKeyVerifier(known_hosts_path="none")
    assert not verifier.is_enabled()


def test_verifier_strict_checking_default_true(tmp_path: Path) -> None:
    """Strict checking defaults to True."""
    custom = tmp_path / "known_hosts"
    custom.touch()

    verifier = HostKeyVerifier(known_hosts_path=str(custom))
    assert verifier.strict_checking is True


def test_verifier_strict_checking_can_be_disabled(tmp_path: Path) -> None:
    """Strict checking can be disabled."""
    custom = tmp_path / "known_hosts"
    custom.touch()

    verifier = HostKeyVerifier(known_hosts_path=str(custom), strict_checking=False)
    assert verifier.strict_checking is False

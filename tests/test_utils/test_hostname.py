"""Tests for hostname detection utilities."""

from scout_mcp.utils.hostname import get_server_hostname, is_localhost_target


def test_get_server_hostname_returns_string():
    """Server hostname should be a non-empty string."""
    hostname = get_server_hostname()
    assert isinstance(hostname, str)
    assert len(hostname) > 0


def test_is_localhost_target_matches_exact_hostname():
    """Should detect when target matches server hostname exactly."""
    server_hostname = get_server_hostname()
    assert is_localhost_target(server_hostname) is True


def test_is_localhost_target_matches_lowercase():
    """Should detect hostname case-insensitively."""
    server_hostname = get_server_hostname()
    assert is_localhost_target(server_hostname.lower()) is True
    assert is_localhost_target(server_hostname.upper()) is True


def test_is_localhost_target_rejects_different_hostname():
    """Should reject hostnames that don't match server."""
    assert is_localhost_target("different-host") is False
    assert is_localhost_target("remote-server") is False


def test_is_localhost_target_handles_fqdn():
    """Should match FQDN if server hostname is FQDN."""
    server_hostname = get_server_hostname()
    # If hostname contains dots, it's FQDN
    if "." in server_hostname:
        short_name = server_hostname.split(".")[0]
        assert is_localhost_target(short_name) is True

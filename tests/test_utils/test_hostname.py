"""Test hostname detection utilities."""

import pytest
from scout_mcp.utils.hostname import get_local_hostname, get_short_hostname


def test_get_local_hostname_returns_string():
    """Test that hostname detection returns a non-empty string."""
    hostname = get_local_hostname()
    assert isinstance(hostname, str)
    assert len(hostname) > 0


def test_get_short_hostname_strips_domain():
    """Test that short hostname removes domain suffix."""
    # Test with FQDN
    short = get_short_hostname("tootie.example.com")
    assert short == "tootie"

    # Test with just hostname
    short = get_short_hostname("tootie")
    assert short == "tootie"

    # Test with empty string
    short = get_short_hostname("")
    assert short == ""


def test_get_local_hostname_cacheable():
    """Test that hostname detection is consistent."""
    hostname1 = get_local_hostname()
    hostname2 = get_local_hostname()
    assert hostname1 == hostname2

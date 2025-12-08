"""Tests for SSHHost model."""

from scout_mcp.models import SSHHost


def test_ssh_host_localhost_override():
    """SSHHost should use localhost when is_localhost=True."""
    host = SSHHost(
        name="tootie",
        hostname="tootie.example.com",
        user="root",
        port=29229,
        is_localhost=True,
    )
    assert host.connection_hostname == "127.0.0.1"
    assert host.connection_port == 22


def test_ssh_host_no_override_when_not_localhost():
    """SSHHost should use original hostname when is_localhost=False."""
    host = SSHHost(
        name="remote",
        hostname="remote.example.com",
        user="root",
        port=29229,
        is_localhost=False,
    )
    assert host.connection_hostname == "remote.example.com"
    assert host.connection_port == 29229


def test_ssh_host_defaults_to_not_localhost():
    """SSHHost should default is_localhost to False."""
    host = SSHHost(
        name="default",
        hostname="default.example.com",
        user="root",
        port=22,
    )
    assert host.is_localhost is False
    assert host.connection_hostname == "default.example.com"

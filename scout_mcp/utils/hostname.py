"""Hostname detection utilities for localhost identification."""

import socket


def get_server_hostname() -> str:
    """Get the hostname of the machine running Scout MCP.

    Returns:
        Hostname string (lowercase for consistent comparison)
    """
    return socket.gethostname().lower()


def is_localhost_target(target_host: str) -> bool:
    """Check if target host is the same as the server host.

    Args:
        target_host: SSH host name to check

    Returns:
        True if target matches server hostname (case-insensitive)
    """
    if not target_host:
        return False

    server_hostname = get_server_hostname()
    target_lower = target_host.lower()

    # Direct match
    if target_lower == server_hostname:
        return True

    # Check if server hostname is FQDN and target is short name
    if "." in server_hostname:
        short_name = server_hostname.split(".")[0]
        if target_lower == short_name:
            return True

    # Check if target is FQDN and server is short name
    if "." in target_lower:
        target_short = target_lower.split(".")[0]
        if target_short == server_hostname:
            return True

    return False

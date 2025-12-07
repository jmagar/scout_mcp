"""Hostname detection utilities."""

import socket


def get_local_hostname() -> str:
    """Get the local machine's hostname.

    Returns:
        Hostname as string (may include domain).

    Examples:
        >>> get_local_hostname()
        'tootie.example.com'
    """
    return socket.gethostname()


def get_short_hostname(hostname: str) -> str:
    """Extract short hostname from FQDN.

    Args:
        hostname: Full hostname (may include domain)

    Returns:
        Short hostname without domain suffix.

    Examples:
        >>> get_short_hostname("tootie.example.com")
        'tootie'
        >>> get_short_hostname("tootie")
        'tootie'
    """
    if not hostname:
        return ""

    return hostname.split(".")[0]

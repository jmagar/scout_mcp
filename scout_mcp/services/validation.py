"""Validation services."""

from fastmcp.exceptions import ResourceError

from scout_mcp.models import SSHHost
from scout_mcp.services.state import get_config


def validate_host(host: str) -> SSHHost:
    """Validate host exists in SSH config.

    Args:
        host: Host name to validate

    Returns:
        SSHHost: Validated host object

    Raises:
        ResourceError: If host not found
    """
    config = get_config()
    ssh_host = config.get_host(host)
    if ssh_host is None:
        available = ", ".join(sorted(config.get_hosts().keys()))
        raise ResourceError(f"Unknown host '{host}'. Available: {available}")
    return ssh_host

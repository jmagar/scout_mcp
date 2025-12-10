"""Validation services."""

from fastmcp.exceptions import ResourceError

from scout_mcp.config import Config
from scout_mcp.models import SSHHost


def validate_host(host: str, config: Config) -> SSHHost:
    """Validate host exists in SSH config.

    Args:
        host: Host name to validate
        config: Config instance to validate against

    Returns:
        SSHHost: Validated host object

    Raises:
        ResourceError: If host not found
    """
    ssh_host = config.get_host(host)
    if ssh_host is None:
        available = ", ".join(sorted(config.get_hosts().keys()))
        raise ResourceError(f"Unknown host '{host}'. Available: {available}")
    return ssh_host

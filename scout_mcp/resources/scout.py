"""Scout resource for reading remote files and directories."""

import logging

from fastmcp.exceptions import ResourceError

from scout_mcp.services import (
    ConnectionError,
    get_config,
    get_connection_with_retry,
)
from scout_mcp.services.executors import cat_file, ls_dir, stat_path

logger = logging.getLogger(__name__)


async def scout_resource(host: str, path: str) -> str:
    """Read remote files or directories via SSH.

    This resource provides read-only access to remote filesystems.
    The host must be configured in ~/.ssh/config.

    Args:
        host: SSH host name from ~/.ssh/config (e.g., "tootie", "squirts")
        path: Remote path to read (e.g., "var/log/app.log", "etc/nginx")

    Returns:
        File contents for files, or ls -la output for directories.

    Examples:
        scout://tootie/var/log/app.log - Read a log file
        scout://squirts/etc/nginx - List nginx config directory
        scout://dookie/home/user/.bashrc - Read user's bashrc
    """
    config = get_config()

    # Validate host exists
    ssh_host = config.get_host(host)
    if ssh_host is None:
        available = ", ".join(sorted(config.get_hosts().keys()))
        raise ResourceError(f"Unknown host '{host}'. Available: {available}")

    # Normalize path - add leading slash if not present
    normalized_path = f"/{path}" if not path.startswith("/") else path

    # Get connection (with one retry on failure)
    try:
        conn = await get_connection_with_retry(ssh_host)
    except ConnectionError as e:
        raise ResourceError(str(e)) from e

    # Determine if path is file or directory
    try:
        path_type = await stat_path(conn, normalized_path)
    except Exception as e:
        raise ResourceError(f"Cannot stat {normalized_path}: {e}") from e

    if path_type is None:
        raise ResourceError(f"Path not found: {normalized_path}")

    # Cat file or list directory
    try:
        if path_type == "file":
            contents, was_truncated = await cat_file(
                conn, normalized_path, config.max_file_size
            )
            if was_truncated:
                contents += f"\n\n[truncated at {config.max_file_size} bytes]"
            return contents
        else:
            # Format directory listing with header
            listing = await ls_dir(conn, normalized_path)
            header = f"# Directory: {host}:{normalized_path}\n\n"
            return header + listing
    except Exception as e:
        raise ResourceError(f"Failed to read {normalized_path}: {e}") from e

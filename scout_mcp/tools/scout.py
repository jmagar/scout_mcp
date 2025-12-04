"""Scout tool for remote file operations via SSH."""

import logging

from scout_mcp.services import get_config
from scout_mcp.tools.handlers import (
    determine_path_type,
    handle_command_execution,
    handle_directory_list,
    handle_file_read,
    handle_hosts_list,
)
from scout_mcp.utils.parser import parse_target

logger = logging.getLogger(__name__)


async def scout(target: str, query: str | None = None, tree: bool = False) -> str:
    """Scout remote files and directories via SSH.

    Args:
        target: Either 'hosts' to list available hosts,
            or 'hostname:/path' to target a path.
        query: Optional shell command to execute
            (e.g., "rg 'pattern'", "find . -name '*.py'").
        tree: If True, show directory tree instead of ls -la.

    Examples:
        scout("hosts") - List available SSH hosts
        scout("dookie:/var/log/app.log") - Cat a file
        scout("tootie:/etc/nginx") - List directory contents
        scout("tootie:/etc/nginx", tree=True) - Show directory tree
        scout("squirts:~/code", "rg 'TODO' -t py") - Search for pattern

    Returns:
        File contents, directory listing, command output, or host list.
    """
    config = get_config()

    # Parse target
    try:
        parsed = parse_target(target)
    except ValueError as e:
        return f"Error: {e}"

    # Handle hosts command
    if parsed.is_hosts_command:
        return await handle_hosts_list()

    # Validate host exists
    ssh_host = config.get_host(parsed.host)  # type: ignore[arg-type]
    if ssh_host is None:
        available = ", ".join(sorted(config.get_hosts().keys()))
        return f"Error: Unknown host '{parsed.host}'. Available: {available}"

    # If query provided, run command
    if query:
        return await handle_command_execution(ssh_host, parsed.path, query)

    # Determine if path is file or directory
    path_type, error = await determine_path_type(ssh_host, parsed.path)
    if error:
        return f"Error: {error}"

    # Handle file or directory
    if path_type == "file":
        return await handle_file_read(ssh_host, parsed.path)
    else:
        return await handle_directory_list(ssh_host, parsed.path, tree)

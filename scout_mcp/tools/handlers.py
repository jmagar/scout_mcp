"""Scout tool handlers for different operations."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from scout_mcp.services import (
    ConnectionError,
    get_config,
    get_connection_with_retry,
)
from scout_mcp.services.executors import (
    beam_transfer,
    cat_file,
    ls_dir,
    run_command,
    stat_path,
    tree_dir,
)
from scout_mcp.utils.ping import check_hosts_online

if TYPE_CHECKING:
    import asyncssh

    from scout_mcp.models import SSHHost

logger = logging.getLogger(__name__)


async def _get_connection(
    ssh_host: "SSHHost",
) -> tuple["asyncssh.SSHClientConnection | None", str | None]:
    """Get connection with retry, returning (connection, error_message).

    Args:
        ssh_host: SSH host configuration

    Returns:
        Tuple of (connection, error_message). If successful, error is None.
        If failed, connection is None.
    """
    try:
        conn = await get_connection_with_retry(ssh_host)
        return conn, None
    except ConnectionError as e:
        return None, str(e)


async def handle_hosts_list() -> str:
    """Handle 'hosts' command - list available SSH hosts with status.

    Returns:
        Formatted host list with online/offline status
    """
    config = get_config()
    hosts = config.get_hosts()

    if not hosts:
        return "No SSH hosts configured."

    # Check online status concurrently
    host_endpoints = {name: (host.hostname, host.port) for name, host in hosts.items()}
    online_status = await check_hosts_online(host_endpoints, timeout=2.0)

    lines = ["Available hosts:"]
    for name, host in sorted(hosts.items()):
        status_icon = "✓" if online_status.get(name) else "✗"
        status_text = "online" if online_status.get(name) else "offline"
        lines.append(
            f"  [{status_icon}] {name} ({status_text}) "
            f"-> {host.user}@{host.hostname}:{host.port}"
        )
    return "\n".join(lines)


async def handle_command_execution(
    ssh_host: "SSHHost",
    path: str,
    command: str,
) -> str:
    """Execute a command on remote host.

    Args:
        ssh_host: SSH host configuration
        path: Working directory for command
        command: Shell command to execute

    Returns:
        Command output or error message
    """
    config = get_config()

    conn, error = await _get_connection(ssh_host)
    if error:
        return f"Error: {error}"

    assert conn is not None  # For mypy - error check above ensures this

    try:
        result = await run_command(
            conn,
            path,
            command,
            timeout=config.command_timeout,
        )

        output_parts = []
        if result.output:
            output_parts.append(result.output)
        if result.error:
            output_parts.append(f"[stderr]\n{result.error}")
        if result.returncode != 0:
            output_parts.append(f"[exit code: {result.returncode}]")

        return "\n".join(output_parts) if output_parts else "(no output)"

    except Exception as e:
        return f"Error: Command failed: {e}"


async def handle_file_read(
    ssh_host: "SSHHost",
    path: str,
) -> str:
    """Read a file from remote host.

    Args:
        ssh_host: SSH host configuration
        path: Path to file

    Returns:
        File contents or error message
    """
    config = get_config()

    conn, error = await _get_connection(ssh_host)
    if error:
        return f"Error: {error}"

    assert conn is not None  # For mypy - error check above ensures this

    try:
        contents, was_truncated = await cat_file(conn, path, config.max_file_size)
        if was_truncated:
            contents += f"\n\n[truncated at {config.max_file_size} bytes]"
        return contents
    except Exception as e:
        return f"Error: {e}"


async def handle_directory_list(
    ssh_host: "SSHHost",
    path: str,
    use_tree: bool = False,
) -> str:
    """List a directory on remote host.

    Args:
        ssh_host: SSH host configuration
        path: Path to directory
        use_tree: If True, show tree view instead of ls

    Returns:
        Directory listing or error message
    """
    conn, error = await _get_connection(ssh_host)
    if error:
        return f"Error: {error}"

    assert conn is not None  # For mypy - error check above ensures this

    try:
        if use_tree:
            return await tree_dir(conn, path)
        else:
            return await ls_dir(conn, path)
    except Exception as e:
        return f"Error: {e}"


async def determine_path_type(
    ssh_host: "SSHHost",
    path: str,
) -> tuple[str | None, str | None]:
    """Determine if path is a file or directory.

    Args:
        ssh_host: SSH host configuration
        path: Path to check

    Returns:
        Tuple of (path_type, error_message)
        path_type is 'file', 'directory', or None
        error_message is set if an error occurred
    """
    conn, error = await _get_connection(ssh_host)
    if error:
        return None, error

    assert conn is not None  # For mypy - error check above ensures this

    try:
        path_type = await stat_path(conn, path)
        if path_type is None:
            return None, f"Path not found: {path}"
        return path_type, None
    except Exception as e:
        return None, f"Cannot stat {path}: {e}"


async def handle_beam_transfer(
    ssh_host: "SSHHost",
    remote_path: str,
    beam_path: str,
) -> str:
    """Handle file transfer (beam) operation.

    Args:
        ssh_host: Target SSH host
        remote_path: Remote file/directory path
        beam_path: Local file/directory path

    Returns:
        Status message describing the transfer result
    """
    # Determine transfer direction
    local_path = Path(beam_path)

    if local_path.exists():
        # Local file exists → Upload (local → remote)
        direction = "upload"
        source = beam_path
        destination = remote_path
    else:
        # Local file doesn't exist → Download (remote → local)
        direction = "download"
        source = remote_path
        destination = beam_path

    try:
        conn = await get_connection_with_retry(ssh_host)
        result = await beam_transfer(conn, source, destination, direction)

        if result.success:
            size_kb = result.bytes_transferred / 1024
            return f"✓ {result.message}\n  Size: {size_kb:.2f} KB"
        else:
            return f"✗ Transfer failed: {result.message}"

    except Exception as e:
        return f"Error: Beam transfer failed: {e}"

"""Scout tool handlers for different operations."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from scout_mcp.services import (
    ConnectionError,
    get_config,
    get_connection_with_retry,
    get_pool,
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

    from scout_mcp.config import Config
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
    pool = get_pool()
    try:
        conn = await get_connection_with_retry(ssh_host, pool)
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

    pool = get_pool()
    try:
        conn = await get_connection_with_retry(ssh_host, pool)
        result = await beam_transfer(conn, source, destination, direction)

        if result.success:
            size_kb = result.bytes_transferred / 1024
            return f"✓ {result.message}\n  Size: {size_kb:.2f} KB"
        else:
            return f"✗ Transfer failed: {result.message}"

    except Exception as e:
        return f"Error: Beam transfer failed: {e}"


async def handle_beam_transfer_remote_to_remote(
    config: "Config",
    beam_source: str,
    beam_target: str,
) -> str:
    """Handle remote-to-remote file transfer.

    Args:
        config: Scout configuration
        beam_source: Source in format "host:/path"
        beam_target: Target in format "host:/path"

    Returns:
        Status message describing transfer result.
    """
    from scout_mcp.services import get_connection_with_retry
    from scout_mcp.services.executors import (
        beam_transfer,
        beam_transfer_remote_to_remote,
    )
    from scout_mcp.utils.hostname import is_localhost_target
    from scout_mcp.utils.parser import parse_target

    # Parse source and target
    try:
        source_parsed = parse_target(beam_source)
        target_parsed = parse_target(beam_target)
    except ValueError as e:
        return f"Error: {e}"

    # Validate both are host:/path format
    if source_parsed.is_hosts_command or source_parsed.host is None:
        return "Error: beam_source must be in format 'host:/path'"

    if target_parsed.is_hosts_command or target_parsed.host is None:
        return "Error: beam_target must be in format 'host:/path'"

    # Get SSH host configs
    source_ssh_host = config.get_host(source_parsed.host)
    if source_ssh_host is None:
        available = ", ".join(sorted(config.get_hosts().keys()))
        return (
            f"Error: Unknown source host '{source_parsed.host}'. "
            f"Available: {available}"
        )

    target_ssh_host = config.get_host(target_parsed.host)
    if target_ssh_host is None:
        available = ", ".join(sorted(config.get_hosts().keys()))
        return (
            f"Error: Unknown target host '{target_parsed.host}'. "
            f"Available: {available}"
        )

    # Determine transfer strategy based on localhost detection
    source_is_local = is_localhost_target(source_parsed.host)
    target_is_local = is_localhost_target(target_parsed.host)

    # Set to None if localhost for optimization
    source_host = None if source_is_local else source_parsed.host
    target_host = None if target_is_local else target_parsed.host

    pool = get_pool()

    try:
        # Case 1: Optimized to local → remote (source is current host)
        if source_host is None and target_host is not None:
            target_conn = await get_connection_with_retry(target_ssh_host, pool)
            result = await beam_transfer(
                target_conn,
                source_parsed.path,  # Local path
                target_parsed.path,  # Remote path
                "upload",
            )

        # Case 2: Optimized to remote → local (target is current host)
        elif source_host is not None and target_host is None:
            source_conn = await get_connection_with_retry(source_ssh_host, pool)
            result = await beam_transfer(
                source_conn,
                source_parsed.path,  # Remote path
                target_parsed.path,  # Local path
                "download",
            )

        # Case 3: Remote → remote (neither is current host)
        elif source_host is not None and target_host is not None:
            source_conn = await get_connection_with_retry(source_ssh_host, pool)
            target_conn = await get_connection_with_retry(target_ssh_host, pool)
            result = await beam_transfer_remote_to_remote(
                source_conn,
                target_conn,
                source_parsed.path,
                target_parsed.path,
            )

        else:
            return "Error: Cannot transfer from local to local"

        # Format result
        if result.success:
            size_kb = result.bytes_transferred / 1024
            return f"✓ {result.message}\n  Size: {size_kb:.2f} KB"
        else:
            return f"✗ Transfer failed: {result.message}"

    except Exception as e:
        return f"Error: Beam transfer failed: {e}"

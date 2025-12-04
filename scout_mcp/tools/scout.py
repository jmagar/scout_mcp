"""Scout tool for remote file operations via SSH."""

import logging
from typing import TYPE_CHECKING

from scout_mcp.services import (
    broadcast_command,
    broadcast_read,
    diff_files,
    diff_with_content,
    find_files,
    get_config,
    get_connection_with_retry,
    get_pool,
)
from scout_mcp.tools.handlers import (
    determine_path_type,
    handle_command_execution,
    handle_directory_list,
    handle_file_read,
    handle_hosts_list,
)
from scout_mcp.utils.parser import parse_target

if TYPE_CHECKING:
    from scout_mcp.models import BroadcastResult

logger = logging.getLogger(__name__)


def _format_broadcast_results(results: list["BroadcastResult"]) -> str:
    """Format broadcast results for display.

    Groups results by success/failure and formats with clear headers.
    """
    lines = []

    for r in results:
        header = f"═══ {r.host}:{r.path} "
        if r.success:
            header += "═" * (60 - len(header))
        else:
            header += "[FAILED] " + "═" * (50 - len(header))

        lines.append(header)

        if r.success:
            lines.append(r.output)
        else:
            lines.append(f"Error: {r.error}")

        lines.append("")  # Blank line separator

    # Summary
    success_count = sum(1 for r in results if r.success)
    lines.append(f"─── {success_count}/{len(results)} hosts succeeded ───")

    return "\n".join(lines)


async def scout(
    target: str = "",
    query: str | None = None,
    tree: bool = False,
    find: str | None = None,
    depth: int = 5,
    diff: str | None = None,
    diff_content: str | None = None,
    targets: list[str] | None = None,
) -> str:
    """Scout remote files and directories via SSH.

    Args:
        target: Either 'hosts' to list available hosts,
            or 'hostname:/path' to target a path.
        targets: List of targets for multi-host broadcast operations.
            When provided, executes on all hosts concurrently.
        query: Optional shell command to execute
            (e.g., "rg 'pattern'", "find . -name '*.py'").
        tree: If True, show directory tree instead of ls -la.
        find: Glob pattern to search for files (e.g., "*.py", "config*").
        depth: Maximum depth for find operations (default: 5).
        diff: Another target to compare against (e.g., "host2:/path").
        diff_content: Expected content to compare file against.

    Examples:
        scout("hosts") - List available SSH hosts
        scout("dookie:/var/log/app.log") - Cat a file
        scout("tootie:/etc/nginx") - List directory contents
        scout("tootie:/etc/nginx", tree=True) - Show directory tree
        scout("squirts:~/code", "rg 'TODO' -t py") - Search for pattern
        scout("host:/path", find="*.py") - Find Python files
        scout("host:/path", find="*.log", depth=2) - Find logs with limited depth
        scout("host1:/etc/nginx.conf", diff="host2:/etc/nginx.conf") - Compare files
        scout("host:/etc/hosts", diff_content="expected content") - Compare
        scout(targets=["web1:/var/log/app.log", "web2:/var/log/app.log"]) - Broadcast
        scout(targets=["host1:/etc", "host2:/etc"], query="ls -la") - Broadcast cmd

    Returns:
        File contents, directory listing, command output, search results,
        diff output, host list, or formatted multi-host results.
    """
    config = get_config()
    pool = get_pool()

    # Handle multi-host broadcast
    if targets:
        # Parse all targets
        parsed_targets: list[tuple[str, str]] = []
        for t in targets:
            try:
                p = parse_target(t)
                if p.is_hosts_command:
                    return "Error: broadcast targets must be 'host:/path', not 'hosts'"
                parsed_targets.append((p.host, p.path))  # type: ignore[arg-type]
            except ValueError as e:
                return f"Error parsing target '{t}': {e}"

        # Execute broadcast
        try:
            if query:
                broadcast_results = await broadcast_command(
                    pool, config, parsed_targets, query, config.command_timeout
                )
            else:
                broadcast_results = await broadcast_read(
                    pool, config, parsed_targets, config.max_file_size
                )

            # Format results
            return _format_broadcast_results(broadcast_results)
        except Exception as e:
            return f"Error: Broadcast operation failed: {e}"

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

    # If find pattern provided, search for files
    if find:
        try:
            conn = await get_connection_with_retry(ssh_host)
            results = await find_files(
                conn,
                parsed.path,
                find,
                max_depth=depth,
            )
            if not results.strip():
                return f"No files matching '{find}' found in {parsed.path}"
            return results
        except Exception as e:
            return f"Error: Find failed: {e}"

    # If diff target provided, compare files
    if diff:
        try:
            # Parse the diff target
            diff_parsed = parse_target(diff)
            if diff_parsed.is_hosts_command:
                return "Error: diff target must be 'host:/path', not 'hosts'"

            # Get connection to second host
            diff_host = config.get_host(diff_parsed.host)  # type: ignore[arg-type]
            if diff_host is None:
                return f"Error: Unknown diff host '{diff_parsed.host}'"

            # Get connections to both hosts
            conn = await get_connection_with_retry(ssh_host)
            diff_conn = await get_connection_with_retry(diff_host)

            diff_output, identical = await diff_files(
                conn,
                parsed.path,
                diff_conn,
                diff_parsed.path,
            )

            if identical:
                return (
                    f"Files are identical:\n"
                    f"  {parsed.host}:{parsed.path}\n"
                    f"  {diff_parsed.host}:{diff_parsed.path}"
                )
            return diff_output

        except Exception as e:
            return f"Error: Diff failed: {e}"

    # If diff_content provided, compare with inline content
    if diff_content:
        try:
            conn = await get_connection_with_retry(ssh_host)
            diff_output, identical = await diff_with_content(
                conn, parsed.path, diff_content
            )

            if identical:
                return f"File matches expected content: {parsed.path}"
            return diff_output

        except Exception as e:
            return f"Error: Diff failed: {e}"

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

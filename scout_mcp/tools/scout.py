"""Scout tool for remote file operations via SSH."""

from scout_mcp.services import get_config, get_pool
from scout_mcp.services.executors import (
    cat_file,
    ls_dir,
    run_command,
    stat_path,
    tree_dir,
)
from scout_mcp.utils.parser import parse_target


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
    pool = get_pool()

    try:
        parsed = parse_target(target)
    except ValueError as e:
        return f"Error: {e}"

    # Handle hosts command
    if parsed.is_hosts_command:
        hosts = config.get_hosts()
        if not hosts:
            return "No SSH hosts configured."

        lines = ["Available hosts:"]
        for name, host in sorted(hosts.items()):
            lines.append(f"  {name} -> {host.user}@{host.hostname}:{host.port}")
        return "\n".join(lines)

    # Validate host
    ssh_host = config.get_host(parsed.host)  # type: ignore[arg-type]
    if ssh_host is None:
        available = ", ".join(sorted(config.get_hosts().keys()))
        return f"Error: Unknown host '{parsed.host}'. Available: {available}"

    # Get connection (with one retry on failure)
    try:
        conn = await pool.get_connection(ssh_host)
    except Exception:
        # Connection failed - clear stale connection and retry once
        try:
            await pool.remove_connection(ssh_host.name)
            conn = await pool.get_connection(ssh_host)
        except Exception as retry_error:
            return f"Error: Cannot connect to {ssh_host.name}: {retry_error}"

    # If query provided, run command
    if query:
        try:
            result = await run_command(
                conn,
                parsed.path,
                query,
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

    # Determine if path is file or directory
    try:
        path_type = await stat_path(conn, parsed.path)
    except Exception as e:
        return f"Error: Cannot stat {parsed.path}: {e}"

    if path_type is None:
        return f"Error: Path not found: {parsed.path}"

    # Cat file or list directory
    try:
        if path_type == "file":
            contents, was_truncated = await cat_file(
                conn, parsed.path, config.max_file_size
            )
            if was_truncated:
                contents += f"\n\n[truncated at {config.max_file_size} bytes]"
            return contents
        else:
            if tree:
                listing = await tree_dir(conn, parsed.path)
            else:
                listing = await ls_dir(conn, parsed.path)
            return listing

    except Exception as e:
        return f"Error: {e}"

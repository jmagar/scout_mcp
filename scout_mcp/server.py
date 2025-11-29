"""Scout MCP FastMCP server."""

from fastmcp import FastMCP

from scout_mcp.config import Config
from scout_mcp.executors import cat_file, ls_dir, run_command, stat_path, tree_dir
from scout_mcp.pool import ConnectionPool
from scout_mcp.scout import parse_target

# Initialize server
mcp = FastMCP("scout_mcp")

# Global state (initialized on startup)
_config: Config | None = None
_pool: ConnectionPool | None = None


def get_config() -> Config:
    """Get or create config."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def get_pool() -> ConnectionPool:
    """Get or create connection pool."""
    global _pool
    if _pool is None:
        config = get_config()
        _pool = ConnectionPool(idle_timeout=config.idle_timeout)
    return _pool


@mcp.tool()
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


def _get_mime_type(path: str) -> str:
    """Infer MIME type from file extension."""
    ext_map = {
        # Config files
        ".conf": "text/plain",
        ".cfg": "text/plain",
        ".ini": "text/plain",
        ".yaml": "text/yaml",
        ".yml": "text/yaml",
        ".toml": "text/plain",
        ".json": "application/json",
        ".xml": "application/xml",
        # Scripts
        ".sh": "text/x-shellscript",
        ".bash": "text/x-shellscript",
        ".zsh": "text/x-shellscript",
        ".py": "text/x-python",
        ".js": "text/javascript",
        ".ts": "text/typescript",
        ".rb": "text/x-ruby",
        ".go": "text/x-go",
        ".rs": "text/x-rust",
        # Web
        ".html": "text/html",
        ".htm": "text/html",
        ".css": "text/css",
        # Docs
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".log": "text/plain",
        ".csv": "text/csv",
    }
    path_lower = path.lower()
    for ext, mime in ext_map.items():
        if path_lower.endswith(ext):
            return mime
    return "text/plain"


@mcp.resource("scout://{host}/{path*}")
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
    from fastmcp.exceptions import ResourceError

    config = get_config()
    pool = get_pool()

    # Validate host exists
    ssh_host = config.get_host(host)
    if ssh_host is None:
        available = ", ".join(sorted(config.get_hosts().keys()))
        raise ResourceError(f"Unknown host '{host}'. Available: {available}")

    # Normalize path - add leading slash if not present
    normalized_path = f"/{path}" if not path.startswith("/") else path

    # Get connection (with one retry on failure)
    try:
        conn = await pool.get_connection(ssh_host)
    except Exception:
        # Connection failed - clear stale connection and retry once
        try:
            await pool.remove_connection(ssh_host.name)
            conn = await pool.get_connection(ssh_host)
        except Exception as retry_error:
            raise ResourceError(
                f"Cannot connect to {host}: {retry_error}"
            ) from retry_error

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


@mcp.resource("hosts://list")
async def list_hosts_resource() -> str:
    """List available SSH hosts with online status.

    Returns:
        Formatted list of available SSH hosts with connectivity status.
    """
    from scout_mcp.ping import check_hosts_online

    config = get_config()
    hosts = config.get_hosts()

    if not hosts:
        return "No SSH hosts configured."

    # Build dict for concurrent checking
    host_endpoints = {name: (host.hostname, host.port) for name, host in hosts.items()}

    # Check all hosts concurrently
    online_status = await check_hosts_online(host_endpoints, timeout=2.0)

    lines = ["Available SSH hosts:", ""]
    for name, host in sorted(hosts.items()):
        status = "online" if online_status.get(name) else "offline"
        status_icon = "\u2713" if online_status.get(name) else "\u2717"
        host_info = f"{host.user}@{host.hostname}:{host.port}"
        lines.append(f"  [{status_icon}] {name} ({status})")
        lines.append(f"      SSH: {host_info}")
        lines.append(f"      Resource: scout://{name}/<path>")
        lines.append("")

    lines.append("Resource URI template: scout://{host}/{path}")
    lines.append("Examples:")
    example_hosts = list(sorted(hosts.keys()))[:2]
    for h in example_hosts:
        lines.append(f"  scout://{h}/etc/hosts")
        lines.append(f"  scout://{h}/var/log")

    return "\n".join(lines)

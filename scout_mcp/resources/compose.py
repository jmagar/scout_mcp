"""Docker Compose resource for reading compose configs and logs from remote hosts."""

from fastmcp.exceptions import ResourceError

from scout_mcp.services import get_config, get_pool
from scout_mcp.services.executors import compose_config, compose_logs, compose_ls


async def compose_list_resource(host: str) -> str:
    """List Docker Compose projects on remote host.

    Args:
        host: SSH host name from ~/.ssh/config

    Returns:
        Formatted list of compose projects.
    """
    config = get_config()
    pool = get_pool()

    # Validate host exists
    ssh_host = config.get_host(host)
    if ssh_host is None:
        available = ", ".join(sorted(config.get_hosts().keys()))
        raise ResourceError(f"Unknown host '{host}'. Available: {available}")

    # Get connection
    try:
        conn = await pool.get_connection(ssh_host)
    except Exception:
        try:
            await pool.remove_connection(ssh_host.name)
            conn = await pool.get_connection(ssh_host)
        except Exception as retry_error:
            raise ResourceError(
                f"Cannot connect to {host}: {retry_error}"
            ) from retry_error

    # List projects
    projects = await compose_ls(conn)

    if not projects:
        return (
            f"# Docker Compose Projects on {host}\n\n"
            "No projects found (or Docker Compose not available)."
        )

    lines = [
        f"# Docker Compose Projects on {host}",
        "=" * 50,
        "",
    ]

    for p in projects:
        status_icon = "●" if "running" in p["status"].lower() else "○"
        lines.append(f"{status_icon} {p['name']}")
        lines.append(f"    Status: {p['status']}")
        lines.append(f"    Config: {p['config_file']}")
        lines.append(f"    View:   {host}://compose/{p['name']}")
        lines.append(f"    Logs:   {host}://compose/{p['name']}/logs")
        lines.append("")

    return "\n".join(lines)


async def compose_file_resource(host: str, project: str) -> str:
    """Read Docker Compose config file for a project.

    Args:
        host: SSH host name from ~/.ssh/config
        project: Compose project name

    Returns:
        Compose file contents.
    """
    config = get_config()
    pool = get_pool()

    # Validate host exists
    ssh_host = config.get_host(host)
    if ssh_host is None:
        available = ", ".join(sorted(config.get_hosts().keys()))
        raise ResourceError(f"Unknown host '{host}'. Available: {available}")

    # Get connection
    try:
        conn = await pool.get_connection(ssh_host)
    except Exception:
        try:
            await pool.remove_connection(ssh_host.name)
            conn = await pool.get_connection(ssh_host)
        except Exception as retry_error:
            raise ResourceError(
                f"Cannot connect to {host}: {retry_error}"
            ) from retry_error

    # Get config
    content, config_path = await compose_config(conn, project)

    if config_path is None:
        raise ResourceError(
            f"Compose project '{project}' not found on {host}. "
            f"Use {host}://compose to see available projects."
        )

    if not content:
        raise ResourceError(f"Cannot read compose file: {config_path}")

    header = f"# Compose: {project}@{host}\n# File: {config_path}\n\n"
    return header + content


async def compose_logs_resource(host: str, project: str) -> str:
    """Read Docker Compose stack logs.

    Args:
        host: SSH host name from ~/.ssh/config
        project: Compose project name

    Returns:
        Stack logs with timestamps.
    """
    config = get_config()
    pool = get_pool()

    # Validate host exists
    ssh_host = config.get_host(host)
    if ssh_host is None:
        available = ", ".join(sorted(config.get_hosts().keys()))
        raise ResourceError(f"Unknown host '{host}'. Available: {available}")

    # Get connection
    try:
        conn = await pool.get_connection(ssh_host)
    except Exception:
        try:
            await pool.remove_connection(ssh_host.name)
            conn = await pool.get_connection(ssh_host)
        except Exception as retry_error:
            raise ResourceError(
                f"Cannot connect to {host}: {retry_error}"
            ) from retry_error

    # Fetch logs
    logs, exists = await compose_logs(conn, project, tail=100, timestamps=True)

    if not exists:
        raise ResourceError(
            f"Compose project '{project}' not found on {host}. "
            f"Use {host}://compose to see available projects."
        )

    if not logs.strip():
        return f"# Compose Logs: {project}@{host}\n\n(no logs available)"

    header = f"# Compose Logs: {project}@{host}\n\n"
    return header + logs

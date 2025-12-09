"""Docker resource for reading container logs from remote hosts."""

from typing import Any

from fastmcp.exceptions import ResourceError

from scout_mcp.services import ConnectionError, get_connection_with_retry
from scout_mcp.services.executors import docker_logs, docker_ps
from scout_mcp.services.validation import validate_host
from scout_mcp.ui import create_log_viewer_ui


async def docker_logs_resource(host: str, container: str) -> str:
    """Read Docker container logs with interactive log viewer UI.

    Args:
        host: SSH host name from ~/.ssh/config
        container: Docker container name

    Returns:
        HTML string with log viewer interface

    Raises:
        ResourceError: If host unknown, connection fails, or container not found.
    """
    # Validate host exists
    ssh_host = validate_host(host)

    # Get connection (with one retry on failure)
    try:
        conn = await get_connection_with_retry(ssh_host)
    except ConnectionError as e:
        raise ResourceError(str(e)) from e

    # Fetch logs
    try:
        logs, exists = await docker_logs(conn, container, tail=100, timestamps=True)
    except RuntimeError as e:
        raise ResourceError(f"Docker error on {host}: {e}") from e

    if not exists:
        raise ResourceError(
            f"Container '{container}' not found on {host}. "
            f"Use {host}://docker/list to see available containers."
        )

    if not logs.strip():
        logs = "(no logs available)"

    # Return interactive log viewer UI instead of plain text
    return await create_log_viewer_ui(
        host,
        f"/docker/{container}/logs",
        logs
    )


async def docker_list_resource(host: str) -> str:
    """List Docker containers on remote host.

    Args:
        host: SSH host name from ~/.ssh/config

    Returns:
        Formatted list of containers with status.
    """
    # Validate host exists
    ssh_host = validate_host(host)

    # Get connection
    try:
        conn = await get_connection_with_retry(ssh_host)
    except ConnectionError as e:
        raise ResourceError(str(e)) from e

    # List containers
    containers = await docker_ps(conn)

    if not containers:
        return (
            f"# Docker Containers on {host}\n\n"
            "No containers found (or Docker not available)."
        )

    lines = [
        f"# Docker Containers on {host}",
        "=" * 50,
        "",
    ]

    for c in containers:
        status_icon = "●" if "Up" in c["status"] else "○"
        lines.append(f"{status_icon} {c['name']}")
        lines.append(f"    Status: {c['status']}")
        lines.append(f"    Image:  {c['image']}")
        lines.append(f"    Logs:   {host}://docker/{c['name']}/logs")
        lines.append("")

    return "\n".join(lines)

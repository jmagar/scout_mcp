"""Syslog resource for reading system logs from remote hosts."""

from typing import Any

from fastmcp.exceptions import ResourceError

from scout_mcp.services import ConnectionError, get_config, get_connection_with_retry
from scout_mcp.services.executors import syslog_read
from scout_mcp.ui import create_log_viewer_ui


async def syslog_resource(host: str, lines: int = 100) -> str:
    """Show system logs with interactive log viewer UI.

    Dynamically detects whether to use journalctl (systemd) or
    /var/log/syslog based on what's available on the host.

    Args:
        host: SSH host name from ~/.ssh/config
        lines: Number of log lines to retrieve (default 100)

    Returns:
        HTML string with log viewer interface
    """
    config = get_config()

    # Validate host exists
    ssh_host = config.get_host(host)
    if ssh_host is None:
        available = ", ".join(sorted(config.get_hosts().keys()))
        raise ResourceError(f"Unknown host '{host}'. Available: {available}")

    # Get connection
    try:
        conn = await get_connection_with_retry(ssh_host)
    except ConnectionError as e:
        raise ResourceError(str(e)) from e

    # Get logs (dynamically detects journalctl vs syslog)
    logs, source = await syslog_read(conn, lines=lines)

    if source == "none":
        logs = (
            "System logs are not available on this host.\n\n"
            "Neither journalctl nor /var/log/syslog is accessible."
        )

    source_desc = "journalctl" if source == "journalctl" else "/var/log/syslog"

    # Return interactive log viewer UI instead of plain text
    return await create_log_viewer_ui(
        host,
        f"/var/log/syslog ({source_desc})",
        logs
    )

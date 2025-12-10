"""Syslog resource plugin for reading system logs from remote hosts."""

from fastmcp.exceptions import ResourceError

from scout_mcp.dependencies import Dependencies
from scout_mcp.resources.plugin import ResourcePlugin
from scout_mcp.services import ConnectionError, get_connection_with_retry
from scout_mcp.services.executors import syslog_read
from scout_mcp.services.validation import validate_host
from scout_mcp.ui import create_log_viewer_ui


async def syslog_resource(host: str, deps: Dependencies, lines: int = 100) -> str:
    """Show system logs with interactive log viewer UI.

    Dynamically detects whether to use journalctl (systemd) or
    /var/log/syslog based on what's available on the host.

    Args:
        host: SSH host name from ~/.ssh/config
        deps: Dependencies container with config and pool
        lines: Number of log lines to retrieve (default 100)

    Returns:
        HTML string with log viewer interface
    """
    # Validate host exists
    ssh_host = validate_host(host, deps.config)

    # Get connection
    try:
        conn = await get_connection_with_retry(ssh_host, deps.pool)
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


class SyslogPlugin(ResourcePlugin):
    """System logs resource.

    URI: {host}://syslog
    """

    def __init__(self, deps: Dependencies):
        """Initialize plugin with dependencies.

        Args:
            deps: Dependencies container with config and pool
        """
        self.deps = deps

    def get_uri_template(self) -> str:
        return "{host}://syslog"

    def get_description(self) -> str:
        return "System logs (last 100 lines)"

    def get_mime_type(self) -> str:
        return "text/html"

    async def handle(self, host: str) -> str:
        """Get system logs for host."""
        return await syslog_resource(host, self.deps)

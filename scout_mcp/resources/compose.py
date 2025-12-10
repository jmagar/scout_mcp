"""Docker Compose resource plugins for reading compose configs and logs."""

from fastmcp.exceptions import ResourceError

from scout_mcp.dependencies import Dependencies
from scout_mcp.resources.plugin import ResourcePlugin
from scout_mcp.services import ConnectionError, get_connection_with_retry
from scout_mcp.services.executors import compose_config, compose_logs, compose_ls
from scout_mcp.services.validation import validate_host
from scout_mcp.ui import create_log_viewer_ui


async def compose_list_resource(host: str, deps: Dependencies) -> str:
    """List Docker Compose projects on remote host.

    Args:
        host: SSH host name from ~/.ssh/config
        deps: Dependencies container with config and pool

    Returns:
        Formatted list of compose projects.
    """
    # Validate host exists
    ssh_host = validate_host(host, deps.config)

    # Get connection
    try:
        conn = await get_connection_with_retry(ssh_host, deps.pool)
    except ConnectionError as e:
        raise ResourceError(str(e)) from e

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


async def compose_file_resource(host: str, project: str, deps: Dependencies) -> str:
    """Read Docker Compose config file for a project.

    Args:
        host: SSH host name from ~/.ssh/config
        project: Compose project name
        deps: Dependencies container with config and pool

    Returns:
        Compose file contents.
    """
    # Validate host exists
    ssh_host = validate_host(host, deps.config)

    # Get connection
    try:
        conn = await get_connection_with_retry(ssh_host, deps.pool)
    except ConnectionError as e:
        raise ResourceError(str(e)) from e

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


async def compose_logs_resource(host: str, project: str, deps: Dependencies) -> str:
    """Read Docker Compose stack logs with interactive log viewer UI.

    Args:
        host: SSH host name from ~/.ssh/config
        project: Compose project name
        deps: Dependencies container with config and pool

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

    # Fetch logs
    logs, exists = await compose_logs(conn, project, tail=100, timestamps=True)

    if not exists:
        raise ResourceError(
            f"Compose project '{project}' not found on {host}. "
            f"Use {host}://compose to see available projects."
        )

    if not logs.strip():
        logs = "(no logs available)"

    # Return interactive log viewer UI instead of plain text
    return await create_log_viewer_ui(
        host,
        f"/compose/{project}/logs",
        logs
    )


class ComposeListPlugin(ResourcePlugin):
    """Docker Compose project list resource.

    URI: {host}://compose
    """

    def __init__(self, deps: Dependencies):
        """Initialize plugin with dependencies.

        Args:
            deps: Dependencies container with config and pool
        """
        self.deps = deps

    def get_uri_template(self) -> str:
        return "{host}://compose"

    def get_description(self) -> str:
        return "List Docker Compose projects"

    async def handle(self, host: str) -> str:
        """List Compose projects on host."""
        return await compose_list_resource(host, self.deps)


class ComposeFilePlugin(ResourcePlugin):
    """Docker Compose config file resource.

    URI: {host}://compose/{project}
    """

    def __init__(self, deps: Dependencies):
        """Initialize plugin with dependencies.

        Args:
            deps: Dependencies container with config and pool
        """
        self.deps = deps

    def get_uri_template(self) -> str:
        return "{host}://compose/{{project}}"

    def get_description(self) -> str:
        return "Docker Compose config file"

    def get_mime_type(self) -> str:
        return "text/yaml"

    async def handle(self, host: str, project: str) -> str:
        """Read Compose config for project on host."""
        return await compose_file_resource(host, project, self.deps)


class ComposeLogsPlugin(ResourcePlugin):
    """Docker Compose project logs resource.

    URI: {host}://compose/{project}/logs
    """

    def __init__(self, deps: Dependencies):
        """Initialize plugin with dependencies.

        Args:
            deps: Dependencies container with config and pool
        """
        self.deps = deps

    def get_uri_template(self) -> str:
        return "{host}://compose/{{project}}/logs"

    def get_description(self) -> str:
        return "Docker Compose project logs (last 100 lines)"

    def get_mime_type(self) -> str:
        return "text/html"

    async def handle(self, host: str, project: str) -> str:
        """Read Compose logs for project on host."""
        return await compose_logs_resource(host, project, self.deps)

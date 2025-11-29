"""Scout MCP FastMCP server.

This is a thin wrapper that wires together the MCP server with tools and resources.
All business logic is delegated to the tools/, resources/, and services/ modules.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP

from scout_mcp.middleware import (
    ErrorHandlingMiddleware,
    LoggingMiddleware,
    TimingMiddleware,
)
from scout_mcp.resources import list_hosts_resource, scout_resource
from scout_mcp.services import get_config
from scout_mcp.tools import scout


async def _read_host_path(host: str, path: str) -> str:
    """Read a file or directory on a remote host.

    Args:
        host: SSH host name
        path: Remote path to read

    Returns:
        File contents or directory listing
    """
    return await scout_resource(host, path)


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Register dynamic host resources at startup.

    Reads SSH hosts from config and registers a resource template
    for each host, enabling URIs like tootie://path/to/file.

    Args:
        server: The FastMCP server instance

    Yields:
        Dict with hosts list
    """
    config = get_config()
    hosts = config.get_hosts()

    for host_name in hosts:

        def make_handler(h: str) -> Any:
            async def handler(path: str) -> str:
                return await _read_host_path(h, path)

            return handler

        # Use the resource decorator to register template
        server.resource(
            uri=f"{host_name}://{{path*}}",
            name=f"{host_name} filesystem",
            description=f"Read files and directories on {host_name}",
            mime_type="text/plain",
        )(make_handler(host_name))

    yield {"hosts": list(hosts.keys())}


def configure_middleware(server: FastMCP) -> None:
    """Configure middleware stack for the server.

    Adds middleware in order: ErrorHandling -> Timing -> Logging

    Environment variables:
        SCOUT_LOG_PAYLOADS: Set to "true" to log request/response payloads
        SCOUT_SLOW_THRESHOLD_MS: Threshold for slow request warnings (default: 1000)
        SCOUT_INCLUDE_TRACEBACK: Set to "true" to include tracebacks in error logs

    Args:
        server: The FastMCP server to configure.
    """
    # Parse environment configuration
    log_payloads = os.getenv("SCOUT_LOG_PAYLOADS", "").lower() == "true"
    slow_threshold = float(os.getenv("SCOUT_SLOW_THRESHOLD_MS", "1000"))
    include_traceback = os.getenv("SCOUT_INCLUDE_TRACEBACK", "").lower() == "true"

    # Add middleware in order (first added = innermost)
    server.add_middleware(ErrorHandlingMiddleware(include_traceback=include_traceback))
    server.add_middleware(TimingMiddleware(slow_threshold_ms=slow_threshold))
    server.add_middleware(LoggingMiddleware(include_payloads=log_payloads))


def create_server() -> FastMCP:
    """Create and configure the MCP server with all middleware and resources.

    Returns:
        Configured FastMCP server instance
    """
    server = FastMCP(
        "scout_mcp",
        lifespan=app_lifespan,
    )

    configure_middleware(server)

    # Register tools
    server.tool()(scout)

    # Register resources
    server.resource("scout://{host}/{path*}")(scout_resource)
    server.resource("hosts://list")(list_hosts_resource)

    return server


# Default server instance
mcp = create_server()

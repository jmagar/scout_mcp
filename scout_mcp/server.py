"""Scout MCP FastMCP server.

This is a thin wrapper that wires together the MCP server with tools and resources.
All business logic is delegated to the tools/, resources/, and services/ modules.
"""

import os

from fastmcp import FastMCP

from scout_mcp.middleware import (
    ErrorHandlingMiddleware,
    LoggingMiddleware,
    TimingMiddleware,
)
from scout_mcp.resources import list_hosts_resource, scout_resource
from scout_mcp.tools import scout


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


# Initialize server
mcp = FastMCP("scout_mcp")

# Configure middleware stack
configure_middleware(mcp)

# Register tools
mcp.tool()(scout)

# Register resources
mcp.resource("scout://{host}/{path*}")(scout_resource)
mcp.resource("hosts://list")(list_hosts_resource)

"""MCP resources for Scout MCP."""

from scout_mcp.resources.hosts import list_hosts_resource
from scout_mcp.resources.scout import scout_resource

__all__ = ["list_hosts_resource", "scout_resource"]

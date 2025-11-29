"""Data models for Scout MCP."""

from scout_mcp.models.command import CommandResult
from scout_mcp.models.ssh import PooledConnection, SSHHost
from scout_mcp.models.target import ScoutTarget

__all__ = [
    "CommandResult",
    "PooledConnection",
    "ScoutTarget",
    "SSHHost",
]

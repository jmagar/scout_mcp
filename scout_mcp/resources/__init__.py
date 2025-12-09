"""MCP resources for Scout MCP."""

from scout_mcp.resources.compose import (
    compose_file_resource,
    compose_list_resource,
    compose_logs_resource,
)
from scout_mcp.resources.docker import docker_list_resource, docker_logs_resource
from scout_mcp.resources.hosts import list_hosts_resource
from scout_mcp.resources.scout import scout_resource
from scout_mcp.resources.syslog import syslog_resource
from scout_mcp.resources.zfs import (
    zfs_datasets_resource,
    zfs_overview_resource,
    zfs_pool_resource,
    zfs_snapshots_resource,
)

__all__ = [
    "compose_file_resource",
    "compose_list_resource",
    "compose_logs_resource",
    "docker_list_resource",
    "docker_logs_resource",
    "list_hosts_resource",
    "scout_resource",
    "syslog_resource",
    "zfs_datasets_resource",
    "zfs_overview_resource",
    "zfs_pool_resource",
    "zfs_snapshots_resource",
]

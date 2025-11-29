"""Scout MCP FastMCP server.

This is a thin wrapper that wires together the MCP server with tools and resources.
All business logic is delegated to the tools/, resources/, and services/ modules.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from scout_mcp.middleware import (
    ErrorHandlingMiddleware,
    LoggingMiddleware,
    TimingMiddleware,
)
from scout_mcp.resources import (
    compose_file_resource,
    compose_list_resource,
    compose_logs_resource,
    docker_list_resource,
    docker_logs_resource,
    list_hosts_resource,
    scout_resource,
    syslog_resource,
    zfs_datasets_resource,
    zfs_overview_resource,
    zfs_pool_resource,
    zfs_snapshots_resource,
)
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


async def _read_docker_logs(host: str, container: str) -> str:
    """Read Docker container logs on a remote host.

    Args:
        host: SSH host name
        container: Docker container name

    Returns:
        Container logs
    """
    return await docker_logs_resource(host, container)


async def _list_docker_containers(host: str) -> str:
    """List Docker containers on a remote host.

    Args:
        host: SSH host name

    Returns:
        Formatted container list
    """
    return await docker_list_resource(host)


async def _list_compose_projects(host: str) -> str:
    """List Docker Compose projects on a remote host."""
    return await compose_list_resource(host)


async def _read_compose_file(host: str, project: str) -> str:
    """Read Docker Compose config file."""
    return await compose_file_resource(host, project)


async def _read_compose_logs(host: str, project: str) -> str:
    """Read Docker Compose stack logs."""
    return await compose_logs_resource(host, project)


async def _zfs_overview(host: str) -> str:
    """Get ZFS overview for a remote host."""
    return await zfs_overview_resource(host)


async def _zfs_pool(host: str, pool: str) -> str:
    """Get ZFS pool status."""
    return await zfs_pool_resource(host, pool)


async def _zfs_datasets(host: str, pool: str) -> str:
    """Get ZFS datasets for a pool."""
    return await zfs_datasets_resource(host, pool)


async def _zfs_snapshots(host: str) -> str:
    """Get ZFS snapshots."""
    return await zfs_snapshots_resource(host)


async def _syslog(host: str) -> str:
    """Get system logs from a remote host."""
    return await syslog_resource(host)


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

    # Register Docker resources for each host (before filesystem wildcard)
    for host_name in hosts:

        def make_docker_logs_handler(h: str) -> Any:
            async def handler(container: str) -> str:
                return await _read_docker_logs(h, container)

            return handler

        def make_docker_list_handler(h: str) -> Any:
            async def handler() -> str:
                return await _list_docker_containers(h)

            return handler

        # Docker logs: tootie://docker/plex/logs
        server.resource(
            uri=f"{host_name}://docker/{{container}}/logs",
            name=f"{host_name} docker logs",
            description=f"Read Docker container logs on {host_name}",
            mime_type="text/plain",
        )(make_docker_logs_handler(host_name))

        # Docker list: tootie://docker
        server.resource(
            uri=f"{host_name}://docker",
            name=f"{host_name} docker containers",
            description=f"List Docker containers on {host_name}",
            mime_type="text/plain",
        )(make_docker_list_handler(host_name))

    # Register Compose resources for each host
    for host_name in hosts:

        def make_compose_list_handler(h: str) -> Any:
            async def handler() -> str:
                return await _list_compose_projects(h)

            return handler

        def make_compose_file_handler(h: str) -> Any:
            async def handler(project: str) -> str:
                return await _read_compose_file(h, project)

            return handler

        def make_compose_logs_handler(h: str) -> Any:
            async def handler(project: str) -> str:
                return await _read_compose_logs(h, project)

            return handler

        # Compose list: tootie://compose
        server.resource(
            uri=f"{host_name}://compose",
            name=f"{host_name} compose projects",
            description=f"List Docker Compose projects on {host_name}",
            mime_type="text/plain",
        )(make_compose_list_handler(host_name))

        # Compose file: tootie://compose/plex
        server.resource(
            uri=f"{host_name}://compose/{{project}}",
            name=f"{host_name} compose file",
            description=f"Read Docker Compose config on {host_name}",
            mime_type="text/yaml",
        )(make_compose_file_handler(host_name))

        # Compose logs: tootie://compose/plex/logs
        server.resource(
            uri=f"{host_name}://compose/{{project}}/logs",
            name=f"{host_name} compose logs",
            description=f"Read Docker Compose stack logs on {host_name}",
            mime_type="text/plain",
        )(make_compose_logs_handler(host_name))

    # Register ZFS resources for each host
    for host_name in hosts:

        def make_zfs_overview_handler(h: str) -> Any:
            async def handler() -> str:
                return await _zfs_overview(h)

            return handler

        def make_zfs_pool_handler(h: str) -> Any:
            async def handler(pool: str) -> str:
                return await _zfs_pool(h, pool)

            return handler

        def make_zfs_datasets_handler(h: str) -> Any:
            async def handler(pool: str) -> str:
                return await _zfs_datasets(h, pool)

            return handler

        def make_zfs_snapshots_handler(h: str) -> Any:
            async def handler() -> str:
                return await _zfs_snapshots(h)

            return handler

        # ZFS overview: tootie://zfs
        server.resource(
            uri=f"{host_name}://zfs",
            name=f"{host_name} zfs overview",
            description=f"ZFS pool overview on {host_name}",
            mime_type="text/plain",
        )(make_zfs_overview_handler(host_name))

        # ZFS pool: tootie://zfs/cache
        server.resource(
            uri=f"{host_name}://zfs/{{pool}}",
            name=f"{host_name} zfs pool",
            description=f"ZFS pool status on {host_name}",
            mime_type="text/plain",
        )(make_zfs_pool_handler(host_name))

        # ZFS datasets: tootie://zfs/cache/datasets
        server.resource(
            uri=f"{host_name}://zfs/{{pool}}/datasets",
            name=f"{host_name} zfs datasets",
            description=f"ZFS datasets on {host_name}",
            mime_type="text/plain",
        )(make_zfs_datasets_handler(host_name))

        # ZFS snapshots: tootie://zfs/snapshots
        server.resource(
            uri=f"{host_name}://zfs/snapshots",
            name=f"{host_name} zfs snapshots",
            description=f"ZFS snapshots on {host_name}",
            mime_type="text/plain",
        )(make_zfs_snapshots_handler(host_name))

    # Register Syslog resources for each host
    for host_name in hosts:

        def make_syslog_handler(h: str) -> Any:
            async def handler() -> str:
                return await _syslog(h)

            return handler

        # Syslog: tootie://syslog
        server.resource(
            uri=f"{host_name}://syslog",
            name=f"{host_name} system logs",
            description=f"System logs on {host_name}",
            mime_type="text/plain",
        )(make_syslog_handler(host_name))

    # Register filesystem wildcard LAST (after specific patterns)
    for host_name in hosts:

        def make_handler(h: str) -> Any:
            async def handler(path: str) -> str:
                return await _read_host_path(h, path)

            return handler

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

    # Add health check endpoint for HTTP transport
    @server.custom_route("/health", methods=["GET"])
    async def health_check(_request: Request) -> PlainTextResponse:
        """Health check endpoint."""
        return PlainTextResponse("OK")

    return server


# Default server instance
mcp = create_server()

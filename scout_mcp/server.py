"""Scout MCP FastMCP server.

This is a thin wrapper that wires together the MCP server with tools and resources.
All business logic is delegated to the tools/, resources/, and services/ modules.
"""

import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from scout_mcp.dependencies import Dependencies
from scout_mcp.middleware import (
    APIKeyMiddleware,
    ErrorHandlingMiddleware,
    LoggingMiddleware,
    RateLimitMiddleware,
)
from scout_mcp.middleware.http_adapter import HTTPMiddlewareAdapter
from scout_mcp.resources import list_hosts_resource, scout_resource
from scout_mcp.resources.compose import (
    ComposeFilePlugin,
    ComposeListPlugin,
    ComposeLogsPlugin,
)
from scout_mcp.resources.docker import DockerListPlugin, DockerLogsPlugin
from scout_mcp.resources.registry import ResourceRegistry
from scout_mcp.resources.syslog import SyslogPlugin
from scout_mcp.resources.zfs import (
    ZFSDatasetsPlugin,
    ZFSOverviewPlugin,
    ZFSPoolPlugin,
    ZFSSnapshotsPlugin,
)
from scout_mcp.tools import scout, test_external_url, test_raw_html, test_remote_dom
from scout_mcp.utils.console import MCPRequestFormatter


def _configure_logging() -> None:
    """Configure colorful logging for the scout_mcp package.

    This is called at module load time to ensure logging is configured
    before any loggers are used, regardless of how the server is started.
    """
    # Get configuration from environment
    log_level = os.getenv("SCOUT_LOG_LEVEL", "DEBUG").upper()
    use_colors = os.getenv("SCOUT_LOG_COLORS", "true").lower() != "false"

    # Disable colors if not a TTY
    if not sys.stderr.isatty():
        use_colors = False

    # Configure root logger for scout_mcp
    scout_logger = logging.getLogger("scout_mcp")
    scout_logger.setLevel(getattr(logging, log_level, logging.DEBUG))

    # Only add handler if not already configured
    if not scout_logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(MCPRequestFormatter(use_colors=use_colors))
        scout_logger.addHandler(handler)
        scout_logger.propagate = False

    # Suppress noisy third-party loggers
    for noisy_logger in [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "asyncssh",
        "httpx",
        "httpcore",
        "fastmcp",
        "starlette",
        "anyio",
    ]:
        lg = logging.getLogger(noisy_logger)
        lg.setLevel(logging.WARNING)
        lg.handlers = []
        lg.propagate = False

    # Suppress root logger - this prevents uvicorn's default output
    root_logger = logging.getLogger()
    root_logger.handlers = []
    root_logger.setLevel(logging.WARNING)


# Configure logging at module load time
_configure_logging()

logger = logging.getLogger(__name__)


async def _read_host_path(host: str, path: str) -> str | dict[str, Any]:
    """Read a file or directory on a remote host.

    Args:
        host: SSH host name
        path: Remote path to read

    Returns:
        UIResource dict or plain text string
    """
    return await scout_resource(host, path)


async def _read_docker_logs(host: str, container: str) -> str:
    """Read Docker container logs on a remote host.

    Args:
        host: SSH host name
        container: Docker container name

    Returns:
        HTML string with log viewer
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
    """Read Docker Compose stack logs.

    Returns:
        HTML string with log viewer
    """
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
    """Get system logs from a remote host.

    Returns:
        HTML string with log viewer
    """
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
    logger.info("Scout MCP server starting up")

    # Create dependencies container
    deps = Dependencies.create()

    # Store in server context for tools/resources to access
    server.deps = deps

    config = deps.config
    hosts = config.get_hosts()
    logger.info(
        "Loaded %d SSH host(s): %s",
        len(hosts),
        ", ".join(sorted(hosts.keys())) if hosts else "(none)",
    )

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
            mime_type="text/html",
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
            mime_type="text/html",
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
            mime_type="text/html",
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

    resource_count = len(hosts) * 9  # 9 resource types per host
    logger.info(
        "Registered %d dynamic resources for %d host(s)",
        resource_count,
        len(hosts),
    )
    logger.info("Scout MCP server ready to accept connections")

    try:
        yield {"hosts": list(hosts.keys())}
    finally:
        # Shutdown: close all SSH connections
        logger.info("Scout MCP server shutting down")
        if deps.pool.pool_size > 0:
            logger.info(
                "Closing %d active SSH connection(s): %s",
                deps.pool.pool_size,
                ", ".join(deps.pool.active_hosts),
            )
            await deps.cleanup()
        logger.info("Scout MCP server shutdown complete")


def configure_middleware(server: FastMCP) -> None:
    """Configure middleware stack for the server.

    Adds middleware in order: ErrorHandling -> Logging (with integrated timing)

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
    # LoggingMiddleware now includes timing, so no separate TimingMiddleware needed
    server.add_middleware(ErrorHandlingMiddleware(include_traceback=include_traceback))
    server.add_middleware(
        LoggingMiddleware(
            include_payloads=log_payloads,
            slow_threshold_ms=slow_threshold,
        )
    )


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
    # Disable output_schema for scout tool - it returns UIResource in content
    # UIResource doesn't need outputSchema validation
    # (per MCP spec: content vs structuredContent)
    server.tool(output_schema=None)(scout)

    # Register MCP-UI test tools
    server.tool(output_schema=None)(test_raw_html)
    server.tool(output_schema=None)(test_remote_dom)
    server.tool(output_schema=None)(test_external_url)

    # Register resources
    server.resource("scout://{host}/{path*}")(scout_resource)
    server.resource("hosts://list")(list_hosts_resource)

    # Add health check endpoint for HTTP transport
    @server.custom_route("/health", methods=["GET"])
    async def health_check(request: Request) -> PlainTextResponse:
        """Health check endpoint."""
        client_host = request.client.host if request.client else "unknown"
        logger.debug("Health check from %s", client_host)
        return PlainTextResponse("OK")

    # Configure HTTP-level middleware for security
    http_app = server.http_app()

    # Add rate limiting middleware (always - disable via SCOUT_RATE_LIMIT_PER_MINUTE=0)
    rate_per_minute = int(os.getenv("SCOUT_RATE_LIMIT_PER_MINUTE", "60"))
    rate_burst = int(os.getenv("SCOUT_RATE_LIMIT_BURST", "10"))

    if rate_per_minute > 0:
        # Create MCP-layer middleware
        rate_limit = RateLimitMiddleware(
            per_minute=rate_per_minute,
            burst=rate_burst,
        )
        # Wrap in HTTP adapter
        http_app.add_middleware(
            HTTPMiddlewareAdapter,
            mcp_middleware=rate_limit,
        )
        logger.info(
            "Rate limiting middleware configured: %d req/min, burst=%d",
            rate_per_minute,
            rate_burst,
        )
    else:
        logger.info("Rate limiting disabled (SCOUT_RATE_LIMIT_PER_MINUTE=0)")

    # Add API key authentication if keys are set
    api_keys_str = os.getenv("SCOUT_API_KEYS", "").strip()
    if api_keys_str:
        # Create MCP-layer middleware
        api_keys = [k.strip() for k in api_keys_str.split(",") if k.strip()]
        auth_enabled = os.getenv("SCOUT_AUTH_ENABLED", "").lower() != "false"

        auth_middleware = APIKeyMiddleware(
            api_keys=api_keys,
            enabled=auth_enabled,
        )
        # Wrap in HTTP adapter
        http_app.add_middleware(
            HTTPMiddlewareAdapter,
            mcp_middleware=auth_middleware,
        )
        if auth_enabled:
            logger.info(
                "API key authentication enabled (%d key(s) configured)",
                len(api_keys),
            )
        else:
            logger.warning(
                "API key authentication DISABLED via SCOUT_AUTH_ENABLED=false"
            )
    else:
        logger.warning(
            "No API keys configured (SCOUT_API_KEYS not set). "
            "Authentication disabled - server is open to all requests!"
        )

    return server


# Default server instance
mcp = create_server()

"""ZFS resource plugins for reading pool and dataset info from remote hosts."""

from fastmcp.exceptions import ResourceError

from scout_mcp.dependencies import Dependencies
from scout_mcp.resources.plugin import ResourcePlugin
from scout_mcp.services import ConnectionError, get_connection_with_retry
from scout_mcp.services.executors import (
    zfs_check,
    zfs_datasets,
    zfs_pool_status,
    zfs_pools,
    zfs_snapshots,
)
from scout_mcp.services.validation import validate_host


async def zfs_overview_resource(host: str, deps: Dependencies) -> str:
    """Show ZFS overview for remote host.

    Args:
        host: SSH host name from ~/.ssh/config
        deps: Dependencies container with config and pool

    Returns:
        Formatted ZFS overview with pools and usage.
    """
    # Validate host exists
    ssh_host = validate_host(host, deps.config)

    # Get connection
    try:
        conn = await get_connection_with_retry(ssh_host, deps.pool)
    except ConnectionError as e:
        raise ResourceError(str(e)) from e

    # Check if ZFS is available
    has_zfs = await zfs_check(conn)
    if not has_zfs:
        return (
            f"# ZFS on {host}\n\n"
            "ZFS is not available on this host.\n\n"
            "This host either does not have ZFS installed or the zpool "
            "command is not accessible."
        )

    # Get pools
    pools_list = await zfs_pools(conn)

    if not pools_list:
        return f"# ZFS on {host}\n\nZFS is installed but no pools are configured."

    lines = [
        f"# ZFS Overview: {host}",
        "=" * 50,
        "",
        "## Pools",
        "",
    ]

    for p in pools_list:
        health_icon = "●" if p["health"] == "ONLINE" else "○"
        lines.append(f"{health_icon} {p['name']} ({p['health']})")
        lines.append(f"    Size:  {p['size']}")
        lines.append(f"    Used:  {p['alloc']} ({p['cap']})")
        lines.append(f"    Free:  {p['free']}")
        lines.append(f"    View:  {host}://zfs/{p['name']}")
        lines.append("")

    lines.append("## Quick Links")
    lines.append("")
    lines.append(f"  Snapshots: {host}://zfs/snapshots")
    for p in pools_list:
        lines.append(f"  {p['name']} datasets: {host}://zfs/{p['name']}/datasets")

    return "\n".join(lines)


async def zfs_pool_resource(host: str, pool_name: str, deps: Dependencies) -> str:
    """Show detailed ZFS pool status.

    Args:
        host: SSH host name from ~/.ssh/config
        pool_name: ZFS pool name
        deps: Dependencies container with config and pool

    Returns:
        Pool status output.
    """
    # Validate host exists
    ssh_host = validate_host(host, deps.config)

    # Get connection
    try:
        conn = await get_connection_with_retry(ssh_host, deps.pool)
    except ConnectionError as e:
        raise ResourceError(str(e)) from e

    # Check if ZFS is available
    has_zfs = await zfs_check(conn)
    if not has_zfs:
        return f"# ZFS Pool: {pool_name}@{host}\n\nZFS is not available on this host."

    # Get pool status
    status, exists = await zfs_pool_status(conn, pool_name)

    if not exists:
        pools_list = await zfs_pools(conn)
        available_pools = ", ".join(p["name"] for p in pools_list) or "none"
        raise ResourceError(
            f"Pool '{pool_name}' not found on {host}. "
            f"Available pools: {available_pools}"
        )

    header = f"# ZFS Pool: {pool_name}@{host}\n\n"
    return header + status


async def zfs_datasets_resource(host: str, pool_name: str, deps: Dependencies) -> str:
    """Show ZFS datasets for a pool.

    Args:
        host: SSH host name from ~/.ssh/config
        pool_name: ZFS pool name
        deps: Dependencies container with config and pool

    Returns:
        Formatted dataset list.
    """
    # Validate host exists
    ssh_host = validate_host(host, deps.config)

    # Get connection
    try:
        conn = await get_connection_with_retry(ssh_host, deps.pool)
    except ConnectionError as e:
        raise ResourceError(str(e)) from e

    # Check if ZFS is available
    has_zfs = await zfs_check(conn)
    if not has_zfs:
        return (
            f"# ZFS Datasets: {pool_name}@{host}\n\nZFS is not available on this host."
        )

    # Get datasets
    datasets_list = await zfs_datasets(conn, pool_name)

    if not datasets_list:
        raise ResourceError(
            f"Pool '{pool_name}' not found or has no datasets on {host}. "
            f"Use {host}://zfs to see available pools."
        )

    lines = [
        f"# ZFS Datasets: {pool_name}@{host}",
        "=" * 50,
        "",
        f"{'NAME':<50} {'USED':>8} {'AVAIL':>8} {'REFER':>8} MOUNTPOINT",
        "-" * 90,
    ]

    for d in datasets_list:
        name = d["name"]
        if len(name) > 48:
            name = "..." + name[-45:]
        line = (
            f"{name:<50} {d['used']:>8} {d['avail']:>8} "
            f"{d['refer']:>8} {d['mountpoint']}"
        )
        lines.append(line)

    return "\n".join(lines)


async def zfs_snapshots_resource(host: str, deps: Dependencies) -> str:
    """Show ZFS snapshots on host.

    Args:
        host: SSH host name from ~/.ssh/config
        deps: Dependencies container with config and pool

    Returns:
        Formatted snapshot list.
    """
    # Validate host exists
    ssh_host = validate_host(host, deps.config)

    # Get connection
    try:
        conn = await get_connection_with_retry(ssh_host, deps.pool)
    except ConnectionError as e:
        raise ResourceError(str(e)) from e

    # Check if ZFS is available
    has_zfs = await zfs_check(conn)
    if not has_zfs:
        return f"# ZFS Snapshots: {host}\n\nZFS is not available on this host."

    # Get snapshots
    snapshots_list = await zfs_snapshots(conn, limit=50)

    if not snapshots_list:
        return f"# ZFS Snapshots: {host}\n\nNo snapshots found."

    lines = [
        f"# ZFS Snapshots: {host}",
        "=" * 50,
        "(showing last 50 snapshots)",
        "",
    ]

    for s in snapshots_list:
        lines.append(f"  {s['name']}")
        lines.append(f"      Used: {s['used']:<10} Created: {s['creation']}")
        lines.append("")

    return "\n".join(lines)


class ZFSOverviewPlugin(ResourcePlugin):
    """ZFS pool overview resource.

    URI: {host}://zfs
    """

    def __init__(self, deps: Dependencies):
        """Initialize plugin with dependencies.

        Args:
            deps: Dependencies container with config and pool
        """
        self.deps = deps

    def get_uri_template(self) -> str:
        return "{host}://zfs"

    def get_description(self) -> str:
        return "ZFS pool overview"

    async def handle(self, host: str) -> str:
        """Get ZFS overview for host."""
        return await zfs_overview_resource(host, self.deps)


class ZFSPoolPlugin(ResourcePlugin):
    """ZFS pool status resource.

    URI: {host}://zfs/{pool}
    """

    def __init__(self, deps: Dependencies):
        """Initialize plugin with dependencies.

        Args:
            deps: Dependencies container with config and pool
        """
        self.deps = deps

    def get_uri_template(self) -> str:
        return "{host}://zfs/{{pool}}"

    def get_description(self) -> str:
        return "ZFS pool status"

    async def handle(self, host: str, pool: str) -> str:
        """Get ZFS pool status."""
        return await zfs_pool_resource(host, pool, self.deps)


class ZFSDatasetsPlugin(ResourcePlugin):
    """ZFS datasets resource.

    URI: {host}://zfs/{pool}/datasets
    """

    def __init__(self, deps: Dependencies):
        """Initialize plugin with dependencies.

        Args:
            deps: Dependencies container with config and pool
        """
        self.deps = deps

    def get_uri_template(self) -> str:
        return "{host}://zfs/{{pool}}/datasets"

    def get_description(self) -> str:
        return "ZFS datasets for pool"

    async def handle(self, host: str, pool: str) -> str:
        """Get ZFS datasets for pool."""
        return await zfs_datasets_resource(host, pool, self.deps)


class ZFSSnapshotsPlugin(ResourcePlugin):
    """ZFS snapshots resource.

    URI: {host}://zfs/snapshots
    """

    def __init__(self, deps: Dependencies):
        """Initialize plugin with dependencies.

        Args:
            deps: Dependencies container with config and pool
        """
        self.deps = deps

    def get_uri_template(self) -> str:
        return "{host}://zfs/snapshots"

    def get_description(self) -> str:
        return "ZFS snapshots (last 50)"

    async def handle(self, host: str) -> str:
        """Get ZFS snapshots for host."""
        return await zfs_snapshots_resource(host, self.deps)

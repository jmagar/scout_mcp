"""Hosts resource for listing available SSH hosts."""

from scout_mcp.services import get_config
from scout_mcp.utils.ping import check_hosts_online


async def list_hosts_resource() -> str:
    """List available SSH hosts with online status and URI schemes.

    Returns:
        Formatted list of available SSH hosts with connectivity status
        and both host-specific and generic URI formats.
    """
    config = get_config()
    hosts = config.get_hosts()

    if not hosts:
        return "No SSH hosts configured."

    # Build dict for concurrent checking
    host_endpoints = {name: (host.hostname, host.port) for name, host in hosts.items()}

    # Check all hosts concurrently
    online_status = await check_hosts_online(host_endpoints, timeout=2.0)

    lines = ["Available SSH Hosts", "=" * 40, ""]

    for name, host in sorted(hosts.items()):
        status = "online" if online_status.get(name) else "offline"
        status_icon = "\u2713" if online_status.get(name) else "\u2717"
        host_info = f"{host.user}@{host.hostname}:{host.port}"

        lines.append(f"[{status_icon}] {name} ({status})")
        lines.append(f"    SSH:      {host_info}")
        lines.append(f"    Direct:   {name}://path/to/file")
        lines.append(f"    Generic:  scout://{name}/path/to/file")
        lines.append("")

    lines.append("Usage Examples:")
    lines.append("-" * 40)

    example_hosts = list(sorted(hosts.keys()))[:2]
    for h in example_hosts:
        lines.append(f"  {h}://etc/hosts          (host-specific)")
        lines.append(f"  scout://{h}/var/log      (generic fallback)")

    lines.append("")
    lines.append("Both URI formats work identically.")

    return "\n".join(lines)

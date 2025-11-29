"""Host connectivity checking utilities."""

import asyncio


async def check_host_online(hostname: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a host is reachable via TCP connection.

    Args:
        hostname: Host to check.
        port: Port to connect to (usually SSH port).
        timeout: Connection timeout in seconds.

    Returns:
        True if host is reachable, False otherwise.
    """
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(hostname, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (TimeoutError, OSError):
        return False


async def check_hosts_online(
    hosts: dict[str, tuple[str, int]],
    timeout: float = 2.0,
) -> dict[str, bool]:
    """Check multiple hosts concurrently.

    Args:
        hosts: Dict of {name: (hostname, port)}.
        timeout: Connection timeout per host.

    Returns:
        Dict of {name: is_online}.
    """
    if not hosts:
        return {}

    names = list(hosts.keys())
    coros = [
        check_host_online(hostname, port, timeout)
        for hostname, port in hosts.values()
    ]

    results = await asyncio.gather(*coros)
    return dict(zip(names, results))

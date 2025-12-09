"""SSH connection helper with automatic retry."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncssh

    from scout_mcp.models import SSHHost

logger = logging.getLogger(__name__)


class ConnectionError(Exception):
    """Failed to establish SSH connection after retry."""

    def __init__(self, host_name: str, original_error: Exception):
        """Initialize connection error.

        Args:
            host_name: Name of the SSH host
            original_error: Original exception that caused the failure
        """
        self.host_name = host_name
        self.original_error = original_error
        super().__init__(f"Cannot connect to {host_name}: {original_error}")


async def get_connection_with_retry(
    ssh_host: "SSHHost",
) -> "asyncssh.SSHClientConnection":
    """Get SSH connection with automatic one-time retry on failure.

    This function implements a one-retry pattern with automatic cleanup
    of stale connections. If the first connection attempt fails, it will:
    1. Log a warning about the failure
    2. Remove the potentially stale connection from the pool
    3. Attempt to connect one more time
    4. Raise ConnectionError if the retry also fails

    Args:
        ssh_host: SSH host configuration

    Returns:
        Active SSH connection

    Raises:
        ConnectionError: If connection fails after retry
    """
    from scout_mcp.services.state import get_pool

    pool = get_pool()

    try:
        return await pool.get_connection(ssh_host)
    except Exception as first_error:
        # Connection failed - clear stale connection and retry once
        logger.warning(
            "Connection to %s failed: %s, retrying after cleanup",
            ssh_host.name,
            first_error,
        )
        try:
            await pool.remove_connection(ssh_host.name)
            conn = await pool.get_connection(ssh_host)
            logger.info("Retry connection to %s succeeded", ssh_host.name)
            return conn
        except Exception as retry_error:
            logger.error(
                "Retry connection to %s failed: %s",
                ssh_host.name,
                retry_error,
            )
            raise ConnectionError(ssh_host.name, retry_error) from retry_error

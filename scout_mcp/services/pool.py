"""SSH connection pooling with lazy disconnect."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import asyncssh

from scout_mcp.models import PooledConnection

if TYPE_CHECKING:
    from scout_mcp.models import SSHHost

logger = logging.getLogger(__name__)


class ConnectionPool:
    """SSH connection pool with idle timeout."""

    def __init__(
        self,
        idle_timeout: int = 60,
        known_hosts: str | None = None,
        strict_host_key_checking: bool = True,
    ) -> None:
        """Initialize pool with idle timeout in seconds.

        Args:
            idle_timeout: Seconds before idle connections are closed
            known_hosts: Path to known_hosts file, or None to disable verification
            strict_host_key_checking: Whether to reject unknown host keys
        """
        self.idle_timeout = idle_timeout
        self._connections: dict[str, PooledConnection] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task[Any] | None = None

        # Cache known_hosts configuration
        self._known_hosts = known_hosts
        self._strict_host_key = strict_host_key_checking

        if self._known_hosts is None:
            logger.warning(
                "SSH host key verification DISABLED - vulnerable to MITM attacks. "
                "Set SCOUT_KNOWN_HOSTS to a valid known_hosts file path."
            )
        else:
            logger.info(
                "SSH host key verification enabled (known_hosts=%s, strict=%s)",
                self._known_hosts,
                self._strict_host_key,
            )

        logger.debug(
            "ConnectionPool initialized (idle_timeout=%ds)",
            idle_timeout,
        )

    async def get_connection(self, host: "SSHHost") -> asyncssh.SSHClientConnection:
        """Get or create a connection to the host."""
        async with self._lock:
            pooled = self._connections.get(host.name)

            # Return existing if valid
            if pooled and not pooled.is_stale:
                pooled.touch()
                logger.debug(
                    "Reusing existing connection to %s (pool_size=%d)",
                    host.name,
                    len(self._connections),
                )
                return pooled.connection

            # Log stale connection detection
            if pooled and pooled.is_stale:
                logger.info(
                    "Connection to %s is stale, creating new connection",
                    host.name,
                )

            # Create new connection
            logger.info(
                "Opening SSH connection to %s (%s@%s:%d)",
                host.name,
                host.user,
                host.hostname,
                host.port,
            )
            client_keys = [host.identity_file] if host.identity_file else None

            # Determine known_hosts setting
            known_hosts_arg = (
                None if self._known_hosts is None else self._known_hosts
            )

            try:
                conn = await asyncssh.connect(
                    host.hostname,
                    port=host.port,
                    username=host.user,
                    known_hosts=known_hosts_arg,
                    client_keys=client_keys,
                )
            except asyncssh.HostKeyNotVerifiable as e:
                if self._strict_host_key:
                    logger.error(
                        "Host key verification failed for %s: %s. "
                        "Add the host key to %s or set "
                        "SCOUT_STRICT_HOST_KEY_CHECKING=false",
                        host.name,
                        e,
                        self._known_hosts,
                    )
                    raise
                else:
                    logger.warning(
                        "Host key not verified for %s (strict mode disabled): %s",
                        host.name,
                        e,
                    )
                    # Retry with verification disabled for this host
                    conn = await asyncssh.connect(
                        host.hostname,
                        port=host.port,
                        username=host.user,
                        known_hosts=None,
                        client_keys=client_keys,
                    )

            self._connections[host.name] = PooledConnection(connection=conn)
            logger.info(
                "SSH connection established to %s (pool_size=%d)",
                host.name,
                len(self._connections),
            )

            # Start cleanup task if not running
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._cleanup_loop())
                logger.debug("Started connection cleanup task")

            return conn

    async def _cleanup_loop(self) -> None:
        """Periodically clean up idle connections."""
        logger.debug("Cleanup loop started (interval=%ds)", self.idle_timeout // 2)
        while True:
            await asyncio.sleep(self.idle_timeout // 2)
            await self._cleanup_idle()

            # Stop if no connections left
            if not self._connections:
                logger.debug("Cleanup loop stopped - no connections remaining")
                break

    async def _cleanup_idle(self) -> None:
        """Close connections that have been idle too long."""
        async with self._lock:
            cutoff = datetime.now() - timedelta(seconds=self.idle_timeout)
            to_remove = []

            for name, pooled in self._connections.items():
                if pooled.last_used < cutoff or pooled.is_stale:
                    reason = "stale" if pooled.is_stale else "idle"
                    logger.info(
                        "Closing %s connection to %s (pool_size=%d)",
                        reason,
                        name,
                        len(self._connections) - 1,
                    )
                    pooled.connection.close()
                    to_remove.append(name)

            for name in to_remove:
                del self._connections[name]

            if to_remove:
                logger.debug(
                    "Cleanup complete: removed %d connection(s), %d remaining",
                    len(to_remove),
                    len(self._connections),
                )

    async def close_all(self) -> None:
        """Close all connections."""
        async with self._lock:
            count = len(self._connections)
            if count > 0:
                logger.info("Closing all %d connection(s)", count)
                for name, pooled in self._connections.items():
                    logger.debug("Closing connection to %s", name)
                    pooled.connection.close()
                self._connections.clear()

            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
                logger.debug("Cleanup task cancelled")

    async def remove_connection(self, host_name: str) -> None:
        """Remove a specific connection from the pool.

        Args:
            host_name: Name of the host to remove.
        """
        async with self._lock:
            if host_name in self._connections:
                logger.info(
                    "Removing connection to %s (pool_size=%d)",
                    host_name,
                    len(self._connections) - 1,
                )
                pooled = self._connections[host_name]
                pooled.connection.close()
                del self._connections[host_name]
            else:
                logger.debug(
                    "No connection to remove for %s (not in pool)",
                    host_name,
                )

    @property
    def pool_size(self) -> int:
        """Return the current number of connections in the pool."""
        return len(self._connections)

    @property
    def active_hosts(self) -> list[str]:
        """Return list of hosts with active connections."""
        return list(self._connections.keys())

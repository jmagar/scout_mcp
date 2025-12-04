"""SSH connection pooling with lazy disconnect.

Locking Strategy:
- `_meta_lock`: Protects _connections OrderedDict and _host_locks dict structure
- Per-host locks: Protect connection creation/removal for specific hosts
- Lock acquisition order: Always per-host lock first, then meta-lock if needed

LRU Eviction:
- Uses OrderedDict with move_to_end() for O(1) LRU tracking
- Eviction happens when pool reaches max_size before creating new connection
- Oldest (first) connection is evicted
"""

import asyncio
import logging
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import asyncssh

from scout_mcp.models import PooledConnection

if TYPE_CHECKING:
    from scout_mcp.models import SSHHost

logger = logging.getLogger(__name__)


class ConnectionPool:
    """SSH connection pool with size limits and LRU eviction."""

    def __init__(
        self,
        idle_timeout: int = 60,
        max_size: int = 100,
        known_hosts: str | None = None,
        strict_host_key_checking: bool = True,
    ) -> None:
        """Initialize pool with idle timeout and size limits.

        Args:
            idle_timeout: Seconds before idle connections are closed
            max_size: Maximum number of concurrent SSH connections (must be > 0)
            known_hosts: Path to known_hosts file, or None to disable verification
            strict_host_key_checking: Whether to reject unknown host keys

        Raises:
            ValueError: If max_size is not positive
        """
        if max_size <= 0:
            raise ValueError(f"max_size must be > 0, got {max_size}")

        self.idle_timeout = idle_timeout
        self.max_size = max_size
        self._connections: OrderedDict[str, PooledConnection] = OrderedDict()
        self._host_locks: dict[str, asyncio.Lock] = {}
        self._meta_lock = asyncio.Lock()  # Protects _connections and _host_locks
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

        logger.info(
            "ConnectionPool initialized (idle_timeout=%ds, max_size=%d)",
            idle_timeout,
            max_size,
        )

    async def _get_host_lock(self, host_name: str) -> asyncio.Lock:
        """Get or create lock for a specific host.

        Args:
            host_name: Name of the host to get lock for

        Returns:
            Lock for the specified host
        """
        async with self._meta_lock:
            if host_name not in self._host_locks:
                self._host_locks[host_name] = asyncio.Lock()
            return self._host_locks[host_name]

    async def _evict_lru_if_needed(self) -> None:
        """Evict least recently used connections if at capacity.

        Uses meta-lock to protect OrderedDict operations during eviction.
        Connections are closed outside the lock to avoid blocking.
        """
        to_close: list[PooledConnection] = []

        async with self._meta_lock:
            while len(self._connections) >= self.max_size:
                # Get oldest (first) key from OrderedDict
                oldest_host = next(iter(self._connections))
                logger.info(
                    "Pool at capacity (%d/%d), evicting LRU: %s",
                    len(self._connections),
                    self.max_size,
                    oldest_host,
                )
                # Remove from pool (close outside lock)
                pooled = self._connections.pop(oldest_host)
                to_close.append(pooled)

        # Close connections outside meta-lock to avoid blocking
        for pooled in to_close:
            pooled.connection.close()

    async def get_connection(self, host: "SSHHost") -> asyncssh.SSHClientConnection:
        """Get or create a connection to the host."""
        host_lock = await self._get_host_lock(host.name)

        async with host_lock:
            pooled = self._connections.get(host.name)

            # Return existing if valid (move to end for LRU)
            if pooled and not pooled.is_stale:
                pooled.touch()
                # Move to end (most recently used) - needs meta-lock for OrderedDict
                async with self._meta_lock:
                    self._connections.move_to_end(host.name)
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

            # Check capacity before creating new
            await self._evict_lru_if_needed()

            # Create new connection (only holds host-specific lock, not global)
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
                # Network I/O happens here - only blocks same host, not all hosts
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

            # Add to pool under meta-lock for OrderedDict safety
            async with self._meta_lock:
                self._connections[host.name] = PooledConnection(connection=conn)
                # New connections go to end (most recently used)
                self._connections.move_to_end(host.name)

            logger.info(
                "SSH connection established to %s (pool_size=%d/%d)",
                host.name,
                len(self._connections),
                self.max_size,
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
        # Get snapshot of hosts to check
        async with self._meta_lock:
            hosts_to_check = list(self._connections.keys())

        cutoff = datetime.now() - timedelta(seconds=self.idle_timeout)
        removed_count = 0

        for host_name in hosts_to_check:
            host_lock = await self._get_host_lock(host_name)
            async with host_lock:
                pooled = self._connections.get(host_name)
                if pooled and (pooled.last_used < cutoff or pooled.is_stale):
                    reason = "stale" if pooled.is_stale else "idle"
                    logger.info(
                        "Closing %s connection to %s (pool_size=%d)",
                        reason,
                        host_name,
                        len(self._connections) - 1,
                    )
                    pooled.connection.close()
                    del self._connections[host_name]
                    removed_count += 1

        if removed_count > 0:
            logger.debug(
                "Cleanup complete: removed %d connection(s), %d remaining",
                removed_count,
                len(self._connections),
            )

    async def close_all(self) -> None:
        """Close all connections."""
        # Get all host names first
        async with self._meta_lock:
            host_names = list(self._connections.keys())

        if len(host_names) > 0:
            logger.info("Closing all %d connection(s)", len(host_names))
            for host_name in host_names:
                await self.remove_connection(host_name)

        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            logger.debug("Cleanup task cancelled")

    async def remove_connection(self, host_name: str) -> None:
        """Remove a specific connection from the pool.

        Args:
            host_name: Name of the host to remove.
        """
        host_lock = await self._get_host_lock(host_name)
        async with host_lock:
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

"""SSH connection pooling with lazy disconnect."""

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import asyncssh

from scout_mcp.models import PooledConnection

if TYPE_CHECKING:
    from scout_mcp.models import SSHHost


class ConnectionPool:
    """SSH connection pool with idle timeout."""

    def __init__(self, idle_timeout: int = 60) -> None:
        """Initialize pool with idle timeout in seconds."""
        self.idle_timeout = idle_timeout
        self._connections: dict[str, PooledConnection] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task[Any] | None = None

    async def get_connection(self, host: "SSHHost") -> asyncssh.SSHClientConnection:
        """Get or create a connection to the host."""
        async with self._lock:
            pooled = self._connections.get(host.name)

            # Return existing if valid
            if pooled and not pooled.is_stale:
                pooled.touch()
                return pooled.connection

            # Create new connection
            client_keys = [host.identity_file] if host.identity_file else None
            conn = await asyncssh.connect(
                host.hostname,
                port=host.port,
                username=host.user,
                known_hosts=None,
                client_keys=client_keys,
            )

            self._connections[host.name] = PooledConnection(connection=conn)

            # Start cleanup task if not running
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._cleanup_loop())

            return conn

    async def _cleanup_loop(self) -> None:
        """Periodically clean up idle connections."""
        while True:
            await asyncio.sleep(self.idle_timeout // 2)
            await self._cleanup_idle()

            # Stop if no connections left
            if not self._connections:
                break

    async def _cleanup_idle(self) -> None:
        """Close connections that have been idle too long."""
        async with self._lock:
            cutoff = datetime.now() - timedelta(seconds=self.idle_timeout)
            to_remove = []

            for name, pooled in self._connections.items():
                if pooled.last_used < cutoff or pooled.is_stale:
                    pooled.connection.close()
                    to_remove.append(name)

            for name in to_remove:
                del self._connections[name]

    async def close_all(self) -> None:
        """Close all connections."""
        async with self._lock:
            for pooled in self._connections.values():
                pooled.connection.close()
            self._connections.clear()

            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()

    async def remove_connection(self, host_name: str) -> None:
        """Remove a specific connection from the pool.

        Args:
            host_name: Name of the host to remove.
        """
        async with self._lock:
            if host_name in self._connections:
                pooled = self._connections[host_name]
                pooled.connection.close()
                del self._connections[host_name]

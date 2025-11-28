"""SSH connection pooling with lazy disconnect."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import asyncssh

if TYPE_CHECKING:
    from mcp_cat.config import SSHHost


@dataclass
class PooledConnection:
    """A pooled SSH connection with last-used timestamp."""

    connection: asyncssh.SSHClientConnection
    last_used: datetime = field(default_factory=datetime.now)

    def touch(self) -> None:
        """Update last-used timestamp."""
        self.last_used = datetime.now()

    @property
    def is_stale(self) -> bool:
        """Check if connection was closed."""
        is_closed: bool = self.connection.is_closed  # type: ignore[assignment]
        return is_closed


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
            conn = await asyncssh.connect(
                host.hostname,
                port=host.port,
                username=host.user,
                known_hosts=None,
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

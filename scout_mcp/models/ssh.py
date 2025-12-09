"""SSH-related data models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncssh


@dataclass
class SSHHost:
    """SSH host configuration."""

    name: str
    hostname: str
    user: str = "root"
    port: int = 22
    identity_file: str | None = None
    is_localhost: bool = False

    @property
    def connection_hostname(self) -> str:
        """Get the hostname to use for SSH connection.

        Returns:
            127.0.0.1 if is_localhost, otherwise original hostname
        """
        return "127.0.0.1" if self.is_localhost else self.hostname

    @property
    def connection_port(self) -> int:
        """Get the port to use for SSH connection.

        Returns:
            22 if is_localhost, otherwise original port
        """
        return 22 if self.is_localhost else self.port


@dataclass
class PooledConnection:
    """A pooled SSH connection with last-used timestamp."""

    connection: "asyncssh.SSHClientConnection"
    last_used: datetime = field(default_factory=datetime.now)

    def touch(self) -> None:
        """Update last-used timestamp."""
        self.last_used = datetime.now()

    @property
    def is_stale(self) -> bool:
        """Check if connection was closed."""
        is_closed: bool = self.connection.is_closed  # type: ignore[assignment]
        return is_closed

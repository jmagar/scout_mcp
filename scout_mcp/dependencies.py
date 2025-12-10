"""Dependency injection container for Scout MCP.

Replaces global singleton pattern with explicit dependency injection.
"""

from dataclasses import dataclass

from scout_mcp.config import Config
from scout_mcp.services.pool import ConnectionPool


@dataclass
class Dependencies:
    """Container for Scout MCP dependencies.

    Holds configuration and connection pool instances.
    Pass this to functions/tools that need access to config or pool.

    Example:
        deps = Dependencies.create()
        result = await some_function(deps=deps)
    """

    config: Config
    pool: ConnectionPool

    @classmethod
    def create(cls) -> "Dependencies":
        """Create dependencies with default configuration.

        Returns:
            Initialized Dependencies instance
        """
        config = Config()
        pool = ConnectionPool(
            idle_timeout=config.idle_timeout,
            max_size=config.max_pool_size,
            known_hosts=config.known_hosts_path,
            strict_host_key_checking=config.strict_host_key_checking,
        )
        return cls(config=config, pool=pool)

    @classmethod
    def from_config(cls, config: Config) -> "Dependencies":
        """Create dependencies with custom configuration.

        Args:
            config: Custom Config instance

        Returns:
            Dependencies with pool initialized from config
        """
        pool = ConnectionPool(
            idle_timeout=config.idle_timeout,
            max_size=config.max_pool_size,
            known_hosts=config.known_hosts_path,
            strict_host_key_checking=config.strict_host_key_checking,
        )
        return cls(config=config, pool=pool)

    async def cleanup(self) -> None:
        """Clean up resources (close all connections)."""
        await self.pool.close_all()

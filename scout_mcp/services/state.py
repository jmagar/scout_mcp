"""Global state management for Scout MCP."""

from scout_mcp.config import Config
from scout_mcp.services.pool import ConnectionPool

# Global state (initialized on first access)
_config: Config | None = None
_pool: ConnectionPool | None = None


def get_config() -> Config:
    """Get or create config."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def get_pool() -> ConnectionPool:
    """Get or create connection pool."""
    global _pool
    if _pool is None:
        config = get_config()
        _pool = ConnectionPool(
            idle_timeout=config.idle_timeout,
            known_hosts=config.known_hosts_path,
            strict_host_key_checking=config.strict_host_key_checking,
        )
    return _pool


def reset_state() -> None:
    """Reset global state for testing.

    This function clears the singleton instances, allowing tests
    to start with fresh state. Should only be used in test fixtures.
    """
    global _config, _pool
    _config = None
    _pool = None


def set_config(config: Config) -> None:
    """Set the global config instance.

    Allows tests to inject a custom config without modifying module internals.

    Args:
        config: Config instance to use globally.
    """
    global _config
    _config = config


def set_pool(pool: ConnectionPool) -> None:
    """Set the global pool instance.

    Allows tests to inject a custom pool without modifying module internals.

    Args:
        pool: ConnectionPool instance to use globally.
    """
    global _pool
    _pool = pool

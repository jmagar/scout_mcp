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
        _pool = ConnectionPool(idle_timeout=config.idle_timeout)
    return _pool

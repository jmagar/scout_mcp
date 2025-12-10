"""Tests for dependency injection container."""

from scout_mcp.config import Config
from scout_mcp.dependencies import Dependencies
from scout_mcp.services.pool import ConnectionPool


class TestDependencies:
    """Test Dependencies container."""

    def test_create_initializes_config_and_pool(self):
        """Dependencies.create() should initialize both config and pool."""
        deps = Dependencies.create()

        assert isinstance(deps.config, Config)
        assert isinstance(deps.pool, ConnectionPool)

    def test_pool_uses_config_values(self):
        """Pool should be initialized with config values."""
        deps = Dependencies.create()

        assert deps.pool.idle_timeout == deps.config.idle_timeout
        assert deps.pool.max_size == deps.config.max_pool_size

    def test_from_config_uses_provided_config(self):
        """Dependencies.from_config() should use provided config."""
        custom_config = Config.from_env()
        custom_config.max_pool_size = 50

        deps = Dependencies.from_config(custom_config)

        assert deps.config is custom_config
        assert deps.pool.max_size == 50

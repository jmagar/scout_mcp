"""Application settings from environment variables.

Centralized environment variable parsing and validation.
"""

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Settings:
    """Application settings from environment.

    Handles parsing, validation, and defaults for all env vars.
    """

    # File/command limits
    max_file_size: int = field(default=1_048_576)  # 1MB
    command_timeout: int = field(default=30)

    # Connection pool
    idle_timeout: int = field(default=60)
    max_pool_size: int = field(default=100)

    # Transport
    transport: str = field(default="http")
    http_host: str = field(default="0.0.0.0")
    http_port: int = field(default=8000)

    # Security
    api_keys: list[str] = field(default_factory=list)
    auth_enabled: bool = field(default=True)
    rate_limit_per_minute: int = field(default=60)
    rate_limit_burst: int = field(default=10)

    # Logging
    log_level: str = field(default="INFO")
    log_payloads: bool = field(default=False)
    slow_threshold_ms: int = field(default=1000)
    include_traceback: bool = field(default=False)

    # UI
    enable_ui: bool = field(default=False)

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment variables.

        Supports both SCOUT_* (preferred) and legacy MCP_CAT_* prefixes.
        SCOUT_* takes precedence if both are set.

        Returns:
            Settings instance with values from environment
        """
        return cls(
            max_file_size=cls._get_int("SCOUT_MAX_FILE_SIZE", "MCP_CAT_MAX_FILE_SIZE", 1_048_576),
            command_timeout=cls._get_int("SCOUT_COMMAND_TIMEOUT", "MCP_CAT_COMMAND_TIMEOUT", 30),
            idle_timeout=cls._get_int("SCOUT_IDLE_TIMEOUT", "MCP_CAT_IDLE_TIMEOUT", 60),
            max_pool_size=cls._get_int("SCOUT_MAX_POOL_SIZE", "", 100),
            transport=cls._get_transport(),
            http_host=os.getenv("SCOUT_HTTP_HOST", "0.0.0.0"),
            http_port=cls._get_int("SCOUT_HTTP_PORT", "", 8000),
            api_keys=cls._get_api_keys(),
            auth_enabled=cls._get_bool("SCOUT_AUTH_ENABLED", True),
            rate_limit_per_minute=cls._get_int("SCOUT_RATE_LIMIT_PER_MINUTE", "", 60),
            rate_limit_burst=cls._get_int("SCOUT_RATE_LIMIT_BURST", "", 10),
            log_level=os.getenv("SCOUT_LOG_LEVEL", "INFO"),
            log_payloads=cls._get_bool("SCOUT_LOG_PAYLOADS", False),
            slow_threshold_ms=cls._get_int("SCOUT_SLOW_THRESHOLD_MS", "", 1000),
            include_traceback=cls._get_bool("SCOUT_INCLUDE_TRACEBACK", False),
            enable_ui=cls._get_bool("SCOUT_ENABLE_UI", False),
        )

    @staticmethod
    def _get_int(key: str, legacy_key: str, default: int) -> int:
        """Get integer from environment with legacy fallback.

        Args:
            key: Primary environment variable key
            legacy_key: Legacy MCP_CAT_* key (empty string to skip)
            default: Default value if not set

        Returns:
            Integer value from environment or default
        """
        # SCOUT_* takes precedence
        value = os.getenv(key)
        if value is None and legacy_key:
            value = os.getenv(legacy_key)

        if value is None:
            return default

        try:
            return int(value)
        except ValueError:
            logger.warning("Invalid int for %s: %s, using default %d", key, value, default)
            return default

    @staticmethod
    def _get_bool(key: str, default: bool) -> bool:
        """Get boolean from environment.

        Args:
            key: Environment variable key
            default: Default value if not set

        Returns:
            Boolean value from environment or default
        """
        value = os.getenv(key)
        if value is None:
            return default
        return value.lower() in ("1", "true", "yes", "on")

    @staticmethod
    def _get_api_keys() -> list[str]:
        """Get API keys from environment.

        Returns:
            List of API keys (empty if not set)
        """
        value = os.getenv("SCOUT_API_KEYS", "").strip()
        if not value:
            return []
        return [k.strip() for k in value.split(",") if k.strip()]

    @staticmethod
    def _get_transport() -> str:
        """Get transport from environment with validation.

        Returns:
            Transport type ("http" or "stdio")
        """
        transport = os.getenv("SCOUT_TRANSPORT", "").lower()
        if transport in ("http", "stdio"):
            return transport
        return "http"

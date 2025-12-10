"""Application configuration.

Delegates to specialized components:
- SSHConfigParser: Reads ~/.ssh/config
- HostKeyVerifier: Manages known_hosts
- Settings: Environment variables
"""

import logging
import os
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

from scout_mcp.config.host_keys import HostKeyVerifier
from scout_mcp.config.parser import SSHConfigParser
from scout_mcp.config.settings import Settings
from scout_mcp.models import SSHHost

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Application configuration.

    Aggregates settings from SSH config, known_hosts, and environment.
    Delegates to specialized components for each concern.
    """

    settings: Settings
    parser: SSHConfigParser
    host_keys: HostKeyVerifier
    _hosts_cache: dict[str, SSHHost] = field(default_factory=dict, init=False, repr=False)

    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment.

        Returns:
            Configured instance with all components initialized
        """
        settings = Settings.from_env()

        # Get allowlist/blocklist from environment
        allowlist_str = os.getenv("SCOUT_ALLOWLIST", "").strip()
        allowlist = [h.strip() for h in allowlist_str.split(",") if h.strip()] if allowlist_str else None

        blocklist_str = os.getenv("SCOUT_BLOCKLIST", "").strip()
        blocklist = [h.strip() for h in blocklist_str.split(",") if h.strip()] if blocklist_str else None

        parser = SSHConfigParser(
            allowlist=allowlist,
            blocklist=blocklist,
        )

        host_keys = HostKeyVerifier(
            known_hosts_path=os.getenv("SCOUT_KNOWN_HOSTS"),
            strict_checking=cls._get_bool_env("SCOUT_STRICT_HOST_KEY_CHECKING", True),
        )

        return cls(
            settings=settings,
            parser=parser,
            host_keys=host_keys,
        )

    @classmethod
    def from_ssh_config(
        cls,
        ssh_config_path: Path | str | None = None,
        allowlist: list[str] | None = None,
        blocklist: list[str] | None = None,
    ) -> "Config":
        """Create config from SSH config path (backward compatibility).

        Deprecated: Use from_env() or Config(...) constructor directly.

        Args:
            ssh_config_path: Path to SSH config file
            allowlist: List of hosts to include
            blocklist: List of hosts to exclude

        Returns:
            Configured instance with default settings
        """
        settings = Settings.from_env()
        parser = SSHConfigParser(
            config_path=ssh_config_path,
            allowlist=allowlist,
            blocklist=blocklist,
        )
        # Disable strict host key checking for backward compatibility
        host_keys = HostKeyVerifier(known_hosts_path=None, strict_checking=False)
        return cls(settings=settings, parser=parser, host_keys=host_keys)

    @staticmethod
    def _get_bool_env(key: str, default: bool) -> bool:
        """Get boolean from environment.

        Args:
            key: Environment variable key
            default: Default value

        Returns:
            Boolean value
        """
        value = os.getenv(key)
        if value is None:
            return default
        return value.lower() != "false"

    def get_hosts(self) -> dict[str, SSHHost]:
        """Get SSH hosts from config.

        Lazy loads and caches hosts on first call.

        Returns:
            Dictionary of hostname to SSHHost
        """
        if not self._hosts_cache:
            self._hosts_cache = self.parser.parse()
        return self._hosts_cache

    def get_host(self, name: str) -> SSHHost | None:
        """Get host by name.

        Args:
            name: Host name to look up

        Returns:
            SSHHost if found, None otherwise
        """
        return self.get_hosts().get(name)

    # Delegate to settings for convenience
    @property
    def max_file_size(self) -> int:
        """Maximum file size in bytes."""
        return self.settings.max_file_size

    @property
    def command_timeout(self) -> int:
        """Command timeout in seconds."""
        return self.settings.command_timeout

    @property
    def idle_timeout(self) -> int:
        """Connection idle timeout in seconds."""
        return self.settings.idle_timeout

    @property
    def max_pool_size(self) -> int:
        """Maximum connection pool size."""
        return self.settings.max_pool_size

    @property
    def transport(self) -> str:
        """Transport type (http or stdio)."""
        return self.settings.transport

    @property
    def http_host(self) -> str:
        """HTTP server bind address."""
        return self.settings.http_host

    @property
    def http_port(self) -> int:
        """HTTP server port."""
        return self.settings.http_port

    @property
    def enable_ui(self) -> bool:
        """Whether MCP-UI is enabled."""
        return self.settings.enable_ui

    @property
    def known_hosts_path(self) -> str | None:
        """Path to known_hosts file or None if disabled."""
        return self.host_keys.get_known_hosts_path()

    @property
    def strict_host_key_checking(self) -> bool:
        """Whether to reject unknown host keys."""
        return self.host_keys.strict_checking

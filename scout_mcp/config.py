"""Configuration management for Scout MCP."""

import logging
import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

from scout_mcp.models import SSHHost

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Scout MCP configuration."""

    ssh_config_path: Path = field(
        default_factory=lambda: Path.home() / ".ssh" / "config"
    )
    allowlist: list[str] = field(default_factory=list)
    blocklist: list[str] = field(default_factory=list)
    max_file_size: int = 1_048_576  # 1MB
    command_timeout: int = 30
    idle_timeout: int = 60
    # Transport configuration
    transport: str = "http"  # "http" or "stdio"
    http_host: str = "0.0.0.0"
    http_port: int = 8000

    _hosts: dict[str, SSHHost] = field(default_factory=dict, init=False, repr=False)
    _parsed: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        """Apply environment variable overrides.

        Supports both SCOUT_* (preferred) and legacy MCP_CAT_* prefixes.
        SCOUT_* takes precedence if both are set.
        """
        import os
        from contextlib import suppress

        # Helper to get env var with fallback to legacy prefix
        def get_env_int(scout_key: str, legacy_key: str) -> int | None:
            # SCOUT_* takes precedence
            if val := os.getenv(scout_key):
                with suppress(ValueError):
                    return int(val)
            # Fall back to legacy MCP_CAT_*
            if val := os.getenv(legacy_key):
                with suppress(ValueError):
                    return int(val)
            return None

        val = get_env_int("SCOUT_MAX_FILE_SIZE", "MCP_CAT_MAX_FILE_SIZE")
        if val is not None:
            self.max_file_size = val

        val = get_env_int("SCOUT_COMMAND_TIMEOUT", "MCP_CAT_COMMAND_TIMEOUT")
        if val is not None:
            self.command_timeout = val

        val = get_env_int("SCOUT_IDLE_TIMEOUT", "MCP_CAT_IDLE_TIMEOUT")
        if val is not None:
            self.idle_timeout = val

        # Transport configuration
        transport = os.getenv("SCOUT_TRANSPORT", "").lower()
        if transport in ("http", "stdio"):
            self.transport = transport

        if http_host := os.getenv("SCOUT_HTTP_HOST"):
            self.http_host = http_host

        http_port = get_env_int("SCOUT_HTTP_PORT", "")
        if http_port is not None:
            self.http_port = http_port

        logger.debug(
            "Config initialized: transport=%s, max_file_size=%d, "
            "command_timeout=%d, idle_timeout=%d",
            self.transport,
            self.max_file_size,
            self.command_timeout,
            self.idle_timeout,
        )

    def _parse_ssh_config(self) -> None:
        """Parse SSH config file and populate hosts."""
        if self._parsed:
            return

        if not self.ssh_config_path.exists():
            logger.warning("SSH config not found: %s", self.ssh_config_path)
            self._parsed = True
            return

        try:
            content = self.ssh_config_path.read_text()
            logger.debug("Reading SSH config from %s", self.ssh_config_path)
        except (OSError, PermissionError) as e:
            # Treat unreadable config as empty
            logger.warning("Cannot read SSH config %s: %s", self.ssh_config_path, e)
            self._parsed = True
            return

        current_host: str | None = None
        current_data: dict[str, str] = {}

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Match Host directive
            host_match = re.match(r"^Host\s+(\S+)", line, re.IGNORECASE)
            if host_match:
                # Save previous host if exists
                if current_host and current_data.get("hostname"):
                    try:
                        port = int(current_data.get("port", "22"))
                    except ValueError:
                        port = 22
                    self._hosts[current_host] = SSHHost(
                        name=current_host,
                        hostname=current_data.get("hostname", ""),
                        user=current_data.get("user", "root"),
                        port=port,
                        identity_file=current_data.get("identityfile"),
                    )
                current_host = host_match.group(1)
                current_data = {}
                continue

            # Match key-value pairs
            kv_match = re.match(r"^(\w+)\s+(.+)$", line)
            if kv_match and current_host:
                key = kv_match.group(1).lower()
                value = kv_match.group(2)
                current_data[key] = value

        # Save last host
        if current_host and current_data.get("hostname"):
            try:
                port = int(current_data.get("port", "22"))
            except ValueError:
                port = 22
            self._hosts[current_host] = SSHHost(
                name=current_host,
                hostname=current_data.get("hostname", ""),
                user=current_data.get("user", "root"),
                port=port,
                identity_file=current_data.get("identityfile"),
            )

        self._parsed = True
        logger.debug("Parsed %d SSH host(s) from config", len(self._hosts))

    def _is_host_allowed(self, name: str) -> bool:
        """Check if host passes allowlist/blocklist filters."""
        # Allowlist takes precedence
        if self.allowlist:
            return any(fnmatch(name, pattern) for pattern in self.allowlist)

        # Check blocklist
        if self.blocklist:
            return not any(fnmatch(name, pattern) for pattern in self.blocklist)

        return True

    def get_hosts(self) -> dict[str, SSHHost]:
        """Get all available SSH hosts after filtering."""
        self._parse_ssh_config()
        return {
            name: host
            for name, host in self._hosts.items()
            if self._is_host_allowed(name)
        }

    def get_host(self, name: str) -> SSHHost | None:
        """Get a specific host by name."""
        hosts = self.get_hosts()
        return hosts.get(name)

"""Configuration management for Scout MCP."""

import logging
import os
import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

from scout_mcp.models import SSHHost
from scout_mcp.utils.hostname import is_localhost_target

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
    max_pool_size: int = 100  # Maximum concurrent SSH connections
    # Transport configuration
    transport: str = "http"  # "http" or "stdio"
    http_host: str = "0.0.0.0"
    http_port: int = 8000
    # UI configuration
    enable_ui: bool = False  # Enable MCP-UI interactive HTML responses

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

        val = get_env_int("SCOUT_MAX_POOL_SIZE", "")
        if val is not None:
            if val <= 0:
                logger.warning(
                    "SCOUT_MAX_POOL_SIZE must be > 0, got %d. Using default: %d",
                    val,
                    self.max_pool_size,
                )
            else:
                self.max_pool_size = val

        # Transport configuration
        transport = os.getenv("SCOUT_TRANSPORT", "").lower()
        if transport in ("http", "stdio"):
            self.transport = transport

        if http_host := os.getenv("SCOUT_HTTP_HOST"):
            self.http_host = http_host

        http_port = get_env_int("SCOUT_HTTP_PORT", "")
        if http_port is not None:
            self.http_port = http_port

        # UI configuration
        if ui_enabled := os.getenv("SCOUT_ENABLE_UI", "").lower():
            self.enable_ui = ui_enabled in ("true", "1", "yes", "on")

        logger.debug(
            "Config initialized: transport=%s, max_file_size=%d, "
            "command_timeout=%d, idle_timeout=%d, max_pool_size=%d",
            self.transport,
            self.max_file_size,
            self.command_timeout,
            self.idle_timeout,
            self.max_pool_size,
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
        global_defaults: dict[str, str] = {}

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Match Host directive
            host_match = re.match(r"^Host\s+(\S+)", line, re.IGNORECASE)
            if host_match:
                # Save previous host if exists
                if (
                    current_host
                    and current_host != "*"
                    and current_data.get("hostname")
                ):
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
                        is_localhost=is_localhost_target(current_host),
                    )
                current_host = host_match.group(1)
                # Start with global defaults for each host (except Host *)
                current_data = global_defaults.copy() if current_host != "*" else {}
                continue

            # Match key-value pairs
            kv_match = re.match(r"^(\w+)\s+(.+)$", line)
            if kv_match and current_host:
                key = kv_match.group(1).lower()
                value = kv_match.group(2)
                # Expand tilde in identity file paths
                if key == "identityfile":
                    value = os.path.expanduser(value)
                current_data[key] = value
                # Save to global defaults if this is Host *
                if current_host == "*":
                    global_defaults[key] = value

        # Save last host
        if current_host and current_host != "*" and current_data.get("hostname"):
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
                is_localhost=is_localhost_target(current_host),
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

    @property
    def known_hosts_path(self) -> str | None:
        """Path to known_hosts file, or None to disable verification.

        Environment: SCOUT_KNOWN_HOSTS
        Default: ~/.ssh/known_hosts (must exist)
        Special value: "none" disables verification (NOT RECOMMENDED - MITM vulnerable)

        Returns:
            Path to known_hosts file or None if explicitly disabled

        Raises:
            FileNotFoundError: If known_hosts file doesn't exist (fail-closed security)
        """
        value = os.getenv("SCOUT_KNOWN_HOSTS", "").strip()

        # Explicit disable with critical security warning
        if value.lower() == "none":
            logger.critical(
                "SSH host key verification DISABLED (SCOUT_KNOWN_HOSTS=none). "
                "This makes connections vulnerable to man-in-the-middle attacks. "
                "Only use this in trusted networks or for testing. "
                "See SECURITY.md for secure configuration."
            )
            return None

        # Custom path specified
        if value:
            custom_path = Path(os.path.expanduser(value))
            if not custom_path.exists():
                raise FileNotFoundError(
                    f"SSH host key verification required but specified known_hosts file not found: {custom_path}\n\n"
                    f"To fix this:\n"
                    f"1. Create the file: touch {custom_path}\n"
                    f"2. Add host keys: ssh-keyscan <hostname> >> {custom_path}\n"
                    f"3. Or use default location: unset SCOUT_KNOWN_HOSTS\n"
                    f"4. Or disable verification (NOT RECOMMENDED): export SCOUT_KNOWN_HOSTS=none\n\n"
                    f"See SECURITY.md for more information."
                )
            return str(custom_path)

        # Default to standard location - must exist (fail-closed)
        default = Path.home() / ".ssh" / "known_hosts"
        if not default.exists():
            raise FileNotFoundError(
                f"SSH host key verification required but ~/.ssh/known_hosts not found.\n\n"
                f"To fix this:\n"
                f"1. Add host keys: ssh-keyscan <hostname> >> ~/.ssh/known_hosts\n"
                f"2. Or connect once: ssh <hostname> (answer 'yes' to add key)\n"
                f"3. Or disable verification (NOT RECOMMENDED): export SCOUT_KNOWN_HOSTS=none\n\n"
                f"See SECURITY.md for more information."
            )
        return str(default)

    @property
    def strict_host_key_checking(self) -> bool:
        """Whether to reject unknown host keys.

        Environment: SCOUT_STRICT_HOST_KEY_CHECKING
        Default: True (reject unknown hosts)

        Returns:
            True if strict checking is enabled
        """
        return os.getenv("SCOUT_STRICT_HOST_KEY_CHECKING", "true").lower() != "false"

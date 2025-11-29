"""Configuration management for Scout MCP."""

import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

from scout_mcp.models import SSHHost


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

    _hosts: dict[str, SSHHost] = field(default_factory=dict, init=False, repr=False)
    _parsed: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        """Apply environment variable overrides."""
        import os
        from contextlib import suppress

        if val := os.getenv("MCP_CAT_MAX_FILE_SIZE"):
            with suppress(ValueError):
                self.max_file_size = int(val)

        if val := os.getenv("MCP_CAT_COMMAND_TIMEOUT"):
            with suppress(ValueError):
                self.command_timeout = int(val)

        if val := os.getenv("MCP_CAT_IDLE_TIMEOUT"):
            with suppress(ValueError):
                self.idle_timeout = int(val)

    def _parse_ssh_config(self) -> None:
        """Parse SSH config file and populate hosts."""
        if self._parsed:
            return

        if not self.ssh_config_path.exists():
            self._parsed = True
            return

        try:
            content = self.ssh_config_path.read_text()
        except (OSError, PermissionError):
            # Treat unreadable config as empty
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

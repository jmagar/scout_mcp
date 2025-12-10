"""SSH config file parser.

Reads ~/.ssh/config and extracts host definitions with allowlist/blocklist filtering.
"""

import logging
import os
import re
from pathlib import Path

from scout_mcp.models import SSHHost
from scout_mcp.utils.hostname import is_localhost_target

logger = logging.getLogger(__name__)


class SSHConfigParser:
    """Parser for SSH config files.

    Reads SSH config format and extracts host definitions.
    Supports allowlist/blocklist filtering.
    """

    def __init__(
        self,
        config_path: Path | str | None = None,
        allowlist: list[str] | None = None,
        blocklist: list[str] | None = None,
    ):
        """Initialize SSH config parser.

        Args:
            config_path: Path to SSH config file (default: ~/.ssh/config)
            allowlist: Only include these hosts (if set)
            blocklist: Exclude these hosts
        """
        if config_path is None:
            config_path = Path.home() / ".ssh" / "config"

        self.config_path = Path(config_path)
        self.allowlist = set(allowlist) if allowlist else None
        self.blocklist = set(blocklist) if blocklist else set()

    def parse(self) -> dict[str, SSHHost]:
        """Parse SSH config and return host definitions.

        Returns:
            Dictionary mapping hostname to SSHHost objects
        """
        if not self.config_path.exists():
            logger.warning("SSH config not found: %s", self.config_path)
            return {}

        try:
            content = self.config_path.read_text()
            logger.debug("Reading SSH config from %s", self.config_path)
        except (OSError, PermissionError) as e:
            logger.warning("Cannot read SSH config %s: %s", self.config_path, e)
            return {}

        hosts: dict[str, SSHHost] = {}
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
                    if self._is_host_allowed(current_host):
                        try:
                            port = int(current_data.get("port", "22"))
                        except ValueError:
                            port = 22
                        hosts[current_host] = SSHHost(
                            name=current_host,
                            hostname=current_data.get("hostname", ""),
                            user=current_data.get("user", "root"),
                            port=port,
                            identity_file=current_data.get("identityfile"),
                            is_localhost=is_localhost_target(current_host),
                        )
                current_host = host_match.group(1)
                # Skip wildcards
                if "*" in current_host or "?" in current_host:
                    current_host = "*"
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
            if self._is_host_allowed(current_host):
                try:
                    port = int(current_data.get("port", "22"))
                except ValueError:
                    port = 22
                hosts[current_host] = SSHHost(
                    name=current_host,
                    hostname=current_data.get("hostname", ""),
                    user=current_data.get("user", "root"),
                    port=port,
                    identity_file=current_data.get("identityfile"),
                    is_localhost=is_localhost_target(current_host),
                )

        logger.info("Parsed %d hosts from %s", len(hosts), self.config_path)
        return hosts

    def _is_host_allowed(self, name: str) -> bool:
        """Check if host passes allowlist/blocklist filters.

        Args:
            name: Host name to check

        Returns:
            True if host is allowed
        """
        # Allowlist takes precedence
        if self.allowlist:
            return name in self.allowlist

        # Check blocklist
        if self.blocklist:
            return name not in self.blocklist

        return True

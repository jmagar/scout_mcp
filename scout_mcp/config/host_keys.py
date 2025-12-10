"""SSH host key verification.

Manages known_hosts file for MITM prevention.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class HostKeyVerifier:
    """SSH host key verification manager.

    Handles known_hosts configuration for MITM prevention.
    """

    def __init__(
        self,
        known_hosts_path: str | None = None,
        strict_checking: bool = True,
    ):
        """Initialize host key verifier.

        Args:
            known_hosts_path: Path to known_hosts file or 'none' to disable
            strict_checking: Reject unknown host keys

        Raises:
            FileNotFoundError: If strict mode and file missing
        """
        self.strict_checking = strict_checking
        self._known_hosts = self._resolve_known_hosts(known_hosts_path)

    def _resolve_known_hosts(self, env_value: str | None) -> str | None:
        """Resolve known_hosts path with security defaults.

        Returns:
            Path to known_hosts file or None to disable verification

        Raises:
            FileNotFoundError: If strict mode and file missing
        """
        # Explicit disable
        if env_value and env_value.lower() == "none":
            logger.critical(
                "⚠️  SSH HOST KEY VERIFICATION DISABLED ⚠️\n"
                "This is INSECURE and vulnerable to MITM attacks.\n"
                "Only use in trusted networks for testing."
            )
            return None

        # Custom path
        if env_value:
            path = Path(os.path.expanduser(env_value))
            if not path.exists():
                if self.strict_checking:
                    raise FileNotFoundError(
                        f"SSH host key verification required but specified "
                        f"known_hosts file not found: {path}\n\n"
                        f"To fix this:\n"
                        f"1. Create the file: touch {path}\n"
                        f"2. Add host keys: ssh-keyscan <hostname> >> {path}\n"
                        f"3. Or use default location: unset SCOUT_KNOWN_HOSTS\n"
                        f"4. Or disable verification (NOT RECOMMENDED): "
                        f"SCOUT_KNOWN_HOSTS=none"
                    )
                else:
                    logger.warning(
                        "known_hosts not found at %s, verification disabled. "
                        "This is insecure!",
                        path,
                    )
                    return None
            return str(path)

        # Default path - fail closed if strict
        default = Path.home() / ".ssh" / "known_hosts"
        if not default.exists():
            if self.strict_checking:
                raise FileNotFoundError(
                    f"SSH host key verification required but "
                    f"known_hosts not found at {default}.\n\n"
                    f"To fix this:\n"
                    f"1. Add host keys: ssh-keyscan <hostname> >> {default}\n"
                    f"2. Or connect once: ssh <hostname> "
                    f"(answer 'yes' to add key)\n"
                    f"3. Or disable verification (NOT RECOMMENDED): "
                    f"export SCOUT_KNOWN_HOSTS=none"
                )
            else:
                logger.warning(
                    "known_hosts not found at %s, verification disabled. "
                    "This is insecure!",
                    default,
                )
                return None

        return str(default)

    def get_known_hosts_path(self) -> str | None:
        """Get path to known_hosts file.

        Returns:
            Path string or None if verification disabled
        """
        return self._known_hosts

    def is_enabled(self) -> bool:
        """Check if host key verification is enabled.

        Returns:
            True if verification is enabled
        """
        return self._known_hosts is not None

"""Scout tool URI parsing and intent detection."""

from dataclasses import dataclass


@dataclass
class ScoutTarget:
    """Parsed scout target."""

    host: str | None
    path: str = ""
    is_hosts_command: bool = False


def parse_target(target: str) -> ScoutTarget:
    """Parse a scout target URI.

    Formats:
        - "hosts" -> list available hosts
        - "hostname:/path" -> target a specific path on host

    Returns:
        ScoutTarget with parsed components.

    Raises:
        ValueError: If target format is invalid.
    """
    target = target.strip()

    # Special case: hosts command
    if target.lower() == "hosts":
        return ScoutTarget(host=None, is_hosts_command=True)

    # Parse host:/path format
    if ":" not in target:
        raise ValueError(
            f"Invalid target '{target}'. Expected 'host:/path' or 'hosts'"
        )

    # Split on first colon only (path may contain colons)
    parts = target.split(":", 1)
    host = parts[0].strip()
    path = parts[1].strip() if len(parts) > 1 else ""

    if not host:
        raise ValueError("Host cannot be empty")

    if not path:
        raise ValueError("Path cannot be empty")

    return ScoutTarget(host=host, path=path)

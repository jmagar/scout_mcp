"""Scout target data models."""

from dataclasses import dataclass


@dataclass
class ScoutTarget:
    """Parsed scout target."""

    host: str | None
    path: str = ""
    is_hosts_command: bool = False

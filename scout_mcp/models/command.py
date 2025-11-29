"""Command execution data models."""

from dataclasses import dataclass


@dataclass
class CommandResult:
    """Result of a remote command execution."""

    output: str
    error: str
    returncode: int

"""Broadcast operation results for multi-host operations."""

from dataclasses import dataclass


@dataclass
class BroadcastResult:
    """Result from a single host in a broadcast operation."""

    host: str
    path: str
    output: str
    success: bool
    error: str | None = None

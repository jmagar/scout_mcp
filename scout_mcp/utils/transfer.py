"""Transfer path detection and strategy selection."""

from dataclasses import dataclass
from enum import Enum


class TransferStrategy(Enum):
    """Transfer strategy based on endpoint locations."""

    LOCAL_TO_REMOTE = "local_to_remote"
    REMOTE_TO_LOCAL = "remote_to_local"
    REMOTE_TO_REMOTE_RELAY = "remote_to_remote_relay"


@dataclass
class TransferPath:
    """Resolved transfer path with strategy."""

    strategy: TransferStrategy
    source_host: str | None  # None if local
    target_host: str | None  # None if local
    source_path: str
    target_path: str


def determine_transfer_strategy(
    source_host: str | None,
    target_host: str | None,
    current_hostname: str,
) -> TransferPath:
    """Determine optimal transfer strategy based on endpoint locations.

    Args:
        source_host: Source hostname (None if local)
        target_host: Target hostname (None if local)
        current_hostname: Hostname of machine running MCP server

    Returns:
        TransferPath with resolved strategy and optimized endpoints.

    Raises:
        ValueError: If source and target are the same host.

    Examples:
        >>> determine_transfer_strategy(None, "remote1", "localhost")
        TransferPath(strategy=LOCAL_TO_REMOTE, source_host=None, target_host="remote1")

        >>> determine_transfer_strategy("remote1", "remote2", "localhost")
        TransferPath(strategy=REMOTE_TO_REMOTE_RELAY, ...)

        >>> determine_transfer_strategy("tootie", "remote1", "tootie")
        TransferPath(strategy=LOCAL_TO_REMOTE, source_host=None, target_host="remote1")
    """
    # Validate not same host
    if source_host and target_host and source_host == target_host:
        raise ValueError(
            f"Source and target cannot be the same host: {source_host}"
        )

    # Optimize: if source is current host, treat as local
    if source_host == current_hostname:
        source_host = None

    # Optimize: if target is current host, treat as local
    if target_host == current_hostname:
        target_host = None

    # Determine strategy
    if source_host is None and target_host is not None:
        strategy = TransferStrategy.LOCAL_TO_REMOTE
    elif source_host is not None and target_host is None:
        strategy = TransferStrategy.REMOTE_TO_LOCAL
    elif source_host is not None and target_host is not None:
        strategy = TransferStrategy.REMOTE_TO_REMOTE_RELAY
    else:
        raise ValueError("Cannot transfer from local to local")

    # Return without paths (will be added by caller)
    return TransferPath(
        strategy=strategy,
        source_host=source_host,
        target_host=target_host,
        source_path="",  # Placeholder
        target_path="",  # Placeholder
    )

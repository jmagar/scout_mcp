"""Path and input validation utilities."""

import os
import re
from typing import Final


class PathTraversalError(ValueError):
    """Attempted path traversal detected."""

    pass


# Path traversal patterns to reject
TRAVERSAL_PATTERNS: Final[list[str]] = [
    r"\.\./",  # ../
    r"/\.\.",  # /..
    r"^\.\.$",  # Just ..
    r"^\.\./",  # Starts with ../
]


def validate_path(path: str, allow_absolute: bool = True) -> str:
    """Validate a remote path for safety.

    Checks for path traversal attempts and suspicious patterns.

    Args:
        path: The path to validate
        allow_absolute: Whether to allow absolute paths (default: True)

    Returns:
        Normalized path

    Raises:
        PathTraversalError: If path contains traversal sequences
        ValueError: If path is invalid
    """
    if not path:
        raise ValueError("Path cannot be empty")

    # Check for null bytes (can bypass validation in some systems)
    if "\x00" in path:
        raise PathTraversalError(f"Path contains null byte: {path!r}")

    # Check for explicit traversal sequences before normalization
    for pattern in TRAVERSAL_PATTERNS:
        if re.search(pattern, path):
            raise PathTraversalError(f"Path traversal not allowed: {path}")

    # Normalize the path
    try:
        normalized = os.path.normpath(path)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid path: {path}") from e

    # After normalization, check if we escaped the root
    if normalized.startswith(".."):
        raise PathTraversalError(f"Path escapes root after normalization: {path}")

    # Check absolute path policy
    if not allow_absolute and os.path.isabs(normalized):
        raise ValueError(f"Absolute paths not allowed: {path}")

    # Allow ~ paths as-is for remote expansion
    if path.startswith("~"):
        return path

    return normalized


def validate_host(host: str) -> str:
    """Validate a host name.

    Args:
        host: The host name to validate

    Returns:
        Validated host name

    Raises:
        ValueError: If host name is invalid
    """
    if not host:
        raise ValueError("Host cannot be empty")

    # Basic hostname validation
    if len(host) > 253:
        raise ValueError(f"Host name too long: {len(host)} chars")

    # Check for suspicious characters that could enable injection
    suspicious_chars = ["/", "\\", ";", "&", "|", "$", "`", "\n", "\r", "\x00"]
    for char in suspicious_chars:
        if char in host:
            raise ValueError(f"Host contains invalid characters: {host!r}")

    return host

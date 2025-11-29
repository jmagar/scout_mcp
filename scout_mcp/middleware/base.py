"""Base middleware classes for Scout MCP."""

import logging

from fastmcp.server.middleware import Middleware


class ScoutMiddleware(Middleware):
    """Base middleware with common functionality for Scout MCP.

    Provides:
        - Configurable logger
        - Common initialization patterns
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """Initialize middleware.

        Args:
            logger: Optional custom logger. Defaults to module logger.
        """
        self.logger = logger or logging.getLogger(__name__)

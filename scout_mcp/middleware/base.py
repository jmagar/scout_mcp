"""Base middleware classes for Scout MCP."""

import logging
from abc import ABC, abstractmethod
from typing import Any

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


class MCPMiddleware(ABC):
    """Base class for MCP-layer middleware.

    Middleware processes requests/responses at the MCP protocol layer,
    independent of transport mechanism (HTTP, STDIO, etc.).
    """

    @abstractmethod
    async def process_request(
        self,
        method: str,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Process request before tool/resource handler.

        Args:
            method: MCP method name (e.g., "tools/call")
            params: Request parameters
            context: Transport-specific context (client IP, etc.)

        Returns:
            Modified context dictionary

        Raises:
            Exception: To reject request
        """
        pass

    async def process_response(
        self,
        method: str,
        response: Any,
        context: dict[str, Any],
    ) -> Any:
        """Process response after tool/resource handler.

        Args:
            method: MCP method name
            response: Handler response
            context: Transport-specific context

        Returns:
            Modified response
        """
        return response

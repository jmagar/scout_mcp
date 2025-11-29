"""Logging middleware for request/response tracking."""

import json
import logging
from typing import Any

from fastmcp.server.middleware import MiddlewareContext

from scout_mcp.middleware.base import ScoutMiddleware


class LoggingMiddleware(ScoutMiddleware):
    """Middleware that logs MCP requests and responses.

    Provides comprehensive request/response logging with configurable
    detail levels and payload inclusion.

    Example:
        >>> middleware = LoggingMiddleware(include_payloads=True)
        >>> mcp.add_middleware(middleware)
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
        include_payloads: bool = False,
        max_payload_length: int = 1000,
    ) -> None:
        """Initialize logging middleware.

        Args:
            logger: Optional custom logger.
            include_payloads: Whether to log request/response payloads.
            max_payload_length: Maximum payload length before truncation.
        """
        super().__init__(logger=logger)
        self.include_payloads = include_payloads
        self.max_payload_length = max_payload_length

    def _truncate(self, data: Any) -> str:
        """Truncate data to max payload length.

        Args:
            data: Data to serialize and truncate.

        Returns:
            Truncated string representation.
        """
        try:
            text = json.dumps(data, default=str)
        except (TypeError, ValueError):
            text = str(data)

        if len(text) > self.max_payload_length:
            return text[: self.max_payload_length] + "... [truncated]"
        return text

    async def on_message(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Log incoming requests and outgoing responses.

        Args:
            context: The middleware context with request info.
            call_next: Function to call the next handler.

        Returns:
            The result from the next handler.
        """
        method = context.method
        source = getattr(context, "source", "unknown")

        # Log incoming request
        self.logger.info("Received %s from %s", method, source)

        if self.include_payloads and hasattr(context.message, "arguments"):
            payload = getattr(context.message, "arguments", None)
            if payload:
                self.logger.debug(
                    "Request payload: %s",
                    self._truncate(payload),
                )

        try:
            result = await call_next(context)

            # Log successful completion
            self.logger.info("Completed %s", method)

            if self.include_payloads and result is not None:
                self.logger.debug(
                    "Response payload: %s",
                    self._truncate(result),
                )

            return result

        except Exception as e:
            self.logger.error(
                "Failed %s: %s: %s",
                method,
                type(e).__name__,
                str(e),
            )
            raise

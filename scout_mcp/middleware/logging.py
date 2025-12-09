"""Logging middleware for request/response tracking."""

import json
import logging
import time
from typing import Any

from fastmcp.server.middleware import MiddlewareContext

from scout_mcp.middleware.base import ScoutMiddleware


class LoggingMiddleware(ScoutMiddleware):
    """Middleware that logs MCP requests and responses with rich detail.

    Provides comprehensive request/response logging including:
    - Tool names and arguments
    - Resource URIs being accessed
    - Request duration (integrated timing)
    - Response size/type

    This middleware combines logging AND timing for cleaner output.
    Use this INSTEAD of TimingMiddleware for a unified log format.

    Example:
        >>> middleware = LoggingMiddleware(include_payloads=True)
        >>> mcp.add_middleware(middleware)
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
        include_payloads: bool = False,
        max_payload_length: int = 1000,
        slow_threshold_ms: float = 1000.0,
    ) -> None:
        """Initialize logging middleware.

        Args:
            logger: Optional custom logger.
            include_payloads: Whether to log request/response payloads.
            max_payload_length: Maximum payload length before truncation.
            slow_threshold_ms: Threshold in ms for slow request warnings.
        """
        super().__init__(logger=logger)
        self.include_payloads = include_payloads
        self.max_payload_length = max_payload_length
        self.slow_threshold_ms = slow_threshold_ms

    def _truncate(self, data: Any) -> str:
        """Truncate data to max payload length."""
        try:
            text = json.dumps(data, default=str)
        except (TypeError, ValueError):
            text = str(data)

        if len(text) > self.max_payload_length:
            return text[: self.max_payload_length] + "... [truncated]"
        return text

    def _format_args(self, args: dict[str, Any] | None) -> str:
        """Format tool arguments for logging."""
        if not args:
            return "()"
        parts = []
        for key, value in args.items():
            if isinstance(value, str) and len(value) > 50:
                value = value[:50] + "..."
            parts.append(f"{key}={value!r}")
        return f"({', '.join(parts)})"

    def _format_duration(self, duration_ms: float) -> str:
        """Format duration with slow indicator if needed."""
        if duration_ms >= self.slow_threshold_ms:
            return f"{duration_ms:.1f}ms SLOW!"
        return f"{duration_ms:.1f}ms"

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Log tool calls with name, arguments, and timing."""
        start = time.perf_counter()
        tool_name = getattr(context.message, "name", "unknown")
        args = getattr(context.message, "arguments", None)

        self.logger.info(
            ">>> TOOL: %s%s",
            tool_name,
            self._format_args(args),
        )

        if self.include_payloads and args:
            self.logger.debug("    Args: %s", self._truncate(args))

        try:
            result = await call_next(context)
            duration_ms = (time.perf_counter() - start) * 1000

            # Get result summary
            result_summary = self._summarize_result(result)

            log_level = (
                logging.WARNING
                if duration_ms >= self.slow_threshold_ms
                else logging.INFO
            )
            self.logger.log(
                log_level,
                "<<< TOOL: %s -> %s [%s]",
                tool_name,
                result_summary,
                self._format_duration(duration_ms),
            )

            if self.include_payloads and result is not None:
                self.logger.debug("    Result: %s", self._truncate(result))

            return result

        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            self.logger.error(
                "!!! TOOL: %s -> %s: %s [%s]",
                tool_name,
                type(e).__name__,
                str(e),
                self._format_duration(duration_ms),
            )
            raise

    async def on_read_resource(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Log resource reads with URI and timing."""
        start = time.perf_counter()
        uri = getattr(context.message, "uri", "unknown")

        self.logger.info(">>> RESOURCE: %s", uri)

        try:
            result = await call_next(context)
            duration_ms = (time.perf_counter() - start) * 1000

            result_summary = self._summarize_result(result)

            log_level = (
                logging.WARNING
                if duration_ms >= self.slow_threshold_ms
                else logging.INFO
            )
            self.logger.log(
                log_level,
                "<<< RESOURCE: %s -> %s [%s]",
                uri,
                result_summary,
                self._format_duration(duration_ms),
            )

            return result

        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            self.logger.error(
                "!!! RESOURCE: %s -> %s: %s [%s]",
                uri,
                type(e).__name__,
                str(e),
                self._format_duration(duration_ms),
            )
            raise

    async def on_list_tools(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Log tool listing requests."""
        start = time.perf_counter()
        self.logger.info(">>> LIST TOOLS")

        try:
            result = await call_next(context)
            duration_ms = (time.perf_counter() - start) * 1000

            # Count tools if possible
            tool_count: int | str = "?"
            if hasattr(result, "tools"):
                tool_count = len(result.tools)
            elif isinstance(result, (list, tuple)):
                tool_count = len(result)

            self.logger.info(
                "<<< LIST TOOLS -> %s tool(s) [%s]",
                tool_count,
                self._format_duration(duration_ms),
            )
            return result

        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            self.logger.error(
                "!!! LIST TOOLS -> %s: %s [%s]",
                type(e).__name__,
                str(e),
                self._format_duration(duration_ms),
            )
            raise

    async def on_list_resources(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Log resource listing requests."""
        start = time.perf_counter()
        self.logger.info(">>> LIST RESOURCES")

        try:
            result = await call_next(context)
            duration_ms = (time.perf_counter() - start) * 1000

            # Count resources if possible
            resource_count: int | str = "?"
            if hasattr(result, "resources"):
                resource_count = len(result.resources)
            elif isinstance(result, (list, tuple)):
                resource_count = len(result)

            self.logger.info(
                "<<< LIST RESOURCES -> %s resource(s) [%s]",
                resource_count,
                self._format_duration(duration_ms),
            )
            return result

        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            self.logger.error(
                "!!! LIST RESOURCES -> %s: %s [%s]",
                type(e).__name__,
                str(e),
                self._format_duration(duration_ms),
            )
            raise

    async def on_message(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Log generic messages that aren't caught by specific handlers."""
        start = time.perf_counter()
        method = context.method

        # Skip methods that have dedicated handlers
        if method in (
            "tools/call",
            "resources/read",
            "tools/list",
            "resources/list",
        ):
            return await call_next(context)

        self.logger.debug(">>> MCP: %s", method)

        try:
            result = await call_next(context)
            duration_ms = (time.perf_counter() - start) * 1000

            self.logger.debug(
                "<<< MCP: %s [%s]",
                method,
                self._format_duration(duration_ms),
            )
            return result

        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            self.logger.error(
                "!!! MCP: %s -> %s: %s [%s]",
                method,
                type(e).__name__,
                str(e),
                self._format_duration(duration_ms),
            )
            raise

    def _summarize_result(self, result: Any) -> str:
        """Create a brief summary of a result for logging."""
        if result is None:
            return "null"

        # Handle string results
        if isinstance(result, str):
            lines = result.count("\n") + 1
            chars = len(result)
            if lines > 1:
                return f"{chars} chars, {lines} lines"
            return f"{chars} chars"

        # Handle list/tuple results
        if isinstance(result, (list, tuple)):
            return f"{len(result)} items"

        # Handle dict results
        if isinstance(result, dict):
            return f"{len(result)} keys"

        # Handle objects with content attribute (MCP responses)
        if hasattr(result, "content"):
            content = result.content
            if isinstance(content, (list, tuple)):
                return f"{len(content)} content item(s)"
            return "content"

        return type(result).__name__

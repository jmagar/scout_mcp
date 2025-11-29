"""Timing middleware for request duration tracking."""

import logging
import time
from typing import Any

from fastmcp.server.middleware import MiddlewareContext

from scout_mcp.middleware.base import ScoutMiddleware


class TimingMiddleware(ScoutMiddleware):
    """Middleware that logs execution time of MCP requests.

    Measures duration of each request and logs timing information.
    Optionally warns on slow requests exceeding a threshold.

    Example:
        >>> middleware = TimingMiddleware(slow_threshold_ms=100.0)
        >>> mcp.add_middleware(middleware)
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
        slow_threshold_ms: float = 1000.0,
    ) -> None:
        """Initialize timing middleware.

        Args:
            logger: Optional custom logger.
            slow_threshold_ms: Threshold in milliseconds for slow request warnings.
                Defaults to 1000ms (1 second).
        """
        super().__init__(logger=logger)
        self.slow_threshold_ms = slow_threshold_ms

    async def on_request(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Time request execution and log results.

        Args:
            context: The middleware context with request info.
            call_next: Function to call the next handler.

        Returns:
            The result from the next handler.
        """
        start_time = time.perf_counter()
        method = context.method

        try:
            result = await call_next(context)
            duration_ms = (time.perf_counter() - start_time) * 1000

            if duration_ms >= self.slow_threshold_ms:
                self.logger.warning(
                    "Slow request: %s completed in %.2fms",
                    method,
                    duration_ms,
                )
            else:
                self.logger.info(
                    "Request %s completed in %.2fms",
                    method,
                    duration_ms,
                )

            return result

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.logger.error(
                "Request %s failed after %.2fms: %s",
                method,
                duration_ms,
                str(e),
            )
            raise

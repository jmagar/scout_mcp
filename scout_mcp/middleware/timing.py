"""Timing middleware for request duration tracking."""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from fastmcp.server.middleware import MiddlewareContext

from scout_mcp.middleware.base import ScoutMiddleware


@dataclass
class TimingStats:
    """Statistics for a timed operation."""

    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0

    @property
    def avg_ms(self) -> float:
        """Average duration in milliseconds."""
        return self.total_ms / self.count if self.count > 0 else 0.0

    def record(self, duration_ms: float) -> None:
        """Record a new timing measurement."""
        self.count += 1
        self.total_ms += duration_ms
        self.min_ms = min(self.min_ms, duration_ms)
        self.max_ms = max(self.max_ms, duration_ms)

    def to_dict(self) -> dict[str, float | int]:
        """Convert to dictionary."""
        return {
            "count": self.count,
            "total_ms": round(self.total_ms, 2),
            "avg_ms": round(self.avg_ms, 2),
            "min_ms": round(self.min_ms, 2) if self.min_ms != float("inf") else 0.0,
            "max_ms": round(self.max_ms, 2),
        }


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


class DetailedTimingMiddleware(ScoutMiddleware):
    """Middleware with per-operation timing breakdowns.

    Tracks timing for specific operation types (tools, resources, prompts)
    and provides aggregate statistics.

    Example:
        >>> middleware = DetailedTimingMiddleware()
        >>> mcp.add_middleware(middleware)
        >>> # Later...
        >>> stats = middleware.get_timing_stats()
        >>> print(stats["tool:scout"]["avg_ms"])
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
        slow_threshold_ms: float = 1000.0,
    ) -> None:
        """Initialize detailed timing middleware.

        Args:
            logger: Optional custom logger.
            slow_threshold_ms: Threshold for slow operation warnings.
        """
        super().__init__(logger=logger)
        self.slow_threshold_ms = slow_threshold_ms
        self._stats: dict[str, TimingStats] = defaultdict(TimingStats)

    def get_timing_stats(self) -> dict[str, dict[str, float | int]]:
        """Get timing statistics for all operations.

        Returns:
            Dictionary mapping operation keys to timing stats.
        """
        return {key: stats.to_dict() for key, stats in self._stats.items()}

    def reset_stats(self) -> None:
        """Reset all timing statistics."""
        self._stats.clear()

    async def _time_operation(
        self,
        key: str,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Time an operation and record stats.

        Args:
            key: Statistics key for this operation.
            context: The middleware context.
            call_next: Function to call the next handler.

        Returns:
            The result from the next handler.
        """
        start_time = time.perf_counter()

        try:
            result = await call_next(context)
            duration_ms = (time.perf_counter() - start_time) * 1000

            self._stats[key].record(duration_ms)

            if duration_ms >= self.slow_threshold_ms:
                self.logger.warning(
                    "Slow operation %s: %.2fms",
                    key,
                    duration_ms,
                )
            else:
                self.logger.info(
                    "Operation %s: %.2fms",
                    key,
                    duration_ms,
                )

            return result

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._stats[key].record(duration_ms)
            self.logger.error(
                "Operation %s failed after %.2fms: %s",
                key,
                duration_ms,
                str(e),
            )
            raise

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Time tool execution."""
        tool_name = getattr(context.message, "name", "unknown")
        return await self._time_operation(f"tool:{tool_name}", context, call_next)

    async def on_read_resource(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Time resource reading."""
        uri = getattr(context.message, "uri", "unknown")
        return await self._time_operation(f"resource:{uri}", context, call_next)

    async def on_get_prompt(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Time prompt retrieval."""
        name = getattr(context.message, "name", "unknown")
        return await self._time_operation(f"prompt:{name}", context, call_next)

    async def on_list_tools(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Time tool listing."""
        return await self._time_operation("list:tools", context, call_next)

    async def on_list_resources(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Time resource listing."""
        return await self._time_operation("list:resources", context, call_next)

    async def on_list_prompts(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Time prompt listing."""
        return await self._time_operation("list:prompts", context, call_next)

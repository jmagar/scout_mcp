"""Error handling middleware for consistent error responses."""

import logging
import traceback
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from fastmcp.server.middleware import MiddlewareContext

from scout_mcp.middleware.base import ScoutMiddleware

ErrorCallback = Callable[[Exception, MiddlewareContext], None]


class ErrorHandlingMiddleware(ScoutMiddleware):
    """Middleware that provides consistent error handling and logging.

    Catches exceptions, logs them appropriately, tracks error statistics,
    and optionally calls an error callback for custom handling.

    Example:
        >>> def on_error(exc, ctx):
        ...     print(f"Error in {ctx.method}: {exc}")
        >>> middleware = ErrorHandlingMiddleware(error_callback=on_error)
        >>> mcp.add_middleware(middleware)
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
        include_traceback: bool = False,
        error_callback: ErrorCallback | None = None,
    ) -> None:
        """Initialize error handling middleware.

        Args:
            logger: Optional custom logger.
            include_traceback: Whether to include full traceback in logs.
            error_callback: Optional callback called on each error.
                Receives (exception, context) as arguments.
        """
        super().__init__(logger=logger)
        self.include_traceback = include_traceback
        self.error_callback = error_callback
        self._error_counts: dict[str, int] = defaultdict(int)

    def get_error_stats(self) -> dict[str, int]:
        """Get error statistics by exception type.

        Returns:
            Dictionary mapping exception type names to occurrence counts.
        """
        return dict(self._error_counts)

    def reset_stats(self) -> None:
        """Reset error statistics."""
        self._error_counts.clear()

    async def on_message(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        """Handle errors during request processing.

        Args:
            context: The middleware context with request info.
            call_next: Function to call the next handler.

        Returns:
            The result from the next handler.

        Raises:
            Exception: Re-raises the original exception after logging.
        """
        try:
            return await call_next(context)

        except Exception as e:
            error_type = type(e).__name__
            method = context.method

            # Track statistics
            self._error_counts[error_type] += 1

            # Log the error
            if self.include_traceback:
                tb = traceback.format_exc()
                self.logger.error(
                    "Error in %s: %s: %s\n%s",
                    method,
                    error_type,
                    str(e),
                    tb,
                )
            else:
                self.logger.error(
                    "Error in %s: %s: %s",
                    method,
                    error_type,
                    str(e),
                )

            # Call error callback if provided
            if self.error_callback:
                try:
                    self.error_callback(e, context)
                except Exception as callback_error:
                    self.logger.warning(
                        "Error callback failed: %s",
                        str(callback_error),
                    )

            # Re-raise the original exception
            raise

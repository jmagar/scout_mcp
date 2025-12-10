"""Rate limiting middleware for MCP requests.

Implements token bucket algorithm to limit requests per client IP.
Works at MCP layer (not HTTP-specific) for transport independence.
"""
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from scout_mcp.middleware.base import MCPMiddleware


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    capacity: int
    refill_rate: float  # tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        self.tokens = float(self.capacity)
        self.last_refill = time.monotonic()

    def consume(self, count: int = 1) -> bool:
        """Try to consume tokens. Returns True if successful."""
        now = time.monotonic()
        elapsed = now - self.last_refill

        # Refill tokens based on time elapsed
        self.tokens = min(self.capacity, self.tokens + (elapsed * self.refill_rate))
        self.last_refill = now

        # Try to consume
        if self.tokens >= count:
            self.tokens -= count
            return True
        return False

    def time_until_ready(self) -> float:
        """Return seconds until next token available."""
        if self.tokens >= 1:
            return 0.0
        needed = 1.0 - self.tokens
        return needed / self.refill_rate


class RateLimitMiddleware(MCPMiddleware):
    """MCP-layer rate limiting middleware.

    Uses token bucket algorithm per client identifier.
    Works with any transport (HTTP, STDIO, etc.).
    """

    def __init__(
        self,
        per_minute: int = 60,
        burst: int = 10,
    ):
        """Initialize rate limiter.

        Args:
            per_minute: Maximum requests per minute per client
            burst: Maximum burst size (token bucket capacity)
        """
        self.per_minute = per_minute
        self.burst = burst
        self.refill_rate = per_minute / 60.0  # tokens per second
        self._buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(
                capacity=self.burst,
                refill_rate=self.refill_rate,
            )
        )

    async def process_request(
        self,
        method: str,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Check rate limit before processing request."""
        # Extract client identifier from context
        client_id = self._get_client_id(context)

        # Get or create bucket for this client
        bucket = self._buckets[client_id]

        # Try to consume token
        if not bucket.consume():
            retry_after = bucket.time_until_ready()
            raise PermissionError(
                f"Rate limit exceeded. Retry after {retry_after:.1f} seconds."
            )

        return context

    def _get_client_id(self, context: dict[str, Any]) -> str:
        """Extract client identifier from context.

        Tries to get client IP from context, falls back to generic identifier.
        HTTP transport should populate 'client_ip' in context.
        """
        # Check for client IP in context (set by HTTP transport)
        if "client_ip" in context:
            return context["client_ip"]

        # Check for other identifiers
        if "client_id" in context:
            return context["client_id"]

        # Fallback to generic (all STDIO clients share bucket)
        return "stdio"

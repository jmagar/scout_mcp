"""Rate limiting middleware for Scout MCP."""

import asyncio
import logging
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting."""

    tokens: float = 0.0
    last_update: float = field(default_factory=time.monotonic)

    def consume(self, tokens_per_second: float, max_tokens: float) -> bool:
        """Try to consume a token. Returns True if allowed."""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.last_update = now

        # Refill tokens
        self.tokens = min(max_tokens, self.tokens + elapsed * tokens_per_second)

        # Try to consume
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting.

    Uses token bucket algorithm per client IP.

    Environment Variables:
        SCOUT_RATE_LIMIT_PER_MINUTE: Requests per minute per client (default: 60)
        SCOUT_RATE_LIMIT_BURST: Max burst size (default: 10)
    """

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self._buckets: dict[str, RateLimitBucket] = {}
        self._lock = asyncio.Lock()

        # Load config
        self._rate_per_minute = int(os.getenv("SCOUT_RATE_LIMIT_PER_MINUTE", "60"))
        self._burst = int(os.getenv("SCOUT_RATE_LIMIT_BURST", "10"))
        self._tokens_per_second = self._rate_per_minute / 60.0

        # Initialize enabled state
        self._enabled = self._rate_per_minute > 0

        if self._enabled:
            logger.info(
                "Rate limiting enabled: %d req/min, burst=%d",
                self._rate_per_minute,
                self._burst,
            )
        else:
            logger.info("Rate limiting disabled")

    def _get_client_key(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Use X-Forwarded-For if behind proxy, else client IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Apply rate limiting."""
        # Skip if disabled
        if not self._enabled:
            return await call_next(request)

        # Skip health checks
        if request.url.path == "/health":
            return await call_next(request)

        client_key = self._get_client_key(request)

        async with self._lock:
            # Initialize new bucket with burst capacity
            if client_key not in self._buckets:
                self._buckets[client_key] = RateLimitBucket(
                    tokens=float(self._burst), last_update=time.monotonic()
                )
            bucket = self._buckets[client_key]
            allowed = bucket.consume(self._tokens_per_second, self._burst)

        if not allowed:
            logger.warning(
                "Rate limit exceeded for client %s on %s",
                client_key,
                request.url.path,
            )
            retry_after = max(1, int(60 / self._rate_per_minute))
            return JSONResponse(
                {
                    "error": "Rate limit exceeded",
                    "retry_after": retry_after,
                },
                status_code=429,
                headers={
                    "Retry-After": str(retry_after),
                },
            )

        return await call_next(request)

    async def cleanup_stale_buckets(self, max_age_seconds: int = 3600) -> int:
        """Remove buckets that haven't been used recently."""
        async with self._lock:
            now = time.monotonic()
            stale = [
                key
                for key, bucket in self._buckets.items()
                if now - bucket.last_update > max_age_seconds
            ]
            for key in stale:
                del self._buckets[key]
            return len(stale)

"""Tests for HTTP middleware adapter."""
import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from scout_mcp.middleware.auth import APIKeyMiddleware
from scout_mcp.middleware.http_adapter import HTTPMiddlewareAdapter
from scout_mcp.middleware.ratelimit import RateLimitMiddleware


class TestHTTPMiddlewareAdapter:
    """Test HTTP middleware adapter."""

    def test_extracts_client_ip_from_request(self):
        """HTTP adapter should extract client IP from request."""
        # Create a simple auth middleware that doesn't check anything
        auth_middleware = APIKeyMiddleware(api_keys=[], enabled=False)

        # Create app with adapter
        app = Starlette(
            routes=[],
            middleware=[
                Middleware(HTTPMiddlewareAdapter, mcp_middleware=auth_middleware)
            ],
        )

        # Track what context was passed
        contexts = []

        async def process_request_spy(method, params, context):
            contexts.append(context)
            return context

        # Monkey patch to spy on context
        auth_middleware.process_request = process_request_spy

        @app.route("/test")
        async def handler(request: Request):
            return PlainTextResponse("OK")

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert len(contexts) == 1
        assert "client_ip" in contexts[0]
        assert contexts[0]["client_ip"] == "testclient"

    def test_extracts_api_key_from_header(self):
        """HTTP adapter should extract API key from X-API-Key header."""
        auth_middleware = APIKeyMiddleware(api_keys=[], enabled=False)

        app = Starlette(
            routes=[],
            middleware=[
                Middleware(HTTPMiddlewareAdapter, mcp_middleware=auth_middleware)
            ],
        )

        contexts = []

        async def process_request_spy(method, params, context):
            contexts.append(context)
            return context

        auth_middleware.process_request = process_request_spy

        @app.route("/test")
        async def handler(request: Request):
            return PlainTextResponse("OK")

        client = TestClient(app)
        response = client.get("/test", headers={"X-API-Key": "test-key-123"})

        assert response.status_code == 200
        assert contexts[0]["api_key"] == "test-key-123"

    def test_handles_x_forwarded_for(self):
        """HTTP adapter should use X-Forwarded-For if present."""
        auth_middleware = APIKeyMiddleware(api_keys=[], enabled=False)

        app = Starlette(
            routes=[],
            middleware=[
                Middleware(HTTPMiddlewareAdapter, mcp_middleware=auth_middleware)
            ],
        )

        contexts = []

        async def process_request_spy(method, params, context):
            contexts.append(context)
            return context

        auth_middleware.process_request = process_request_spy

        @app.route("/test")
        async def handler(request: Request):
            return PlainTextResponse("OK")

        client = TestClient(app)
        response = client.get(
            "/test", headers={"X-Forwarded-For": "192.168.1.100, 10.0.0.1"}
        )

        assert response.status_code == 200
        assert contexts[0]["client_ip"] == "192.168.1.100"

    def test_maps_rate_limit_error_to_429(self):
        """HTTP adapter should map RateLimitError to 429 status."""
        rate_limit = RateLimitMiddleware(per_minute=1, burst=1)

        app = Starlette(
            routes=[],
            middleware=[Middleware(HTTPMiddlewareAdapter, mcp_middleware=rate_limit)],
        )

        @app.route("/test")
        async def handler(request: Request):
            return PlainTextResponse("OK")

        client = TestClient(app)

        # First request succeeds
        response1 = client.get("/test")
        assert response1.status_code == 200

        # Second request is rate limited
        response2 = client.get("/test")
        assert response2.status_code == 429
        assert "error" in response2.json()
        assert "Rate limit exceeded" in response2.json()["error"]

    def test_maps_auth_error_to_401(self):
        """HTTP adapter should map auth PermissionError to 401 status."""
        auth_middleware = APIKeyMiddleware(api_keys=["valid-key"], enabled=True)

        app = Starlette(
            routes=[],
            middleware=[
                Middleware(HTTPMiddlewareAdapter, mcp_middleware=auth_middleware)
            ],
        )

        @app.route("/test")
        async def handler(request: Request):
            return PlainTextResponse("OK")

        client = TestClient(app)

        # No API key
        response = client.get("/test")
        assert response.status_code == 401
        assert "error" in response.json()

    def test_includes_retry_after_header(self):
        """HTTP adapter should include Retry-After header for rate limits."""
        rate_limit = RateLimitMiddleware(per_minute=1, burst=1)

        app = Starlette(
            routes=[],
            middleware=[Middleware(HTTPMiddlewareAdapter, mcp_middleware=rate_limit)],
        )

        @app.route("/test")
        async def handler(request: Request):
            return PlainTextResponse("OK")

        client = TestClient(app)

        # First request succeeds
        client.get("/test")

        # Second request is rate limited
        response = client.get("/test")
        assert response.status_code == 429
        assert "Retry-After" in response.headers
        # Should be >= 1 second
        assert int(response.headers["Retry-After"]) >= 1

    def test_health_endpoint_bypasses_middleware(self):
        """Health check endpoint should bypass all middleware."""
        # Create very strict rate limit
        rate_limit = RateLimitMiddleware(per_minute=1, burst=1)

        app = Starlette(
            routes=[],
            middleware=[Middleware(HTTPMiddlewareAdapter, mcp_middleware=rate_limit)],
        )

        @app.route("/health")
        async def health_handler(request: Request):
            return PlainTextResponse("OK")

        @app.route("/test")
        async def test_handler(request: Request):
            return PlainTextResponse("OK")

        client = TestClient(app)

        # Multiple health checks should all succeed
        for _ in range(5):
            response = client.get("/health")
            assert response.status_code == 200

        # But regular endpoints are still rate limited
        client.get("/test")
        response = client.get("/test")
        assert response.status_code == 429

    def test_health_endpoint_bypasses_auth(self):
        """Health check endpoint should bypass authentication."""
        auth_middleware = APIKeyMiddleware(api_keys=["secret"], enabled=True)

        app = Starlette(
            routes=[],
            middleware=[
                Middleware(HTTPMiddlewareAdapter, mcp_middleware=auth_middleware)
            ],
        )

        @app.route("/health")
        async def health_handler(request: Request):
            return PlainTextResponse("OK")

        @app.route("/test")
        async def test_handler(request: Request):
            return PlainTextResponse("OK")

        client = TestClient(app)

        # Health check without auth works
        response = client.get("/health")
        assert response.status_code == 200

        # But regular endpoint requires auth
        response = client.get("/test")
        assert response.status_code == 401

    def test_unknown_client_handled(self):
        """HTTP adapter should handle requests with unknown client."""
        auth_middleware = APIKeyMiddleware(api_keys=[], enabled=False)

        app = Starlette(
            routes=[],
            middleware=[
                Middleware(HTTPMiddlewareAdapter, mcp_middleware=auth_middleware)
            ],
        )

        contexts = []

        async def process_request_spy(method, params, context):
            contexts.append(context)
            return context

        auth_middleware.process_request = process_request_spy

        @app.route("/test")
        async def handler(request: Request):
            return PlainTextResponse("OK")

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        # Should have a client_ip (even if it's "testclient")
        assert "client_ip" in contexts[0]

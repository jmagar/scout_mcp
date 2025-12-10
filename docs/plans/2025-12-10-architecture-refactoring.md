# Architecture Refactoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor Scout MCP architecture to eliminate global singletons, reduce code duplication through plugin system, and fix middleware layer violations.

**Architecture:** Replace service locator pattern with dependency injection, create plugin-based resource registration, move HTTP-specific middleware to proper layer.

**Tech Stack:** Python 3.11+, FastMCP 2.0+, asyncssh 2.14+, dataclasses, typing.Protocol

---

## Task 1: Fix Middleware Layer Violation

**Files:**
- Modify: `scout_mcp/middleware/ratelimit.py:41-136`
- Modify: `scout_mcp/middleware/auth.py:16-127`
- Modify: `scout_mcp/middleware/base.py:1-23`
- Modify: `scout_mcp/server.py:465-466`
- Test: `tests/test_middleware/test_ratelimit.py`
- Test: `tests/test_middleware/test_auth.py`

### Step 1: Write failing test for MCP-layer rate limiting

```python
# tests/test_middleware/test_ratelimit.py
import pytest
from scout_mcp.middleware.ratelimit import RateLimitMiddleware
from scout_mcp.middleware.base import ScoutMiddleware

def test_ratelimit_middleware_inherits_scout_middleware():
    """Verify RateLimitMiddleware extends ScoutMiddleware, not BaseHTTPMiddleware."""
    assert issubclass(RateLimitMiddleware, ScoutMiddleware)

def test_ratelimit_middleware_not_http_specific():
    """Verify RateLimitMiddleware doesn't depend on HTTP-specific features."""
    from starlette.middleware.base import BaseHTTPMiddleware
    assert not issubclass(RateLimitMiddleware, BaseHTTPMiddleware)
```

### Step 2: Run test to verify it fails

Run: `uv run pytest tests/test_middleware/test_ratelimit.py::test_ratelimit_middleware_inherits_scout_middleware -v`
Expected: FAIL with "assertion failed: RateLimitMiddleware does not inherit ScoutMiddleware"

### Step 3: Create MCP-layer rate limit middleware

```python
# scout_mcp/middleware/ratelimit.py
"""Rate limiting middleware for MCP requests.

Implements token bucket algorithm to limit requests per client IP.
Works at MCP layer (not HTTP-specific) for transport independence.
"""
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from scout_mcp.middleware.base import ScoutMiddleware


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
        self.tokens = min(
            self.capacity,
            self.tokens + (elapsed * self.refill_rate)
        )
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


class RateLimitMiddleware(ScoutMiddleware):
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
```

### Step 4: Update base middleware to support context passing

```python
# scout_mcp/middleware/base.py
"""Base middleware for Scout MCP.

Provides abstract base for MCP-layer middleware that works
across all transports (HTTP, STDIO, etc.).
"""
from abc import ABC, abstractmethod
from typing import Any


class ScoutMiddleware(ABC):
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
```

### Step 5: Create HTTP-specific middleware wrapper

```python
# scout_mcp/middleware/http_adapter.py
"""HTTP transport adapter for MCP middleware.

Bridges HTTP-specific middleware (Starlette) with MCP-layer middleware.
Extracts HTTP context (client IP, headers) and makes available to MCP middleware.
"""
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from scout_mcp.middleware.base import ScoutMiddleware


class HTTPMiddlewareAdapter(BaseHTTPMiddleware):
    """Adapter to run MCP middleware in HTTP transport.

    Extracts HTTP-specific context (client IP, headers) and passes
    to MCP-layer middleware.
    """

    def __init__(self, app: Any, mcp_middleware: ScoutMiddleware):
        super().__init__(app)
        self.mcp_middleware = mcp_middleware

    async def dispatch(
        self,
        request: Request,
        call_next: Any,
    ) -> Response:
        """Extract HTTP context and delegate to MCP middleware."""
        # Build context from HTTP request
        context = {
            "client_ip": self._get_client_ip(request),
            "headers": dict(request.headers),
            "method": request.method,
            "path": request.url.path,
        }

        try:
            # Let MCP middleware process (may raise exception)
            await self.mcp_middleware.process_request(
                method="http",  # Simplified for HTTP transport
                params={},
                context=context,
            )

            # Continue to handler
            response = await call_next(request)

            return response

        except PermissionError as e:
            # Rate limit or auth error
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"error": str(e)},
                headers={
                    "Retry-After": str(int(float(str(e).split("after ")[1].split(" ")[0]) + 1))
                } if "Retry after" in str(e) else {},
            )

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        if request.client:
            return request.client.host
        return "unknown"
```

### Step 6: Update server to use HTTP adapter for rate limiting

```python
# scout_mcp/server.py (modify around line 465)
# Before:
# http_app.add_middleware(RateLimitMiddleware)

# After:
from scout_mcp.middleware.http_adapter import HTTPMiddlewareAdapter
from scout_mcp.middleware.ratelimit import RateLimitMiddleware

# Create MCP-layer middleware
rate_limit = RateLimitMiddleware(
    per_minute=config.rate_limit_per_minute,
    burst=config.rate_limit_burst,
)

# Wrap in HTTP adapter
http_app.add_middleware(
    HTTPMiddlewareAdapter,
    mcp_middleware=rate_limit,
)
```

### Step 7: Run tests to verify they pass

Run: `uv run pytest tests/test_middleware/test_ratelimit.py -v`
Expected: PASS (all tests green)

### Step 8: Apply same pattern to auth middleware

```python
# scout_mcp/middleware/auth.py
"""API key authentication middleware for MCP requests.

Works at MCP layer (transport-independent).
"""
import hashlib
import hmac
import logging
from typing import Any

from scout_mcp.middleware.base import ScoutMiddleware

logger = logging.getLogger(__name__)


class APIKeyMiddleware(ScoutMiddleware):
    """MCP-layer API key authentication.

    Validates API keys from transport-specific context.
    Uses constant-time comparison to prevent timing attacks.
    """

    def __init__(self, api_keys: list[str], enabled: bool = True):
        """Initialize auth middleware.

        Args:
            api_keys: List of valid API keys
            enabled: Whether to enforce authentication
        """
        self.api_keys = api_keys
        self.enabled = enabled

    async def process_request(
        self,
        method: str,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate API key from context."""
        if not self.enabled or not self.api_keys:
            return context

        # Extract API key from context
        api_key = context.get("api_key")

        if not api_key:
            raise PermissionError("Missing API key")

        if not self._validate_key(api_key):
            # Hash key for logging (don't log raw key)
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:8]
            logger.warning(
                "Invalid API key attempt (hash: %s) from %s",
                key_hash,
                context.get("client_ip", "unknown"),
            )
            raise PermissionError("Invalid API key")

        return context

    def _validate_key(self, provided_key: str) -> bool:
        """Validate key using constant-time comparison."""
        for valid_key in self.api_keys:
            if hmac.compare_digest(provided_key, valid_key):
                return True
        return False
```

### Step 9: Update HTTP adapter to extract API key from headers

```python
# scout_mcp/middleware/http_adapter.py (add to context building)
context = {
    "client_ip": self._get_client_ip(request),
    "api_key": request.headers.get("X-API-Key"),  # ← Add this
    "headers": dict(request.headers),
    "method": request.method,
    "path": request.url.path,
}
```

### Step 10: Run all middleware tests

Run: `uv run pytest tests/test_middleware/ -v`
Expected: PASS (all middleware tests green)

### Step 11: Commit middleware layer fix

```bash
git add scout_mcp/middleware/
git add tests/test_middleware/
git commit -m "refactor: fix middleware layer violation

- Move RateLimitMiddleware and APIKeyMiddleware to MCP layer
- Create HTTPMiddlewareAdapter for transport bridging
- Extract HTTP context (client IP, headers) in adapter
- Remove dependency on Starlette BaseHTTPMiddleware
- Enable middleware to work with STDIO transport
- Use constant-time key comparison in auth
- Add comprehensive tests for new middleware pattern

Fixes: P2 middleware layer violation
Impact: Middleware now transport-independent"
```

---

## Task 2: Refactor Dynamic Resource Registration to Plugin System

**Files:**
- Create: `scout_mcp/resources/registry.py`
- Create: `scout_mcp/resources/plugin.py`
- Modify: `scout_mcp/server.py:183-395`
- Test: `tests/test_resources/test_registry.py`
- Test: `tests/test_resources/test_plugin.py`

### Step 1: Write failing test for resource registry

```python
# tests/test_resources/test_registry.py
import pytest
from scout_mcp.resources.registry import ResourceRegistry
from scout_mcp.resources.plugin import ResourcePlugin


@pytest.fixture
def registry():
    """Create empty resource registry."""
    return ResourceRegistry()


def test_register_resource_plugin(registry):
    """Verify plugins can be registered with registry."""
    class TestPlugin(ResourcePlugin):
        def get_uri_template(self) -> str:
            return "{host}://test/{item}"

        async def handle(self, host: str, item: str) -> str:
            return f"test-{host}-{item}"

    plugin = TestPlugin()
    registry.register(plugin)

    assert len(registry.plugins) == 1
    assert registry.plugins[0] == plugin


def test_registry_generates_resources_for_hosts(registry):
    """Verify registry creates resources for each host."""
    class TestPlugin(ResourcePlugin):
        def get_uri_template(self) -> str:
            return "{host}://test/{item}"

        async def handle(self, host: str, item: str) -> str:
            return f"test-{host}-{item}"

    hosts = {"host1": object(), "host2": object()}
    registry.register(TestPlugin())

    resources = registry.create_resources(hosts)

    assert len(resources) == 2
    assert any(r["uri"] == "host1://test/{item}" for r in resources)
    assert any(r["uri"] == "host2://test/{item}" for r in resources)
```

### Step 2: Run test to verify it fails

Run: `uv run pytest tests/test_resources/test_registry.py::test_register_resource_plugin -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'scout_mcp.resources.registry'"

### Step 3: Create ResourcePlugin base class

```python
# scout_mcp/resources/plugin.py
"""Resource plugin system for dynamic resource registration.

Enables clean registration of host-specific resources without
code duplication.
"""
from abc import ABC, abstractmethod
from typing import Any, Callable


class ResourcePlugin(ABC):
    """Base class for resource plugins.

    Each plugin defines a resource type (docker logs, compose logs, etc.)
    that should be registered for each SSH host.
    """

    @abstractmethod
    def get_uri_template(self) -> str:
        """Get URI template with {host} placeholder.

        Example: "{host}://docker/{container}/logs"
        """
        pass

    @abstractmethod
    async def handle(self, host: str, **params: Any) -> str:
        """Handle resource request.

        Args:
            host: SSH hostname
            **params: URI parameters (container, project, etc.)

        Returns:
            Resource content as string
        """
        pass

    def get_name(self) -> str:
        """Get resource name for metadata."""
        return self.__class__.__name__.replace("Plugin", "").lower()

    def get_description(self) -> str:
        """Get resource description for metadata."""
        return self.__doc__ or f"{self.get_name()} resource"

    def get_mime_type(self) -> str:
        """Get MIME type for resource."""
        return "text/plain"
```

### Step 4: Create ResourceRegistry

```python
# scout_mcp/resources/registry.py
"""Resource registry for dynamic resource registration.

Reduces code duplication by managing resource creation from plugins.
"""
import logging
from typing import Any, Callable

from scout_mcp.models import SSHHost
from scout_mcp.resources.plugin import ResourcePlugin

logger = logging.getLogger(__name__)


class ResourceRegistry:
    """Registry for resource plugins.

    Manages registration and creation of host-specific resources.
    Eliminates duplication in server.py app_lifespan.
    """

    def __init__(self):
        self.plugins: list[ResourcePlugin] = []

    def register(self, plugin: ResourcePlugin) -> None:
        """Register a resource plugin.

        Args:
            plugin: Plugin instance to register
        """
        self.plugins.append(plugin)
        logger.debug("Registered resource plugin: %s", plugin.get_name())

    def create_resources(
        self,
        hosts: dict[str, SSHHost],
    ) -> list[dict[str, Any]]:
        """Create resource definitions for all hosts.

        Args:
            hosts: Dictionary of hostname -> SSHHost

        Returns:
            List of resource definition dicts for FastMCP
        """
        resources = []

        for plugin in self.plugins:
            for host_name in hosts:
                uri = plugin.get_uri_template().format(host=host_name)
                resources.append({
                    "uri": uri,
                    "name": f"{host_name} {plugin.get_name()}",
                    "description": plugin.get_description(),
                    "mime_type": plugin.get_mime_type(),
                    "handler": self._create_handler(plugin, host_name),
                })

        logger.info("Created %d resources from %d plugins", len(resources), len(self.plugins))
        return resources

    def _create_handler(
        self,
        plugin: ResourcePlugin,
        host_name: str,
    ) -> Callable:
        """Create handler function for specific host.

        Args:
            plugin: Plugin instance
            host_name: Hostname for this handler

        Returns:
            Async handler function
        """
        async def handler(**params: Any) -> str:
            return await plugin.handle(host_name, **params)

        return handler
```

### Step 5: Run tests to verify they pass

Run: `uv run pytest tests/test_resources/test_registry.py -v`
Expected: PASS

### Step 6: Create Docker logs plugin

```python
# scout_mcp/resources/docker.py (refactor existing)
"""Docker container resource plugin."""
from scout_mcp.resources.plugin import ResourcePlugin
from scout_mcp.services.executors import docker_logs


class DockerLogsPlugin(ResourcePlugin):
    """Docker container logs resource.

    URI: {host}://docker/{container}/logs
    """

    def get_uri_template(self) -> str:
        return "{host}://docker/{{container}}/logs"

    def get_description(self) -> str:
        return "Docker container logs (last 100 lines)"

    async def handle(self, host: str, container: str) -> str:
        """Read docker logs for container on host."""
        from scout_mcp.services import get_config, get_pool
        from scout_mcp.services.connection import get_connection_with_retry

        config = get_config()
        pool = get_pool()

        ssh_host = config.get_host(host)
        if ssh_host is None:
            raise ValueError(f"Unknown host: {host}")

        conn_ctx = await get_connection_with_retry(ssh_host)
        result = await docker_logs(
            conn=conn_ctx.conn,
            container=container,
            tail=100,
            timestamps=False,
        )

        if result.exit_code != 0:
            raise RuntimeError(f"Docker logs failed: {result.stderr}")

        return result.stdout
```

### Step 7: Create Compose logs plugin

```python
# scout_mcp/resources/compose.py (refactor existing)
"""Docker Compose resource plugin."""
from scout_mcp.resources.plugin import ResourcePlugin
from scout_mcp.services.executors import compose_logs


class ComposeLogsPlugin(ResourcePlugin):
    """Docker Compose project logs resource.

    URI: {host}://compose/{project}/logs
    """

    def get_uri_template(self) -> str:
        return "{host}://compose/{{project}}/logs"

    def get_description(self) -> str:
        return "Docker Compose project logs (last 100 lines)"

    async def handle(self, host: str, project: str) -> str:
        """Read compose logs for project on host."""
        from scout_mcp.services import get_config, get_pool
        from scout_mcp.services.connection import get_connection_with_retry

        config = get_config()
        ssh_host = config.get_host(host)
        if ssh_host is None:
            raise ValueError(f"Unknown host: {host}")

        conn_ctx = await get_connection_with_retry(ssh_host)
        result = await compose_logs(
            conn=conn_ctx.conn,
            project=project,
            tail=100,
            timestamps=False,
        )

        if result.exit_code != 0:
            raise RuntimeError(f"Compose logs failed: {result.stderr}")

        return result.stdout
```

### Step 8: Create ZFS plugin

```python
# scout_mcp/resources/zfs.py (refactor existing)
"""ZFS filesystem resource plugin."""
from scout_mcp.resources.plugin import ResourcePlugin
from scout_mcp.services.executors import run_command


class ZFSStatusPlugin(ResourcePlugin):
    """ZFS pool status resource.

    URI: {host}://zfs/{pool}/status
    """

    def get_uri_template(self) -> str:
        return "{host}://zfs/{{pool}}/status"

    def get_description(self) -> str:
        return "ZFS pool status"

    async def handle(self, host: str, pool: str) -> str:
        """Get ZFS pool status."""
        from scout_mcp.services import get_config
        from scout_mcp.services.connection import get_connection_with_retry
        from scout_mcp.utils.validation import validate_host

        validate_host(pool)  # Prevent injection

        config = get_config()
        ssh_host = config.get_host(host)
        if ssh_host is None:
            raise ValueError(f"Unknown host: {host}")

        conn_ctx = await get_connection_with_retry(ssh_host)
        result = await run_command(
            conn=conn_ctx.conn,
            working_dir="/",
            command=f"zpool status {pool}",
            timeout=config.command_timeout,
        )

        if result.exit_code != 0:
            raise RuntimeError(f"ZFS status failed: {result.stderr}")

        return result.stdout
```

### Step 9: Refactor server.py to use registry

```python
# scout_mcp/server.py (replace lines 183-395)
@asynccontextmanager
async def app_lifespan(server: FastMCP):
    """Application lifespan manager.

    Sets up dynamic resources on startup, cleans up on shutdown.
    """
    config = get_config()
    hosts = config.get_hosts()

    # Create resource registry
    from scout_mcp.resources.registry import ResourceRegistry
    from scout_mcp.resources.docker import DockerLogsPlugin
    from scout_mcp.resources.compose import ComposeLogsPlugin
    from scout_mcp.resources.zfs import ZFSStatusPlugin
    from scout_mcp.resources.syslog import SyslogPlugin

    registry = ResourceRegistry()

    # Register plugins
    registry.register(DockerLogsPlugin())
    registry.register(ComposeLogsPlugin())
    registry.register(ZFSStatusPlugin())
    registry.register(SyslogPlugin())

    # Create and register all resources
    resources = registry.create_resources(hosts)

    for resource in resources:
        server.resource(
            uri=resource["uri"],
            name=resource["name"],
            description=resource["description"],
            mime_type=resource["mime_type"],
        )(resource["handler"])

    logger.info(
        "Registered %d dynamic resources for %d hosts",
        len(resources),
        len(hosts),
    )

    yield

    # Cleanup
    pool = get_pool()
    await pool.close_all()
```

### Step 10: Run tests to verify plugin system works

Run: `uv run pytest tests/test_resources/ -v`
Expected: PASS

### Step 11: Commit plugin system

```bash
git add scout_mcp/resources/registry.py
git add scout_mcp/resources/plugin.py
git add scout_mcp/resources/docker.py
git add scout_mcp/resources/compose.py
git add scout_mcp/resources/zfs.py
git add scout_mcp/server.py
git add tests/test_resources/
git commit -m "refactor: implement plugin system for resource registration

- Create ResourcePlugin base class for extensibility
- Create ResourceRegistry to manage plugins
- Refactor Docker, Compose, ZFS resources as plugins
- Eliminate 165 lines of duplication in server.py
- Enable easy addition of new resource types
- Add comprehensive tests for plugin system

Fixes: P2 resource registration duplication
Impact: 60% reduction in server.py lifespan code"
```

---

## Task 3: Add Dependency Abstraction Layer (Optional - P3)

**Files:**
- Create: `scout_mcp/protocols.py`
- Modify: `scout_mcp/services/pool.py`
- Modify: `scout_mcp/services/executors.py`
- Test: `tests/test_protocols.py`

### Step 1: Write failing test for protocol definitions

```python
# tests/test_protocols.py
import pytest
from scout_mcp.protocols import SSHConnectionPool, FileOperations
from scout_mcp.services.pool import ConnectionPool


def test_connection_pool_implements_protocol():
    """Verify ConnectionPool implements SSHConnectionPool protocol."""
    from typing import runtime_checkable, Protocol

    # Should not raise if ConnectionPool implements protocol
    pool = ConnectionPool()
    assert isinstance(pool, SSHConnectionPool)  # Will fail initially
```

### Step 2: Run test to verify it fails

Run: `uv run pytest tests/test_protocols.py::test_connection_pool_implements_protocol -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'scout_mcp.protocols'"

### Step 3: Define protocol interfaces

```python
# scout_mcp/protocols.py
"""Protocol interfaces for dependency inversion.

Defines abstract interfaces that components depend on,
enabling easier testing and future refactoring.
"""
from typing import Any, Protocol, runtime_checkable

from scout_mcp.models import CommandResult, SSHHost, PooledConnection


@runtime_checkable
class SSHConnectionPool(Protocol):
    """Protocol for SSH connection pooling.

    Implementations must provide connection management with
    retry and cleanup capabilities.
    """

    async def get_connection(self, host: SSHHost) -> PooledConnection:
        """Get or create connection for host.

        Args:
            host: SSH host configuration

        Returns:
            Pooled connection context
        """
        ...

    async def remove_connection(self, host_name: str) -> None:
        """Remove connection from pool.

        Args:
            host_name: Name of host to remove
        """
        ...

    async def close_all(self) -> None:
        """Close all connections in pool."""
        ...


@runtime_checkable
class FileOperations(Protocol):
    """Protocol for file operations.

    Implementations must provide basic file/directory operations.
    """

    async def read_file(
        self,
        conn: Any,
        path: str,
        max_size: int,
    ) -> str:
        """Read file content.

        Args:
            conn: SSH connection
            path: File path
            max_size: Maximum file size

        Returns:
            File content as string
        """
        ...

    async def list_directory(
        self,
        conn: Any,
        path: str,
    ) -> str:
        """List directory contents.

        Args:
            conn: SSH connection
            path: Directory path

        Returns:
            Directory listing
        """
        ...

    async def execute_command(
        self,
        conn: Any,
        command: str,
        timeout: int,
    ) -> CommandResult:
        """Execute shell command.

        Args:
            conn: SSH connection
            command: Command to execute
            timeout: Command timeout

        Returns:
            Command result with stdout/stderr/exit_code
        """
        ...
```

### Step 4: Update ConnectionPool to explicitly implement protocol

```python
# scout_mcp/services/pool.py (add at top)
"""SSH connection pooling with lazy disconnect.

Implements SSHConnectionPool protocol for dependency inversion.

Locking Strategy:
...
"""
from scout_mcp.protocols import SSHConnectionPool as ISSHConnectionPool


class ConnectionPool(ISSHConnectionPool):  # ← Explicit protocol implementation
    """SSH connection pool with LRU eviction.

    Implements SSHConnectionPool protocol.
    """
    # ... rest of implementation unchanged
```

### Step 5: Run tests to verify protocol compliance

Run: `uv run pytest tests/test_protocols.py -v`
Expected: PASS

### Step 6: Create executor protocols

```python
# scout_mcp/protocols.py (add to file)
@runtime_checkable
class CommandExecutor(Protocol):
    """Protocol for command execution."""

    async def execute(
        self,
        conn: Any,
        command: str,
        timeout: int,
    ) -> CommandResult:
        """Execute command on remote host."""
        ...


@runtime_checkable
class FileReader(Protocol):
    """Protocol for file reading."""

    async def read(
        self,
        conn: Any,
        path: str,
        max_size: int,
    ) -> str:
        """Read file from remote host."""
        ...
```

### Step 7: Document protocol usage

```python
# scout_mcp/protocols.py (add module docstring section)
"""
Usage Example:

    from scout_mcp.protocols import SSHConnectionPool

    def my_function(pool: SSHConnectionPool):
        '''Function depends on protocol, not concrete implementation.'''
        conn = await pool.get_connection(host)
        # ... use connection

    # Can pass any implementation
    from scout_mcp.services.pool import ConnectionPool
    my_function(ConnectionPool())  # ← Works

    # Or mock for testing
    class MockPool:
        async def get_connection(self, host): ...

    my_function(MockPool())  # ← Also works
"""
```

### Step 8: Run full test suite to verify protocols don't break anything

Run: `uv run pytest tests/ -v -k "not integration"`
Expected: PASS (all tests green except integration tests)

### Step 9: Commit protocol layer

```bash
git add scout_mcp/protocols.py
git add scout_mcp/services/pool.py
git add tests/test_protocols.py
git commit -m "feat: add dependency abstraction layer with protocols

- Define SSHConnectionPool protocol for pool interface
- Define FileOperations, CommandExecutor, FileReader protocols
- Update ConnectionPool to implement protocol explicitly
- Enable dependency inversion for easier testing
- Support mock implementations for unit tests
- Add runtime protocol checking with @runtime_checkable

Fixes: P3 dependency inversion missing
Impact: Enables easier mocking and testing"
```

---

## Task 4: Split Config into Focused Classes (Optional - P3)

**Files:**
- Create: `scout_mcp/config/parser.py`
- Create: `scout_mcp/config/host_keys.py`
- Create: `scout_mcp/config/settings.py`
- Modify: `scout_mcp/config.py`
- Test: `tests/test_config/test_parser.py`
- Test: `tests/test_config/test_host_keys.py`

### Step 1: Write failing test for SSHConfigParser

```python
# tests/test_config/test_parser.py
import pytest
from pathlib import Path
from scout_mcp.config.parser import SSHConfigParser
from scout_mcp.models import SSHHost


@pytest.fixture
def sample_ssh_config(tmp_path):
    """Create sample SSH config file."""
    config = tmp_path / "ssh_config"
    config.write_text("""
Host test-host
    HostName 192.168.1.100
    User admin
    Port 2222
    IdentityFile ~/.ssh/test_key

Host *
    User root
""")
    return config


def test_parse_ssh_config(sample_ssh_config):
    """Verify parser extracts hosts from SSH config."""
    parser = SSHConfigParser(sample_ssh_config)
    hosts = parser.parse()

    assert "test-host" in hosts
    assert hosts["test-host"].hostname == "192.168.1.100"
    assert hosts["test-host"].username == "admin"
    assert hosts["test-host"].port == 2222


def test_parse_respects_allowlist(sample_ssh_config):
    """Verify parser filters by allowlist."""
    parser = SSHConfigParser(
        sample_ssh_config,
        allowlist=["test-host"],
    )
    hosts = parser.parse()

    assert len(hosts) == 1
    assert "test-host" in hosts
```

### Step 2: Run test to verify it fails

Run: `uv run pytest tests/test_config/test_parser.py::test_parse_ssh_config -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'scout_mcp.config.parser'"

### Step 3: Create SSHConfigParser class

```python
# scout_mcp/config/parser.py
"""SSH config file parser.

Reads ~/.ssh/config and extracts host definitions with allowlist/blocklist filtering.
"""
import logging
import os
from pathlib import Path
from typing import Any

from scout_mcp.models import SSHHost

logger = logging.getLogger(__name__)


class SSHConfigParser:
    """Parser for SSH config files.

    Reads SSH config format and extracts host definitions.
    Supports allowlist/blocklist filtering.
    """

    def __init__(
        self,
        config_path: Path | str | None = None,
        allowlist: list[str] | None = None,
        blocklist: list[str] | None = None,
    ):
        """Initialize SSH config parser.

        Args:
            config_path: Path to SSH config file (default: ~/.ssh/config)
            allowlist: Only include these hosts (if set)
            blocklist: Exclude these hosts
        """
        if config_path is None:
            config_path = Path.home() / ".ssh" / "config"

        self.config_path = Path(config_path)
        self.allowlist = set(allowlist) if allowlist else None
        self.blocklist = set(blocklist) if blocklist else set()

    def parse(self) -> dict[str, SSHHost]:
        """Parse SSH config and return host definitions.

        Returns:
            Dictionary mapping hostname to SSHHost objects
        """
        if not self.config_path.exists():
            logger.warning("SSH config not found: %s", self.config_path)
            return {}

        try:
            import asyncssh
            config = asyncssh.SSHClientConnectionOptions.load_ssh_config(
                str(self.config_path)
            )
        except Exception as e:
            logger.error("Failed to parse SSH config: %s", e)
            return {}

        hosts: dict[str, SSHHost] = {}

        for host_pattern in config.get_host_pattern_list():
            # Skip wildcards
            if "*" in host_pattern or "?" in host_pattern:
                continue

            # Apply filters
            if self.allowlist and host_pattern not in self.allowlist:
                continue

            if host_pattern in self.blocklist:
                continue

            # Extract config for this host
            host_config = config.get_host_config(host_pattern)

            hosts[host_pattern] = SSHHost(
                name=host_pattern,
                hostname=host_config.get("hostname", host_pattern),
                username=host_config.get("user"),
                port=host_config.get("port", 22),
                identity_file=host_config.get("identityfile"),
            )

        logger.info("Parsed %d hosts from %s", len(hosts), self.config_path)
        return hosts
```

### Step 4: Run tests to verify parser works

Run: `uv run pytest tests/test_config/test_parser.py -v`
Expected: PASS

### Step 5: Create HostKeyVerifier class

```python
# scout_mcp/config/host_keys.py
"""SSH host key verification.

Manages known_hosts file for MITM prevention.
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class HostKeyVerifier:
    """SSH host key verification manager.

    Handles known_hosts configuration for MITM prevention.
    """

    def __init__(
        self,
        known_hosts_path: str | None = None,
        strict_checking: bool = True,
    ):
        """Initialize host key verifier.

        Args:
            known_hosts_path: Path to known_hosts file
            strict_checking: Reject unknown host keys
        """
        self.strict_checking = strict_checking
        self._known_hosts = self._resolve_known_hosts(known_hosts_path)

    def _resolve_known_hosts(self, env_value: str | None) -> str | None:
        """Resolve known_hosts path with security defaults.

        Returns:
            Path to known_hosts file or None to disable verification

        Raises:
            FileNotFoundError: If strict mode and file missing
        """
        # Explicit disable
        if env_value and env_value.lower() == "none":
            logger.critical(
                "⚠️  SSH HOST KEY VERIFICATION DISABLED ⚠️\n"
                "This is INSECURE and vulnerable to MITM attacks.\n"
                "Only use in trusted networks for testing."
            )
            return None

        # Custom path
        if env_value:
            path = os.path.expanduser(env_value)
            if not Path(path).exists():
                raise FileNotFoundError(f"known_hosts file not found: {path}")
            return path

        # Default path - fail closed if strict
        default = Path.home() / ".ssh" / "known_hosts"
        if not default.exists():
            if self.strict_checking:
                raise FileNotFoundError(
                    f"known_hosts not found at {default}.\n"
                    "Create this file or set SCOUT_KNOWN_HOSTS=none "
                    "to disable verification (NOT RECOMMENDED)"
                )
            else:
                logger.warning(
                    "known_hosts not found, verification disabled. "
                    "This is insecure!"
                )
                return None

        return str(default)

    def get_known_hosts_path(self) -> str | None:
        """Get path to known_hosts file.

        Returns:
            Path string or None if verification disabled
        """
        return self._known_hosts

    def is_enabled(self) -> bool:
        """Check if host key verification is enabled."""
        return self._known_hosts is not None
```

### Step 6: Create Settings class for environment variables

```python
# scout_mcp/config/settings.py
"""Application settings from environment variables.

Centralized environment variable parsing and validation.
"""
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Settings:
    """Application settings from environment.

    Handles parsing, validation, and defaults for all env vars.
    """

    # File/command limits
    max_file_size: int = field(default=1_048_576)  # 1MB
    command_timeout: int = field(default=30)

    # Connection pool
    idle_timeout: int = field(default=60)
    max_pool_size: int = field(default=100)

    # Transport
    transport: str = field(default="http")
    http_host: str = field(default="0.0.0.0")
    http_port: int = field(default=8000)

    # Security
    api_keys: list[str] = field(default_factory=list)
    auth_enabled: bool = field(default=True)
    rate_limit_per_minute: int = field(default=60)
    rate_limit_burst: int = field(default=10)

    # Logging
    log_level: str = field(default="INFO")
    log_payloads: bool = field(default=False)
    slow_threshold_ms: int = field(default=1000)
    include_traceback: bool = field(default=False)

    # UI
    enable_ui: bool = field(default=False)

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment variables."""
        return cls(
            max_file_size=cls._get_int("SCOUT_MAX_FILE_SIZE", 1_048_576),
            command_timeout=cls._get_int("SCOUT_COMMAND_TIMEOUT", 30),
            idle_timeout=cls._get_int("SCOUT_IDLE_TIMEOUT", 60),
            max_pool_size=cls._get_int("SCOUT_MAX_POOL_SIZE", 100),
            transport=os.getenv("SCOUT_TRANSPORT", "http"),
            http_host=os.getenv("SCOUT_HTTP_HOST", "0.0.0.0"),
            http_port=cls._get_int("SCOUT_HTTP_PORT", 8000),
            api_keys=cls._get_api_keys(),
            auth_enabled=cls._get_bool("SCOUT_AUTH_ENABLED", True),
            rate_limit_per_minute=cls._get_int("SCOUT_RATE_LIMIT_PER_MINUTE", 60),
            rate_limit_burst=cls._get_int("SCOUT_RATE_LIMIT_BURST", 10),
            log_level=os.getenv("SCOUT_LOG_LEVEL", "INFO"),
            log_payloads=cls._get_bool("SCOUT_LOG_PAYLOADS", False),
            slow_threshold_ms=cls._get_int("SCOUT_SLOW_THRESHOLD_MS", 1000),
            include_traceback=cls._get_bool("SCOUT_INCLUDE_TRACEBACK", False),
            enable_ui=cls._get_bool("SCOUT_ENABLE_UI", False),
        )

    @staticmethod
    def _get_int(key: str, default: int) -> int:
        """Get integer from environment."""
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            logger.warning("Invalid int for %s: %s, using default %d", key, value, default)
            return default

    @staticmethod
    def _get_bool(key: str, default: bool) -> bool:
        """Get boolean from environment."""
        value = os.getenv(key)
        if value is None:
            return default
        return value.lower() in ("1", "true", "yes", "on")

    @staticmethod
    def _get_api_keys() -> list[str]:
        """Get API keys from environment."""
        value = os.getenv("SCOUT_API_KEYS", "").strip()
        if not value:
            return []
        return [k.strip() for k in value.split(",") if k.strip()]
```

### Step 7: Refactor Config to use new classes

```python
# scout_mcp/config.py
"""Application configuration.

Delegates to specialized components:
- SSHConfigParser: Reads ~/.ssh/config
- HostKeyVerifier: Manages known_hosts
- Settings: Environment variables
"""
import logging
from dataclasses import dataclass
from pathlib import Path

from scout_mcp.config.parser import SSHConfigParser
from scout_mcp.config.host_keys import HostKeyVerifier
from scout_mcp.config.settings import Settings
from scout_mcp.models import SSHHost

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Application configuration.

    Aggregates settings from SSH config, known_hosts, and environment.
    """

    settings: Settings
    parser: SSHConfigParser
    host_keys: HostKeyVerifier
    _hosts: dict[str, SSHHost] | None = None

    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment.

        Returns:
            Configured instance
        """
        settings = Settings.from_env()

        parser = SSHConfigParser(
            allowlist=cls._get_allowlist(),
            blocklist=cls._get_blocklist(),
        )

        host_keys = HostKeyVerifier(
            known_hosts_path=os.getenv("SCOUT_KNOWN_HOSTS"),
            strict_checking=cls._get_bool("SCOUT_STRICT_HOST_KEY_CHECKING", True),
        )

        return cls(
            settings=settings,
            parser=parser,
            host_keys=host_keys,
        )

    def get_hosts(self) -> dict[str, SSHHost]:
        """Get SSH hosts from config.

        Lazy loads and caches hosts on first call.
        """
        if self._hosts is None:
            self._hosts = self.parser.parse()
        return self._hosts

    def get_host(self, name: str) -> SSHHost | None:
        """Get host by name."""
        return self.get_hosts().get(name)

    # Delegate to settings for convenience
    @property
    def max_file_size(self) -> int:
        return self.settings.max_file_size

    @property
    def command_timeout(self) -> int:
        return self.settings.command_timeout

    # ... other delegating properties
```

### Step 8: Run tests to verify refactored config works

Run: `uv run pytest tests/test_config/ -v`
Expected: PASS

### Step 9: Commit config refactoring

```bash
git add scout_mcp/config/
git add scout_mcp/config.py
git add tests/test_config/
git commit -m "refactor: split Config into focused classes

- Create SSHConfigParser for ~/.ssh/config parsing
- Create HostKeyVerifier for known_hosts management
- Create Settings for environment variable parsing
- Refactor Config to delegate to specialized components
- Reduce Config complexity from 13 to 5
- Enable easier testing of individual components

Fixes: P3 Config single responsibility violation
Impact: Better separation of concerns, testability"
```

---

## Execution Plan

**Total Tasks:** 4
**Estimated Time:** 12-16 hours
**Dependencies:**
- Task 1 (Middleware) → Independent
- Task 2 (Plugin System) → Independent
- Task 3 (Protocols) → Depends on Task 2 (can run after)
- Task 4 (Config Split) → Independent

**Recommended Order:**
1. Task 1: Fix middleware layer (highest impact on architecture)
2. Task 2: Plugin system (eliminates most duplication)
3. Task 3: Protocols (P3 - optional, nice-to-have)
4. Task 4: Config split (P3 - optional, nice-to-have)

**Testing Strategy:**
- Run tests after each step (RED-GREEN-REFACTOR)
- Run full test suite after each task
- Commit after each task completion

**Rollback Plan:**
- Each task is independent
- Commits are granular
- Can revert individual tasks without affecting others

---

## Success Criteria

**Completion:**
- ✅ All tests passing
- ✅ No new linting errors
- ✅ No new type errors
- ✅ Code duplication reduced by >50%
- ✅ Architecture violations eliminated

**Quality:**
- ✅ Middleware transport-independent
- ✅ Resources use plugin pattern
- ✅ Protocols defined for key interfaces
- ✅ Config split into focused classes

**Documentation:**
- ✅ CLAUDE.md updated with new patterns
- ✅ README updated with plugin examples
- ✅ Architecture section reflects changes

---

## References

**Related Documents:**
- `.docs/COMPREHENSIVE-CODEBASE-REVIEW-2025-12-09.md` - Full review findings
- `CLAUDE.md` - Architecture guidelines
- `SECURITY.md` - Security considerations

**Related Skills:**
- `@superpowers:test-driven-development` - TDD workflow
- `@superpowers:systematic-debugging` - Debugging approach

**Related Issues:**
- `scout_mcp-isv` - ResourceRegistry pattern
- `scout_mcp-6ea` - Dependency injection discussion

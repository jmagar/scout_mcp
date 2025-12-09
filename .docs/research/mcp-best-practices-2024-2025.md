# Model Context Protocol (MCP) Best Practices 2024-2025

**Research Date:** December 3, 2025
**Protocol Version:** 2025-06-18 (Latest)
**Target Audience:** Production MCP Server Developers

## Executive Summary

The Model Context Protocol (MCP) has rapidly evolved from its November 2024 introduction to become the de facto standard for connecting AI applications to external data sources and tools. With three major releases in eight months (2024-11-05, 2025-03-26, 2025-06-18), the specification has matured significantly in security, transport mechanisms, and enterprise readiness.

This document synthesizes best practices from the official specification, production implementations, and community expertise to provide actionable recommendations for building production-quality MCP servers.

---

## 1. Official MCP Specification Overview

### Architecture Fundamentals

MCP establishes a **JSON-RPC 2.0 message-based system** with three primary components:

- **Hosts**: LLM applications (Claude Desktop, ChatGPT) that initiate connections
- **Clients**: Connectors within host applications that communicate with servers
- **Servers**: Services providing context, data, and capabilities

**Key Design Principle**: Stateful connections with capability negotiation, allowing both parties to understand supported features before exchanging data.

### Three Core Primitives

Understanding when to use each primitive is crucial:

1. **Resources** (app-controlled): File-like structured data (APIs, knowledge bases, documents, code files)
   - Read-only, idempotent, side-effect-free
   - Use for: Configuration files, database schemas, documentation

2. **Tools** (model-controlled): Executable functions the LLM can invoke
   - Arbitrary code execution requiring user consent
   - Use for: Database queries, API calls, file manipulation

3. **Prompts** (user-controlled): Predefined templates guiding model interaction
   - Templated messages and workflows
   - Use for: Common workflows, standardized responses

### Specification Evolution

| Version | Release Date | Key Features |
|---------|--------------|--------------|
| 2024-11-05 | Nov 2024 | Initial specification, STDIO + HTTP+SSE transports |
| 2025-03-26 | Mar 2025 | Enhanced security features, improved authorization |
| 2025-06-18 | Jun 2025 | Streamable HTTP transport, OAuth 2.1, structured tool outputs, elicitation support |

**Current Status**: Adopted by OpenAI (March 2025) and Google DeepMind (April 2025). Community has built thousands of MCP servers across all major programming languages.

---

## 2. Tool Design Patterns

### Domain-Aware Tool Design

**Anti-pattern**: Low-level CRUD operations
```python
# DON'T: Generic, requires LLM to understand implementation
create_record(table="expenses", data={...})
update_row(table="leaves", id=123, status="approved")
```

**Best Practice**: Domain-specific actions
```python
# DO: Self-explanatory, high-level semantics
submit_expense_report(employee_id, items, total)
approve_leave_request(request_id, approver_id)
schedule_meeting(attendees, start_time, duration)
```

**Rationale**: Higher-level tools are easier for agents to understand, reason about, and chain together. They reduce the cognitive load on the LLM and make intent explicit.

### Tool Design Principles

1. **Single Responsibility**: Each tool should do one thing well
2. **Minimal Parameters**: Limit to 5 parameters or fewer (use objects for complex inputs)
3. **Clear Naming**: Use descriptive verbs (`create_invoice` not `process_data`)
4. **Rich Metadata**: Provide descriptions, input/output schemas, usage examples

### Tool Schema Example

```python
from pydantic import BaseModel, Field

class ExpenseReportInput(BaseModel):
    employee_id: str = Field(description="Employee identifier")
    items: list[dict] = Field(description="List of expense items")
    total: float = Field(description="Total amount in USD", gt=0)

@mcp.tool()
async def submit_expense_report(input: ExpenseReportInput) -> str:
    """
    Submit an expense report for approval.

    This tool validates the expense items, calculates totals,
    and routes the report to the appropriate approver based
    on company policy.
    """
    # Implementation
```

### Error Handling in Tools

**Critical Rule**: Tools should return error strings, NOT raise exceptions to the MCP client.

```python
# DON'T: Raise exceptions
@mcp.tool()
async def create_user(email: str) -> dict:
    if not validate_email(email):
        raise ValueError("Invalid email format")
    # ...

# DO: Return structured error information
@mcp.tool()
async def create_user(email: str) -> str:
    if not validate_email(email):
        return json.dumps({
            "error": "validation_failed",
            "message": "Invalid email format",
            "field": "email",
            "suggestion": "Use format: user@example.com"
        })
    # ...
```

**Tool Execution Failures**: Failed tool calls return a successful JSON-RPC response with an `isError` flag, separating protocol errors from application errors.

### Code Execution Pattern (Advanced)

For servers with hundreds or thousands of tools, Anthropic's **code execution with MCP** pattern offers significant performance improvements:

**Traditional Approach**:
- Load all tool definitions upfront
- Pass intermediate results through context window
- Slow as tool count increases

**Code Execution Approach**:
- Tools become code-level APIs
- Model writes and executes code instead of direct tool calls
- Load only needed tools on-demand
- Process data in execution environment before returning to model

**When to Use**: Production servers exposing >100 tools, or tools generating large intermediate datasets.

---

## 3. Resource Patterns

### URI Design Best Practices

**Good URI Design**:
```
config://app/production/database.yml
repos://acme/myproject/info
note://personal/2024-12-03-meeting-notes
stock://AAPL/earnings?quarter=Q4&year=2024
```

**Poor URI Design**:
```
resource://1234                    # Not descriptive
http://localhost/data              # Generic, no context
file:///tmp/xyz.json              # Exposes implementation details
```

### URI Design Principles

1. **Descriptive Schemes**: Use domain-specific schemes (`note://`, `stock://`, `config://`)
2. **Logical Hierarchy**: Structure paths to reflect relationships
3. **RFC 6570 Compliance**: Follow standard URI template syntax
4. **Opaque Identifiers**: Don't expose internal IDs or implementation details

### Resource Templates (RFC 6570)

Enable dynamic resource generation with parameterized URIs:

```python
from fastmcp import FastMCP

mcp = FastMCP("stock-data")

@mcp.resource("stock://{symbol}/earnings")
async def get_earnings(symbol: str) -> str:
    """Fetch earnings data for a stock symbol."""
    data = await fetch_earnings(symbol)
    return json.dumps(data)

@mcp.resource("repos://{owner}/{repo}/info")
async def repo_info(owner: str, repo: str) -> str:
    """Get repository information from GitHub."""
    return await github_api.get_repo(owner, repo)
```

**Template Syntax**:
- `{param}`: Single path segment
- `{param*}`: Multi-segment wildcard
- `{?param1,param2}`: Optional query parameters

### Query Parameters

Provide optional configuration without cluttering paths:

```python
@mcp.resource("weather://{city}{?units,lang}")
async def weather(city: str, units: str = "metric", lang: str = "en") -> str:
    """Get weather for a city with optional units and language."""
    # FastMCP automatically coerces types based on function hints
    return await fetch_weather(city, units, lang)
```

### MIME Types

Specify content types explicitly for proper client handling:

```python
# Text content (default)
@mcp.resource("log://app/errors.txt")
async def error_log() -> str:
    return read_log_file()

# JSON content
@mcp.resource("api://users/list", mime_type="application/json")
async def users_list() -> dict:
    return {"users": await db.get_users()}

# Binary content
@mcp.resource("image://logo.png", mime_type="image/png")
async def logo() -> bytes:
    return read_binary_file("logo.png")
```

**Best Practice**: Explicit is better for non-text types. FastMCP defaults to `text/plain` for strings and `application/json` for dicts.

### Resource Metadata

Include rich annotations for client optimization:

```python
@mcp.resource(
    uri="docs://api/reference",
    name="API Reference Documentation",
    description="Complete REST API reference with examples",
    mime_type="text/markdown",
    annotations={
        "audience": "assistant",  # or "user" or "both"
        "priority": 0.9,          # 0.0 to 1.0 scale
        "category": "documentation"
    }
)
async def api_docs() -> str:
    return load_markdown("api_reference.md")
```

**Annotations**: Hints for clients to sort, filter, or highlight resources. Not guarantees of behavior.

### Pagination

For large resource collections, implement cursor-based pagination:

```python
from typing import Optional

@mcp.list_resources()
async def list_resources(cursor: Optional[str] = None) -> tuple[list[Resource], Optional[str]]:
    """
    List available resources with pagination.

    Returns:
        Tuple of (resources, next_cursor). next_cursor is None when no more pages.
    """
    offset = int(cursor) if cursor else 0
    limit = 100

    resources = await db.get_resources(offset=offset, limit=limit)
    next_cursor = str(offset + limit) if len(resources) == limit else None

    return resources, next_cursor
```

**Key Principles**:
- Cursors are opaque to clients (encode position internally)
- Return `None` for cursor when no more pages
- Keep page sizes reasonable (100-1000 items)

### Resource Subscriptions

Notify clients of resource changes:

```python
# Notify when resource collection changes
await mcp.send_notification("notifications/resources/list_changed")

# Notify when specific resource updates
await mcp.send_resource_updated("config://app/production/database.yml")
```

**Use Cases**: Live data feeds, configuration hot-reload, collaborative editing.

### Error Handling

Resources should raise `ResourceError` for clean client-facing messages:

```python
from fastmcp import ResourceError

@mcp.resource("file://{path}")
async def read_file(path: str) -> str:
    # Validate path to prevent directory traversal
    if ".." in path or path.startswith("/"):
        raise ResourceError(f"Invalid path: {path}")

    try:
        return await read_secure_file(path)
    except FileNotFoundError:
        raise ResourceError(f"File not found: {path}")
    except PermissionError:
        raise ResourceError(f"Permission denied: {path}")
```

**ResourceError vs Standard Exceptions**:
- `ResourceError`: Client-facing messages (always sent to clients)
- Standard exceptions: Logged internally, masked in production (unless `mask_error_details=False`)

---

## 4. Transport Layer

### Transport Options

| Transport | Use Case | Pros | Cons |
|-----------|----------|------|------|
| **Streamable HTTP** | Remote servers, web apps, multi-client | Modern, scalable, supports auth | More complex setup |
| **STDIO** | Local tools, CLI, single client | Simple, no network overhead | Local only, single client |
| **SSE (deprecated)** | Legacy support | Backward compatibility | Two endpoints, deprecated |

### Streamable HTTP (Recommended)

**Why**: Single endpoint, supports both request-response and streaming, session management, comprehensive authentication.

**Basic Implementation**:

```python
from fastmcp import FastMCP

mcp = FastMCP("my-server")

# Default transport is Streamable HTTP on 0.0.0.0:8000
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
```

**Production Implementation** (Node.js/TypeScript):

```typescript
import express from 'express';
import { MCPServer } from '@modelcontextprotocol/sdk';

const app = express();
const server = new MCPServer();

app.post('/mcp', async (req, res) => {
    const response = await server.handleRequest(req.body);

    if (response.streaming && req.accepts('text/event-stream')) {
        // SSE stream for long-running operations
        res.setHeader('Content-Type', 'text/event-stream');
        res.setHeader('Cache-Control', 'no-cache');
        res.setHeader('X-Accel-Buffering', 'no'); // Prevent proxy buffering

        for await (const message of response.stream) {
            res.write(`data: ${JSON.stringify(message)}\n\n`);
        }
        res.end();
    } else {
        // JSON response for quick operations
        res.json(response);
    }
});

app.get('/health', (req, res) => res.send('OK'));
app.listen(8000);
```

### Session Management

Distribute session state for horizontal scaling:

```python
import uuid
import json
from datetime import datetime, timedelta
import redis.asyncio as redis

class SessionManager:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)

    async def create_session(self, client_info: dict) -> str:
        session_id = str(uuid.uuid4())
        session_data = {
            "id": session_id,
            "created_at": datetime.utcnow().isoformat(),
            "client_info": client_info,
            "last_activity": datetime.utcnow().isoformat()
        }

        # 1-hour TTL, extended on each request
        await self.redis.setex(
            f"session:{session_id}",
            3600,
            json.dumps(session_data)
        )

        return session_id

    async def validate_session(self, session_id: str) -> dict | None:
        data = await self.redis.get(f"session:{session_id}")
        if not data:
            return None

        # Extend TTL on access
        await self.redis.expire(f"session:{session_id}", 3600)
        return json.loads(data)
```

**Headers**:
- `Mcp-Session-Id`: Preserve across requests for session tracking
- `Last-Event-ID`: Enable stream resumption after disconnection

### STDIO Transport

**When to Use**: Local tools, Claude Desktop integration, single-client scenarios.

```python
if __name__ == "__main__":
    import os
    transport = os.getenv("SCOUT_TRANSPORT", "http")

    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="http", host="0.0.0.0", port=8000)
```

**Claude Desktop Configuration**:

```json
{
  "mcpServers": {
    "my-server": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/server", "python", "-m", "my_server"],
      "env": {
        "TRANSPORT": "stdio"
      }
    }
  }
}
```

### Message Framing

**STDIO**: Newline-delimited JSON. Messages MUST NOT contain embedded newlines.

```python
# Correct
sys.stdout.write(json.dumps(message) + "\n")
sys.stdout.flush()

# Incorrect - breaks framing
sys.stdout.write(json.dumps(message, indent=2) + "\n")
```

**HTTP**: Standard JSON-RPC 2.0 over HTTP POST. SSE for streaming uses `data: {json}\n\n` format.

### Streaming Best Practices

**Backpressure Handling**:

```typescript
for await (const message of response.stream) {
    if (streamClosed) break;

    const canWrite = res.write(`data: ${JSON.stringify(message)}\n\n`);

    if (!canWrite) {
        // Wait for drain event to prevent memory buildup
        await new Promise(resolve => res.once('drain', resolve));
    }
}
```

**Heartbeats**: Send periodic events every 30 seconds to prevent proxy timeouts.

```typescript
const heartbeat = setInterval(() => {
    if (!streamClosed) {
        res.write(': heartbeat\n\n');
    }
}, 30000);

// Clean up on close
res.on('close', () => clearInterval(heartbeat));
```

### Health Check Endpoint

**Essential for Production**:

```python
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
```

**Advanced Health Check**:

```python
@app.get("/health")
async def health_check():
    checks = {
        "database": await check_db_connection(),
        "redis": await check_redis_connection(),
        "api": await check_external_api()
    }

    healthy = all(checks.values())
    status_code = 200 if healthy else 503

    return Response(
        content=json.dumps({
            "status": "healthy" if healthy else "unhealthy",
            "checks": checks,
            "timestamp": datetime.utcnow().isoformat()
        }),
        status_code=status_code,
        media_type="application/json"
    )
```

---

## 5. Performance Considerations

### Connection Pooling (80% Performance Win)

**Problem**: Creating new connections for each request adds 200ms+ latency.

**Solution**: Reuse connections via pooling.

**Implementation** (Python/AsyncSSH):

```python
import asyncio
import asyncssh
from typing import Dict, Optional
from datetime import datetime, timedelta

class PooledConnection:
    def __init__(self, connection: asyncssh.SSHClientConnection, host: str):
        self.connection = connection
        self.host = host
        self.last_used = datetime.utcnow()
        self.lock = asyncio.Lock()
        self.uses = 0

class ConnectionPool:
    def __init__(self, idle_timeout: int = 60):
        self._pool: Dict[str, PooledConnection] = {}
        self._lock = asyncio.Lock()
        self._idle_timeout = idle_timeout
        self._cleanup_task = None

    async def get_connection(self, host: str, **ssh_params) -> asyncssh.SSHClientConnection:
        async with self._lock:
            if host in self._pool:
                pooled = self._pool[host]
                if not pooled.connection.is_closed():
                    pooled.last_used = datetime.utcnow()
                    pooled.uses += 1
                    return pooled.connection
                else:
                    # Connection died, remove from pool
                    del self._pool[host]

        # Create new connection
        try:
            connection = await asyncssh.connect(host, **ssh_params)
            async with self._lock:
                self._pool[host] = PooledConnection(connection, host)
            return connection
        except Exception as e:
            # One-retry pattern
            connection = await asyncssh.connect(host, **ssh_params)
            async with self._lock:
                self._pool[host] = PooledConnection(connection, host)
            return connection

    async def cleanup_idle(self):
        """Remove connections idle for longer than idle_timeout."""
        async with self._lock:
            now = datetime.utcnow()
            to_remove = []

            for host, pooled in self._pool.items():
                idle_time = (now - pooled.last_used).total_seconds()
                if idle_time > self._idle_timeout:
                    to_remove.append(host)
                    if not pooled.connection.is_closed():
                        pooled.connection.close()

            for host in to_remove:
                del self._pool[host]

    async def start_cleanup_task(self):
        """Start background task for idle connection cleanup."""
        while True:
            await asyncio.sleep(30)  # Check every 30 seconds
            await self.cleanup_idle()

# Global singleton
_pool: Optional[ConnectionPool] = None

def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(idle_timeout=60)
    return _pool
```

**Database Connection Pooling** (SQLAlchemy):

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/db",
    pool_size=20,          # Normal pool size
    max_overflow=10,       # Additional connections under load
    pool_timeout=30,       # Wait time for connection
    pool_recycle=3600,     # Recycle connections after 1 hour
    pool_pre_ping=True     # Verify connection health before use
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)
```

### Caching Strategies

**In-Memory Caching with Background Refresh**:

```python
from datetime import datetime, timedelta
from typing import Any, Optional, Callable
import asyncio

class CacheEntry:
    def __init__(self, value: Any, expires_at: datetime):
        self.value = value
        self.expires_at = expires_at
        self.refreshing = False

class SmartCache:
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def get_or_fetch(
        self,
        key: str,
        fetch_fn: Callable,
        ttl: int = 60
    ) -> Any:
        """
        Get cached value or fetch new one.
        Refresh in background if cache is stale but still valid.
        """
        now = datetime.utcnow()

        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]

                # Cache still valid
                if now < entry.expires_at:
                    # Refresh in background if approaching expiry
                    time_until_expiry = (entry.expires_at - now).total_seconds()
                    if time_until_expiry < ttl * 0.2 and not entry.refreshing:
                        entry.refreshing = True
                        asyncio.create_task(self._background_refresh(key, fetch_fn, ttl))

                    return entry.value

                # Cache expired, remove
                del self._cache[key]

        # Fetch new value
        value = await fetch_fn()

        async with self._lock:
            self._cache[key] = CacheEntry(
                value=value,
                expires_at=now + timedelta(seconds=ttl)
            )

        return value

    async def _background_refresh(self, key: str, fetch_fn: Callable, ttl: int):
        """Refresh cache in background."""
        try:
            value = await fetch_fn()
            async with self._lock:
                self._cache[key] = CacheEntry(
                    value=value,
                    expires_at=datetime.utcnow() + timedelta(seconds=ttl)
                )
        except Exception:
            # Keep old value on refresh failure
            async with self._lock:
                if key in self._cache:
                    self._cache[key].refreshing = False

# Usage
cache = SmartCache()

@mcp.tool()
async def get_stock_price(symbol: str) -> str:
    price = await cache.get_or_fetch(
        f"stock:{symbol}",
        lambda: fetch_stock_price(symbol),
        ttl=60
    )
    return f"${price}"
```

**Redis Caching**:

```python
import redis.asyncio as redis
import json

class RedisCache:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)

    async def get(self, key: str) -> Optional[Any]:
        value = await self.redis.get(key)
        return json.loads(value) if value else None

    async def set(self, key: str, value: Any, ttl: int = 60):
        await self.redis.setex(key, ttl, json.dumps(value))

    async def get_or_fetch(self, key: str, fetch_fn: Callable, ttl: int = 60) -> Any:
        cached = await self.get(key)
        if cached is not None:
            return cached

        value = await fetch_fn()
        await self.set(key, value, ttl)
        return value
```

### Request Batching

**Problem**: 10 individual requests = 500ms total (50ms each)

**Solution**: Batch similar requests = 60ms total

```python
from collections import defaultdict
import asyncio

class RequestBatcher:
    def __init__(self, max_batch_size: int = 50, max_wait_ms: int = 10):
        self._pending: Dict[str, List] = defaultdict(list)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._max_batch_size = max_batch_size
        self._max_wait_ms = max_wait_ms

    async def batch_request(self, batch_key: str, item_id: str, fetch_fn: Callable) -> Any:
        """
        Add request to batch. Flush when batch is full or timeout expires.
        """
        async with self._locks[batch_key]:
            # Add to pending
            future = asyncio.Future()
            self._pending[batch_key].append((item_id, future))

            # Flush if batch is full
            if len(self._pending[batch_key]) >= self._max_batch_size:
                await self._flush_batch(batch_key, fetch_fn)
            else:
                # Schedule flush after timeout
                asyncio.create_task(self._delayed_flush(batch_key, fetch_fn))

        return await future

    async def _delayed_flush(self, batch_key: str, fetch_fn: Callable):
        await asyncio.sleep(self._max_wait_ms / 1000)
        async with self._locks[batch_key]:
            if self._pending[batch_key]:
                await self._flush_batch(batch_key, fetch_fn)

    async def _flush_batch(self, batch_key: str, fetch_fn: Callable):
        if not self._pending[batch_key]:
            return

        batch = self._pending[batch_key]
        self._pending[batch_key] = []

        # Fetch all items in batch
        item_ids = [item_id for item_id, _ in batch]
        results = await fetch_fn(item_ids)

        # Resolve futures
        for (item_id, future), result in zip(batch, results):
            future.set_result(result)

# Usage
batcher = RequestBatcher()

async def fetch_users_batch(user_ids: list[str]) -> list[dict]:
    """Fetch multiple users in single query."""
    return await db.execute(
        "SELECT * FROM users WHERE id = ANY($1)",
        user_ids
    )

@mcp.tool()
async def get_user(user_id: str) -> str:
    user = await batcher.batch_request(
        "users",
        user_id,
        fetch_users_batch
    )
    return json.dumps(user)
```

### Timeout Configuration

**MCP Error -32001**: Request timeout (60-second default in TypeScript clients).

**Solution**: Progress notifications keep connections alive.

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def with_progress(mcp_context, operation: str, total: int):
    """Context manager that sends progress updates."""
    async def send_progress(current: int):
        await mcp_context.send_progress(
            progress_token=operation,
            progress=current,
            total=total
        )

    try:
        yield send_progress
    finally:
        pass

@mcp.tool()
async def process_large_dataset(file_path: str) -> str:
    total_rows = await count_rows(file_path)

    async with with_progress(mcp.context, "processing", total_rows) as send_progress:
        processed = 0

        async for batch in read_batches(file_path):
            await process_batch(batch)
            processed += len(batch)

            # Send progress every 5 seconds
            if processed % 1000 == 0:
                await send_progress(processed)

    return f"Processed {total_rows} rows"
```

**Note**: TypeScript clients have a hard 60-second limit that doesn't reset with progress updates. Design long operations as async workflows with callbacks.

### Implementation Priority

Based on community research, implement optimizations in this order:

1. **Connection pooling** (10 minutes, 80% improvement)
2. **Basic caching** (20 minutes, 15% improvement)
3. **Request batching** (30 minutes, 5% improvement)

Total time: ~1 hour for 90%+ performance gain.

---

## 6. Security Best Practices

### Authentication

**Transport-Level Authentication**: Authentication happens at the transport layer, NOT within MCP messages.

#### OAuth 2.1 (Recommended for HTTP)

MCP specification supports OAuth 2.1 for non-stdio transports.

**Implementation** (with Keycloak):

```python
from fastapi import FastAPI, Header, HTTPException
from fastapi.security import OAuth2PasswordBearer
import httpx
import jwt

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class AuthMiddleware:
    def __init__(self, keycloak_url: str, realm: str):
        self.keycloak_url = keycloak_url
        self.realm = realm
        self.jwks_client = jwt.PyJWKClient(
            f"{keycloak_url}/realms/{realm}/protocol/openid-connect/certs"
        )

    async def validate_token(self, token: str) -> dict:
        """Validate JWT token and extract user info."""
        try:
            # Get signing key
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)

            # Decode and validate
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience="mcp-server",  # Must match server's audience
                options={"verify_exp": True}
            )

            return {
                "user_id": payload.get("sub"),
                "email": payload.get("email"),
                "roles": payload.get("realm_access", {}).get("roles", [])
            }
        except jwt.ExpiredSignatureError:
            raise HTTPException(401, "Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(401, "Invalid token")

auth = AuthMiddleware(
    keycloak_url=os.getenv("KEYCLOAK_URL"),
    realm=os.getenv("KEYCLOAK_REALM")
)

@app.post("/mcp")
async def mcp_endpoint(
    request: dict,
    authorization: str = Header(...)
):
    # Extract bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")

    token = authorization[7:]
    user_info = await auth.validate_token(token)

    # Add user context to request
    request["user"] = user_info

    # Process MCP request
    response = await mcp.handle_request(request)
    return response
```

**Resource Indicators**: Clients must include the MCP server's address in the `resource` parameter during authorization. The resulting token includes this as the `audience` claim, ensuring tokens are scoped to specific servers.

#### API Keys (Simple Auth)

For internal services or development:

```python
import secrets
from functools import wraps

# Generate secure API keys
def generate_api_key() -> str:
    return secrets.token_urlsafe(32)

# Store in database with hashing
async def store_api_key(user_id: str, key: str):
    hashed = bcrypt.hashpw(key.encode(), bcrypt.gensalt())
    await db.execute(
        "INSERT INTO api_keys (user_id, key_hash) VALUES ($1, $2)",
        user_id, hashed
    )

# Validate in middleware
async def validate_api_key(key: str) -> dict:
    result = await db.fetch_one(
        "SELECT user_id, key_hash FROM api_keys WHERE active = true"
    )

    for row in result:
        if bcrypt.checkpw(key.encode(), row["key_hash"]):
            return {"user_id": row["user_id"]}

    raise HTTPException(401, "Invalid API key")
```

#### Mutual TLS (High Security)

For highly secure environments:

```python
import ssl
from fastapi import FastAPI

app = FastAPI()

# Configure SSL context with client certificate verification
ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
ssl_context.load_cert_chain(
    certfile="server-cert.pem",
    keyfile="server-key.pem"
)
ssl_context.load_verify_locations(cafile="ca-cert.pem")
ssl_context.verify_mode = ssl.CERT_REQUIRED

# Run with mTLS
import uvicorn
uvicorn.run(app, ssl_context=ssl_context)
```

### Authorization

**Principle of Least Privilege**: Grant minimal necessary permissions.

#### Role-Based Access Control (RBAC)

```python
from enum import Enum
from typing import Set

class Permission(Enum):
    READ_TOOLS = "read:tools"
    WRITE_TOOLS = "write:tools"
    MANAGE_USERS = "manage:users"
    MANAGE_ROLES = "manage:roles"

class Role(Enum):
    VIEWER = "viewer"
    USER = "user"
    ADMIN = "admin"

ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.VIEWER: {Permission.READ_TOOLS},
    Role.USER: {Permission.READ_TOOLS, Permission.WRITE_TOOLS},
    Role.ADMIN: {
        Permission.READ_TOOLS,
        Permission.WRITE_TOOLS,
        Permission.MANAGE_USERS,
        Permission.MANAGE_ROLES
    }
}

def has_permission(user_roles: list[str], required: Permission) -> bool:
    """Check if user has required permission via their roles."""
    for role_name in user_roles:
        try:
            role = Role(role_name)
            if required in ROLE_PERMISSIONS[role]:
                return True
        except ValueError:
            continue
    return False

# Decorator for tool authorization
def require_permission(permission: Permission):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = kwargs.get("user")  # Injected by auth middleware
            if not user:
                raise HTTPException(401, "Not authenticated")

            if not has_permission(user.get("roles", []), permission):
                raise HTTPException(
                    403,
                    f"Missing required permission: {permission.value}"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Usage in tools
@mcp.tool()
@require_permission(Permission.WRITE_TOOLS)
async def create_issue(title: str, description: str, user: dict = None) -> str:
    """Create a new issue (requires write permission)."""
    issue = await db.create_issue(
        title=title,
        description=description,
        created_by=user["user_id"]
    )
    return f"Created issue #{issue.id}"

@mcp.tool()
@require_permission(Permission.READ_TOOLS)
async def list_issues(user: dict = None) -> str:
    """List issues (requires read permission)."""
    issues = await db.get_issues()
    return json.dumps(issues)
```

#### Tool-Level Scoping

Different tools require different permissions:

```python
@mcp.tool()
@require_permission(Permission.READ_TOOLS)
async def get_user_profile(user_id: str) -> str:
    """Read user profile (safe operation)."""
    pass

@mcp.tool()
@require_permission(Permission.WRITE_TOOLS)
async def update_user_profile(user_id: str, data: dict) -> str:
    """Update user profile (requires write permission)."""
    pass

@mcp.tool()
@require_permission(Permission.MANAGE_USERS)
async def delete_user(user_id: str) -> str:
    """Delete user (admin only)."""
    pass
```

### Input Validation

**Critical Defense**: Every parameter must undergo strict validation.

#### Schema Validation

Use Pydantic for strong type safety:

```python
from pydantic import BaseModel, Field, validator, EmailStr
from typing import Literal

class CreateUserInput(BaseModel):
    email: EmailStr = Field(description="User email address")
    name: str = Field(min_length=1, max_length=100)
    role: Literal["viewer", "user", "admin"] = Field(default="user")

    @validator("name")
    def validate_name(cls, v):
        # No special characters
        if not v.replace(" ", "").isalnum():
            raise ValueError("Name must be alphanumeric")
        return v

@mcp.tool()
async def create_user(input: CreateUserInput) -> str:
    # Input already validated by Pydantic
    user = await db.create_user(
        email=input.email,
        name=input.name,
        role=input.role
    )
    return f"Created user: {user.id}"
```

#### Path Traversal Prevention

Critical for file access tools:

```python
import os
from pathlib import Path

SAFE_BASE_DIR = Path("/var/mcp/files").resolve()

def validate_file_path(requested_path: str) -> Path:
    """Validate file path to prevent directory traversal."""
    # Resolve to absolute path
    requested = (SAFE_BASE_DIR / requested_path).resolve()

    # Ensure it's within base directory
    if not str(requested).startswith(str(SAFE_BASE_DIR)):
        raise ValueError(f"Path traversal attempt: {requested_path}")

    return requested

@mcp.tool()
async def read_file(path: str) -> str:
    """Read file with path validation."""
    safe_path = validate_file_path(path)

    if not safe_path.exists():
        return json.dumps({"error": "File not found"})

    if not safe_path.is_file():
        return json.dumps({"error": "Not a file"})

    return safe_path.read_text()
```

#### SQL Injection Prevention

Always use parameterized queries:

```python
# DON'T: String interpolation
async def get_user_unsafe(email: str) -> dict:
    query = f"SELECT * FROM users WHERE email = '{email}'"  # VULNERABLE
    return await db.fetch_one(query)

# DO: Parameterized queries
async def get_user_safe(email: str) -> dict:
    query = "SELECT * FROM users WHERE email = $1"
    return await db.fetch_one(query, email)
```

#### Command Injection Prevention

Avoid shell execution; use libraries instead:

```python
import subprocess

# DON'T: Shell execution with user input
async def ping_host_unsafe(host: str):
    result = subprocess.run(f"ping -c 1 {host}", shell=True)  # VULNERABLE

# DO: Parameterized execution
async def ping_host_safe(host: str):
    # Validate hostname format
    if not re.match(r'^[a-zA-Z0-9.-]+$', host):
        raise ValueError("Invalid hostname")

    result = subprocess.run(
        ["ping", "-c", "1", host],
        shell=False,  # No shell injection
        capture_output=True,
        timeout=5
    )
    return result.returncode == 0
```

#### Sanitization and Normalization

```python
import html
import re

def sanitize_html(text: str) -> str:
    """Remove HTML tags and escape special characters."""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Escape HTML entities
    return html.escape(text)

def normalize_email(email: str) -> str:
    """Normalize email to lowercase."""
    return email.strip().lower()

@mcp.tool()
async def create_post(title: str, content: str) -> str:
    """Create blog post with sanitized content."""
    safe_title = sanitize_html(title)
    safe_content = sanitize_html(content)

    post = await db.create_post(title=safe_title, content=safe_content)
    return f"Created post #{post.id}"
```

### Encryption

**Transport Encryption**: All remote MCP connections MUST use TLS 1.2+.

```python
import uvicorn

# Production HTTPS configuration
uvicorn.run(
    app,
    host="0.0.0.0",
    port=443,
    ssl_keyfile="/path/to/private.key",
    ssl_certfile="/path/to/certificate.crt",
    ssl_ca_certs="/path/to/ca-bundle.crt",
    ssl_version=ssl.PROTOCOL_TLSv1_2  # Minimum TLS 1.2
)
```

**Certificate Validation**:

```python
import httpx

# Verify server certificates
async with httpx.AsyncClient(verify=True) as client:
    response = await client.get("https://api.example.com")

# Certificate pinning (advanced)
import certifi
async with httpx.AsyncClient(verify=certifi.where()) as client:
    response = await client.get("https://api.example.com")
```

### Rate Limiting

Protect against abuse and DoS:

```python
from datetime import datetime, timedelta
from collections import defaultdict

class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self.requests: Dict[str, list[datetime]] = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        now = datetime.utcnow()
        cutoff = now - self.window

        # Remove old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > cutoff
        ]

        # Check limit
        if len(self.requests[client_id]) >= self.max_requests:
            return False

        # Record request
        self.requests[client_id].append(now)
        return True

rate_limiter = RateLimiter(max_requests=100, window_seconds=60)

@app.post("/mcp")
async def mcp_endpoint(request: dict, user: dict):
    if not rate_limiter.is_allowed(user["user_id"]):
        raise HTTPException(429, "Rate limit exceeded")

    return await mcp.handle_request(request)
```

**Redis-Based Rate Limiting** (for distributed systems):

```python
import redis.asyncio as redis

class DistributedRateLimiter:
    def __init__(self, redis_client: redis.Redis, max_requests: int, window_seconds: int):
        self.redis = redis_client
        self.max_requests = max_requests
        self.window = window_seconds

    async def is_allowed(self, client_id: str) -> bool:
        key = f"rate_limit:{client_id}"

        # Use Redis pipeline for atomic operations
        pipe = self.redis.pipeline()
        now = datetime.utcnow().timestamp()

        # Remove old entries
        pipe.zremrangebyscore(key, 0, now - self.window)
        # Count remaining entries
        pipe.zcard(key)
        # Add current request
        pipe.zadd(key, {str(now): now})
        # Set expiry
        pipe.expire(key, self.window)

        results = await pipe.execute()
        count = results[1]

        return count < self.max_requests
```

### Security Checklist

- [ ] **Authentication**: Implement OAuth 2.1, API keys, or mTLS
- [ ] **Authorization**: RBAC with least-privilege access
- [ ] **Input Validation**: Schema validation, path traversal prevention, SQL/command injection prevention
- [ ] **Encryption**: TLS 1.2+ for all remote connections
- [ ] **Certificate Validation**: Verify server certificates, consider pinning
- [ ] **Rate Limiting**: Protect against abuse (100 req/min baseline)
- [ ] **Secrets Management**: Environment variables, never hardcode
- [ ] **Logging**: Audit logs for security events (auth failures, permission denials)
- [ ] **Error Handling**: Don't leak internal details in error messages
- [ ] **Dependency Scanning**: Regularly update dependencies, scan for vulnerabilities
- [ ] **Security Headers**: HSTS, CSP, X-Frame-Options for HTTP servers
- [ ] **Isolation**: Run in containers/VPCs, avoid direct internet exposure
- [ ] **Monitoring**: Alert on suspicious activity (brute force, unusual patterns)

---

## 7. Error Handling Standards

### JSON-RPC 2.0 Error Codes

MCP inherits standard JSON-RPC 2.0 error codes:

| Code | Meaning | When to Use |
|------|---------|-------------|
| -32700 | Parse error | Invalid JSON syntax |
| -32600 | Invalid Request | JSON-RPC structure invalid |
| -32601 | Method not found | Unknown method called |
| -32602 | Invalid params | Parameter validation failed |
| -32603 | Internal error | Server-side error |
| -32000 to -32099 | Server errors | Custom application errors |

### MCP-Specific Error Codes

| Code | Error | Description |
|------|-------|-------------|
| -32001 | Request timeout | Request exceeded timeout (default 60s) |
| -32002 | Resource not found | Requested resource doesn't exist |
| -32003 | Tool execution failed | Tool encountered error |

### Error Response Structure

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32002,
    "message": "Resource not found",
    "data": {
      "uri": "config://app/missing.yml",
      "suggestion": "Check available resources with resources/list"
    }
  },
  "id": 1
}
```

### Context-Aware Error Handling

Provide actionable error messages that help the LLM understand what failed and how to proceed:

```python
# Poor error
raise ResourceError("Invalid query")

# Good error
raise ResourceError(
    "Database query failed: syntax error near 'WHERE'. "
    "Check SQL syntax. Example: SELECT * FROM users WHERE id = $1"
)

# Excellent error with recovery suggestion
if not await db.table_exists(table_name):
    available_tables = await db.list_tables()
    raise ResourceError(
        f"Table '{table_name}' does not exist. "
        f"Available tables: {', '.join(available_tables)}"
    )
```

### Tool Execution Errors

Tools return success with `isError` flag instead of throwing:

```python
@mcp.tool()
async def query_database(sql: str) -> str:
    try:
        result = await db.execute(sql)
        return json.dumps({"success": True, "data": result})
    except Exception as e:
        # Return error as success response with isError flag
        return json.dumps({
            "isError": True,
            "error": {
                "type": "database_error",
                "message": str(e),
                "sql": sql,
                "suggestion": "Check SQL syntax and table names"
            }
        })
```

### Error Masking

Protect internal details in production:

```python
# Development: Show full stack traces
mcp = FastMCP("my-server", mask_error_details=False)

# Production: Mask internal errors, preserve ResourceError
mcp = FastMCP("my-server", mask_error_details=True)

# ResourceError always sent to client
raise ResourceError("User-facing error message")

# Standard exceptions masked in production
raise ValueError("Internal error")  # Logged, not sent to client
```

### Logging Errors

Comprehensive error logging for debugging:

```python
import logging
from datetime import datetime

logger = logging.getLogger("mcp.errors")

@mcp.tool()
async def risky_operation(input: str) -> str:
    try:
        result = await perform_operation(input)
        return json.dumps(result)
    except Exception as e:
        # Log full error details
        logger.error(
            "Tool execution failed",
            extra={
                "tool": "risky_operation",
                "input": input,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "timestamp": datetime.utcnow().isoformat(),
                "stack_trace": traceback.format_exc()
            }
        )

        # Return sanitized error to client
        return json.dumps({
            "isError": True,
            "error": "Operation failed. Please contact support.",
            "error_id": str(uuid.uuid4())  # For support lookup
        })
```

---

## 8. Testing Strategies

### Unit Testing

Test tools and resources in isolation:

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_create_user_success():
    with patch("my_server.db.create_user") as mock_create:
        mock_create.return_value = {"id": "123", "email": "test@example.com"}

        result = await create_user(
            CreateUserInput(email="test@example.com", name="Test User")
        )

        assert "Created user: 123" in result
        mock_create.assert_called_once()

@pytest.mark.asyncio
async def test_create_user_validation():
    with pytest.raises(ValueError, match="Name must be alphanumeric"):
        await create_user(
            CreateUserInput(email="test@example.com", name="Test<script>")
        )
```

### Integration Testing

Test with real MCP client:

```python
import pytest
from mcp import ClientSession, StdioServerParameters
import json

@pytest.mark.asyncio
async def test_mcp_tool_integration():
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "my_server"],
        env={"TRANSPORT": "stdio"}
    )

    async with ClientSession(server_params) as session:
        # Initialize
        await session.initialize()

        # List tools
        tools = await session.list_tools()
        assert any(tool.name == "create_user" for tool in tools.tools)

        # Call tool
        result = await session.call_tool(
            "create_user",
            arguments={
                "email": "test@example.com",
                "name": "Test User",
                "role": "user"
            }
        )

        assert result.isError is False
        assert "Created user" in result.content[0].text

@pytest.mark.asyncio
async def test_resource_access():
    async with ClientSession(server_params) as session:
        await session.initialize()

        # Read resource
        content = await session.read_resource("config://app/settings.yml")
        assert content.contents[0].mimeType == "text/yaml"
```

### Load Testing

Verify performance under stress:

```python
import asyncio
import time
from statistics import mean, stdev

async def load_test_tool(concurrency: int, requests_per_client: int):
    """Load test MCP tool with concurrent clients."""

    async def client_worker(client_id: int):
        latencies = []

        async with ClientSession(server_params) as session:
            await session.initialize()

            for i in range(requests_per_client):
                start = time.time()
                await session.call_tool("list_users", arguments={})
                latency = (time.time() - start) * 1000
                latencies.append(latency)

        return latencies

    # Run concurrent clients
    tasks = [client_worker(i) for i in range(concurrency)]
    all_latencies = await asyncio.gather(*tasks)

    # Flatten results
    latencies = [lat for client_lats in all_latencies for lat in client_lats]

    print(f"Concurrency: {concurrency}")
    print(f"Total requests: {len(latencies)}")
    print(f"Mean latency: {mean(latencies):.2f}ms")
    print(f"Std dev: {stdev(latencies):.2f}ms")
    print(f"Min: {min(latencies):.2f}ms")
    print(f"Max: {max(latencies):.2f}ms")
    print(f"P95: {sorted(latencies)[int(len(latencies) * 0.95)]:.2f}ms")

# Run load test
asyncio.run(load_test_tool(concurrency=10, requests_per_client=100))
```

### Security Testing

Verify authentication, authorization, and input validation:

```python
@pytest.mark.asyncio
async def test_authentication_required():
    """Verify requests without auth token are rejected."""
    response = await client.post("/mcp", json={"method": "tools/list"})
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_authorization_enforcement():
    """Verify users can't access resources beyond their permissions."""
    viewer_token = get_token(role="viewer")

    response = await client.post(
        "/mcp",
        json={"method": "tools/call", "params": {"name": "delete_user"}},
        headers={"Authorization": f"Bearer {viewer_token}"}
    )

    assert response.status_code == 403

@pytest.mark.asyncio
async def test_path_traversal_prevention():
    """Verify path traversal attempts are blocked."""
    result = await session.call_tool("read_file", arguments={"path": "../../../etc/passwd"})
    assert result.isError is True
    assert "Path traversal" in str(result.content)

@pytest.mark.asyncio
async def test_sql_injection_prevention():
    """Verify SQL injection attempts are blocked."""
    result = await session.call_tool(
        "search_users",
        arguments={"query": "'; DROP TABLE users; --"}
    )
    # Should return empty results, not execute SQL
    assert result.isError is False
```

---

## 9. Production Deployment

### Environment Configuration

Separate configuration for dev/staging/production:

```python
from pydantic_settings import BaseSettings
from typing import Literal

class Settings(BaseSettings):
    # Environment
    environment: Literal["development", "staging", "production"] = "development"

    # Transport
    transport: Literal["http", "stdio"] = "http"
    http_host: str = "0.0.0.0"
    http_port: int = 8000

    # Security
    oauth_enabled: bool = False
    keycloak_url: str = ""
    keycloak_realm: str = ""
    keycloak_client_id: str = ""
    keycloak_client_secret: str = ""

    # Performance
    max_file_size: int = 1048576  # 1MB
    command_timeout: int = 30
    idle_timeout: int = 60
    connection_pool_size: int = 20
    cache_ttl: int = 60

    # Logging
    log_level: str = "INFO"
    log_payloads: bool = False
    include_traceback: bool = False

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60

    # Database
    database_url: str = ""

    # Redis
    redis_url: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen

# Copy application
COPY . .

# Non-root user
RUN useradd -m -u 1000 mcp && chown -R mcp:mcp /app
USER mcp

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run server
CMD ["uv", "run", "python", "-m", "my_server"]
```

### Docker Compose

```yaml
services:
  mcp-server:
    build: .
    ports:
      - "53000:8000"
    environment:
      - ENVIRONMENT=production
      - TRANSPORT=http
      - HTTP_HOST=0.0.0.0
      - HTTP_PORT=8000
      - DATABASE_URL=postgresql://user:pass@db:5432/mcp
      - REDIS_URL=redis://redis:6379/0
      - OAUTH_ENABLED=true
      - KEYCLOAK_URL=https://auth.example.com
      - LOG_LEVEL=INFO
    depends_on:
      - db
      - redis
    restart: unless-stopped
    networks:
      - mcp-network

  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=mcp
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - mcp-network

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    networks:
      - mcp-network

volumes:
  postgres_data:
  redis_data:

networks:
  mcp-network:
    driver: bridge
```

### Monitoring and Observability

```python
import logging
from datetime import datetime
from contextvars import ContextVar

# Structured logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S | %m/%d/%Y'
)

logger = logging.getLogger("mcp")

# Request context
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

class RequestLoggingMiddleware:
    async def __call__(self, request: dict, call_next):
        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)

        logger.info(
            f"Request started",
            extra={
                "request_id": request_id,
                "method": request.get("method"),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        start = time.time()

        try:
            response = await call_next(request)
            duration = (time.time() - start) * 1000

            logger.info(
                f"Request completed",
                extra={
                    "request_id": request_id,
                    "duration_ms": duration,
                    "status": "success"
                }
            )

            return response
        except Exception as e:
            duration = (time.time() - start) * 1000

            logger.error(
                f"Request failed",
                extra={
                    "request_id": request_id,
                    "duration_ms": duration,
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
            )
            raise

# Metrics collection
from prometheus_client import Counter, Histogram, start_http_server

request_counter = Counter("mcp_requests_total", "Total requests", ["method", "status"])
request_duration = Histogram("mcp_request_duration_seconds", "Request duration", ["method"])
tool_calls = Counter("mcp_tool_calls_total", "Tool calls", ["tool_name", "status"])

# Start metrics server
start_http_server(9090)
```

---

## 10. Key Takeaways and Recommendations

### Critical Best Practices

1. **Use Streamable HTTP transport** for production deployments (single endpoint, session management, scalability)

2. **Implement connection pooling first** - it's 80% of your performance improvement for ~10 minutes of work

3. **Design domain-aware tools** - avoid CRUD operations, use high-level semantic actions

4. **Validate all inputs** - schema validation, path traversal prevention, SQL/command injection prevention

5. **Implement OAuth 2.1** for authentication with resource indicators for token scoping

6. **Use RBAC for authorization** with least-privilege access and tool-level permissions

7. **Return error strings from tools** - never raise exceptions to MCP clients

8. **Structure URIs logically** with descriptive schemes and RFC 6570 templates

9. **Cache with background refresh** - serve cached data instantly while updating in background

10. **Monitor and log everything** - structured logging, request IDs, metrics collection

### Common Pitfalls to Avoid

❌ **Using STDIO for multi-client scenarios** - Use HTTP transport
❌ **Exposing low-level CRUD operations as tools** - Design domain-aware actions
❌ **Hardcoding secrets in code** - Use environment variables
❌ **Skipping input validation** - Validate everything at API boundaries
❌ **Creating new connections per request** - Implement connection pooling
❌ **Leaking internal errors to clients** - Use structured error responses
❌ **Using standard ports (80, 443, 3000, 5432)** - Use high ports (53000+)
❌ **Granting broad permissions by default** - Use least-privilege access
❌ **Ignoring rate limiting** - Protect against abuse
❌ **Not implementing health checks** - Essential for monitoring

### Implementation Roadmap

**Week 1: Foundation**
- Set up project structure with proper separation (models/services/utils/tools)
- Implement basic tools and resources with schema validation
- Configure Streamable HTTP transport with health check endpoint

**Week 2: Security**
- Implement authentication (OAuth 2.1 or API keys)
- Add RBAC with role-to-permission mapping
- Input validation for all parameters

**Week 3: Performance**
- Connection pooling for databases and external APIs
- Basic caching with 60-second TTL
- Request batching for similar operations

**Week 4: Production Readiness**
- Structured logging with request IDs
- Metrics collection (Prometheus)
- Rate limiting and circuit breakers
- Docker containerization
- Load testing and security testing

### Additional Resources

**Official Documentation**:
- [MCP Specification 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18)
- [GitHub Repository](https://github.com/modelcontextprotocol/modelcontextprotocol)
- [Anthropic MCP Introduction](https://www.anthropic.com/news/model-context-protocol)

**Implementation Guides**:
- [FastMCP Resources Guide](https://gofastmcp.com/servers/resources)
- [Speakeasy MCP Building Servers](https://www.speakeasy.com/mcp/building-servers/protocol-reference/resources)
- [MCP Authentication Guide](https://stytch.com/blog/MCP-authentication-and-authorization-guide/)

**Performance & Security**:
- [MCP Performance Optimization](https://dev.to/leomarsh/mcp-mastery-part-6-why-your-mcp-server-is-slow-and-how-to-fix-it-2356)
- [Securing MCP Servers](https://www.infracloud.io/blogs/securing-mcp-servers/)
- [MCP Security Best Practices](https://www.mcpevals.io/blog/mcp-security-best-practices)

**Production Deployment**:
- [Building Streamable HTTP MCP Servers](https://mcpcat.io/guides/building-streamablehttp-mcp-server/)
- [MCP Health Check Endpoints](https://mcpcat.io/guides/building-health-check-endpoint-mcp-server/)
- [MCP Server Transports](https://docs.roocode.com/features/mcp/server-transports)

---

## Sources

- [MCP Specification (2025-06-18)](https://modelcontextprotocol.io/specification/2025-06-18)
- [MCP GitHub Repository](https://github.com/modelcontextprotocol/modelcontextprotocol)
- [Anthropic Introduction to MCP](https://www.anthropic.com/news/model-context-protocol)
- [MCP Complete Guide 2025](https://www.keywordsai.co/blog/introduction-to-mcp)
- [Claude Code Best Practices](https://www.anthropic.com/engineering/claude-code-best-practices)
- [MCP Best Practices Guide](https://oshea00.github.io/posts/mcp-practices/)
- [FastMCP Resources Documentation](https://gofastmcp.com/servers/resources)
- [Speakeasy MCP Resources](https://www.speakeasy.com/mcp/building-servers/protocol-reference/resources)
- [MCP Resources Specification](https://spec.modelcontextprotocol.io/specification/2025-03-26/server/resources/)
- [MCP Error Codes](https://www.mcpevals.io/blog/mcp-error-codes)
- [MCP Transports Specification](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
- [HTTP Stream Transport](https://mcp-framework.com/docs/Transports/http-stream-transport/)
- [MCP Server Transports Guide](https://docs.roocode.com/features/mcp/server-transports)
- [MCP Performance Optimization](https://dev.to/leomarsh/mcp-mastery-part-6-why-your-mcp-server-is-slow-and-how-to-fix-it-2356)
- [MCP Connection Pooling](https://www.byteplus.com/en/topic/542260)
- [Building StreamableHTTP MCP Servers](https://mcpcat.io/guides/building-streamablehttp-mcp-server/)
- [Fixing MCP Timeout Errors](https://mcpcat.io/guides/fixing-mcp-error-32001-request-timeout/)
- [MCP Authorization Specification](https://modelcontextprotocol.io/specification/draft/basic/authorization)
- [Auth0 MCP Authorization Guide](https://auth0.com/blog/an-introduction-to-mcp-and-authorization/)
- [Securing MCP Servers](https://www.infracloud.io/blogs/securing-mcp-servers/)
- [MCP Authentication Guide](https://stytch.com/blog/MCP-authentication-and-authorization-guide/)
- [MCP Security Checklist](https://www.gopher.security/mcp-security/mcp-security-checklist-owasp-best-practices)
- [MCP Security Best Practices](https://www.mcpevals.io/blog/mcp-security-best-practices)
- [MCP Server Security](https://www.truefoundry.com/blog/mcp-server-security-best-practices)

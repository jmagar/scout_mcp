# Streamable HTTP Transport Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the MCP server run as streamable HTTP by default instead of STDIO, enabling network accessibility and multi-client support.

**Architecture:** Add transport configuration to the server module with environment variable controls. The server will default to HTTP transport with configurable host/port. STDIO transport remains available via environment variable for backward compatibility with Claude Desktop.

**Tech Stack:** FastMCP 2.0+, Python 3.11+, pytest-asyncio

---

## Task 1: Add Transport Configuration to Config

**Files:**
- Modify: [scout_mcp/config.py](scout_mcp/config.py:12-58)
- Test: [tests/test_config.py](tests/test_config.py) (create if doesn't exist)

**Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
"""Tests for configuration management."""

import os
from pathlib import Path

import pytest

from scout_mcp.config import Config


class TestTransportConfig:
    """Tests for transport configuration."""

    def test_default_transport_is_http(self, tmp_path: Path) -> None:
        """Default transport should be http."""
        config = Config(ssh_config_path=tmp_path / "ssh_config")
        assert config.transport == "http"

    def test_default_host_is_localhost(self, tmp_path: Path) -> None:
        """Default host should be 127.0.0.1."""
        config = Config(ssh_config_path=tmp_path / "ssh_config")
        assert config.http_host == "127.0.0.1"

    def test_default_port_is_8000(self, tmp_path: Path) -> None:
        """Default port should be 8000."""
        config = Config(ssh_config_path=tmp_path / "ssh_config")
        assert config.http_port == 8000

    def test_transport_from_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Transport can be set via SCOUT_TRANSPORT env var."""
        monkeypatch.setenv("SCOUT_TRANSPORT", "stdio")
        config = Config(ssh_config_path=tmp_path / "ssh_config")
        assert config.transport == "stdio"

    def test_host_from_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Host can be set via SCOUT_HTTP_HOST env var."""
        monkeypatch.setenv("SCOUT_HTTP_HOST", "0.0.0.0")
        config = Config(ssh_config_path=tmp_path / "ssh_config")
        assert config.http_host == "0.0.0.0"

    def test_port_from_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Port can be set via SCOUT_HTTP_PORT env var."""
        monkeypatch.setenv("SCOUT_HTTP_PORT", "9000")
        config = Config(ssh_config_path=tmp_path / "ssh_config")
        assert config.http_port == 9000

    def test_invalid_port_uses_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid port value falls back to default."""
        monkeypatch.setenv("SCOUT_HTTP_PORT", "not-a-number")
        config = Config(ssh_config_path=tmp_path / "ssh_config")
        assert config.http_port == 8000

    def test_invalid_transport_uses_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid transport value falls back to http."""
        monkeypatch.setenv("SCOUT_TRANSPORT", "invalid")
        config = Config(ssh_config_path=tmp_path / "ssh_config")
        assert config.transport == "http"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `AttributeError: 'Config' object has no attribute 'transport'`

**Step 3: Write minimal implementation**

Edit `scout_mcp/config.py` - add new fields to the Config dataclass after line 22:

```python
@dataclass
class Config:
    """Scout MCP configuration."""

    ssh_config_path: Path = field(
        default_factory=lambda: Path.home() / ".ssh" / "config"
    )
    allowlist: list[str] = field(default_factory=list)
    blocklist: list[str] = field(default_factory=list)
    max_file_size: int = 1_048_576  # 1MB
    command_timeout: int = 30
    idle_timeout: int = 60
    # Transport configuration
    transport: str = "http"  # "http" or "stdio"
    http_host: str = "127.0.0.1"
    http_port: int = 8000

    _hosts: dict[str, SSHHost] = field(default_factory=dict, init=False, repr=False)
    _parsed: bool = field(default=False, init=False, repr=False)
```

Then update `__post_init__` to handle the new env vars:

```python
    def __post_init__(self) -> None:
        """Apply environment variable overrides."""
        import os
        from contextlib import suppress

        def get_env_int(scout_key: str, legacy_key: str) -> int | None:
            if val := os.getenv(scout_key):
                with suppress(ValueError):
                    return int(val)
            if val := os.getenv(legacy_key):
                with suppress(ValueError):
                    return int(val)
            return None

        val = get_env_int("SCOUT_MAX_FILE_SIZE", "MCP_CAT_MAX_FILE_SIZE")
        if val is not None:
            self.max_file_size = val

        val = get_env_int("SCOUT_COMMAND_TIMEOUT", "MCP_CAT_COMMAND_TIMEOUT")
        if val is not None:
            self.command_timeout = val

        val = get_env_int("SCOUT_IDLE_TIMEOUT", "MCP_CAT_IDLE_TIMEOUT")
        if val is not None:
            self.idle_timeout = val

        # Transport configuration
        transport = os.getenv("SCOUT_TRANSPORT", "").lower()
        if transport in ("http", "stdio"):
            self.transport = transport

        if http_host := os.getenv("SCOUT_HTTP_HOST"):
            self.http_host = http_host

        http_port = get_env_int("SCOUT_HTTP_PORT", "")
        if http_port is not None:
            self.http_port = http_port
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_config.py scout_mcp/config.py
git commit -m "feat: add transport configuration to Config dataclass"
```

---

## Task 2: Update __main__.py to Use Transport Config

**Files:**
- Modify: [scout_mcp/__main__.py](scout_mcp/__main__.py:1-6)
- Test: `tests/test_main.py` (create)

**Step 1: Write the failing test**

Create `tests/test_main.py`:

```python
"""Tests for main entry point."""

from unittest.mock import MagicMock, patch

import pytest


class TestMain:
    """Tests for __main__ module."""

    def test_runs_with_http_transport_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Server runs with HTTP transport by default."""
        mock_mcp = MagicMock()
        mock_config = MagicMock()
        mock_config.transport = "http"
        mock_config.http_host = "127.0.0.1"
        mock_config.http_port = 8000

        with patch("scout_mcp.__main__.mcp", mock_mcp), \
             patch("scout_mcp.__main__.get_config", return_value=mock_config):
            # Import triggers if __name__ == "__main__" but we test run_server()
            from scout_mcp.__main__ import run_server
            run_server()

        mock_mcp.run.assert_called_once_with(
            transport="http",
            host="127.0.0.1",
            port=8000,
        )

    def test_runs_with_stdio_when_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Server runs with STDIO transport when configured."""
        mock_mcp = MagicMock()
        mock_config = MagicMock()
        mock_config.transport = "stdio"

        with patch("scout_mcp.__main__.mcp", mock_mcp), \
             patch("scout_mcp.__main__.get_config", return_value=mock_config):
            from scout_mcp.__main__ import run_server
            run_server()

        mock_mcp.run.assert_called_once_with(transport="stdio")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_main.py -v`
Expected: FAIL with `ImportError: cannot import name 'run_server' from 'scout_mcp.__main__'`

**Step 3: Write minimal implementation**

Replace `scout_mcp/__main__.py`:

```python
"""Entry point for scout_mcp server."""

from scout_mcp.server import mcp
from scout_mcp.services import get_config


def run_server() -> None:
    """Run the MCP server with configured transport."""
    config = get_config()

    if config.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(
            transport="http",
            host=config.http_host,
            port=config.http_port,
        )


if __name__ == "__main__":
    run_server()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_main.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scout_mcp/__main__.py tests/test_main.py
git commit -m "feat: use transport config in main entry point"
```

---

## Task 3: Add Health Check Endpoint

**Files:**
- Modify: [scout_mcp/server.py](scout_mcp/server.py:303-327)
- Test: `tests/test_health.py` (create)

**Step 1: Write the failing test**

Create `tests/test_health.py`:

```python
"""Tests for health check endpoint."""

from unittest.mock import patch

import pytest
from starlette.testclient import TestClient


class TestHealthCheck:
    """Tests for health check endpoint."""

    @pytest.fixture
    def client(self, tmp_path):
        """Create test client for HTTP server."""
        from pathlib import Path
        from scout_mcp.config import Config
        from scout_mcp.server import create_server

        ssh_config = tmp_path / "ssh_config"
        ssh_config.write_text("Host test\n    HostName 127.0.0.1\n")
        config = Config(ssh_config_path=ssh_config)

        with patch("scout_mcp.server.get_config", return_value=config):
            server = create_server()
            # Get the ASGI app for testing
            app = server.http_app()
            return TestClient(app)

    def test_health_returns_ok(self, client) -> None:
        """Health endpoint returns OK status."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.text == "OK"

    def test_health_returns_plain_text(self, client) -> None:
        """Health endpoint returns plain text content type."""
        response = client.get("/health")
        assert "text/plain" in response.headers["content-type"]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_health.py -v`
Expected: FAIL with `404 Not Found` (health endpoint doesn't exist)

**Step 3: Write minimal implementation**

Add to `scout_mcp/server.py` in `create_server()` function, before `return server`:

```python
from starlette.responses import PlainTextResponse

def create_server() -> FastMCP:
    """Create and configure the MCP server with all middleware and resources."""
    server = FastMCP(
        "scout_mcp",
        lifespan=app_lifespan,
    )

    configure_middleware(server)

    # Register tools
    server.tool()(scout)

    # Register resources
    server.resource("scout://{host}/{path*}")(scout_resource)
    server.resource("hosts://list")(list_hosts_resource)

    # Add health check endpoint for HTTP transport
    @server.custom_route("/health", methods=["GET"])
    async def health_check(request):  # type: ignore[no-untyped-def]
        """Health check endpoint."""
        return PlainTextResponse("OK")

    return server
```

Also add the import at the top of the file:

```python
from starlette.responses import PlainTextResponse
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_health.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scout_mcp/server.py tests/test_health.py
git commit -m "feat: add /health endpoint for HTTP transport"
```

---

## Task 4: Add starlette Dependency

**Files:**
- Modify: [pyproject.toml](pyproject.toml:1-11)

**Step 1: Verify starlette is needed**

Run: `uv run python -c "from starlette.responses import PlainTextResponse; print('OK')"`
Expected: May work (FastMCP includes it) or fail if not bundled

**Step 2: Add dependency if needed**

If starlette is not bundled with FastMCP, edit `pyproject.toml`:

```toml
dependencies = [
    "fastmcp>=2.0.0",
    "asyncssh>=2.14.0",
    "starlette>=0.36.0",
]
```

**Step 3: Run tests to verify**

Run: `uv run pytest tests/test_health.py -v`
Expected: PASS

**Step 4: Commit (if changed)**

```bash
git add pyproject.toml
git commit -m "chore: add starlette dependency for health endpoint"
```

---

## Task 5: Update Documentation

**Files:**
- Modify: [CLAUDE.md](CLAUDE.md)

**Step 1: Update environment variables table**

Add new environment variables to the Configuration section:

```markdown
### Environment Variables
| Variable | Default | Purpose |
|----------|---------|---------|
| `SCOUT_TRANSPORT` | http | Transport protocol: "http" or "stdio" |
| `SCOUT_HTTP_HOST` | 127.0.0.1 | HTTP server bind address |
| `SCOUT_HTTP_PORT` | 8000 | HTTP server port |
| `SCOUT_MAX_FILE_SIZE` | 1048576 | Max file size in bytes (1MB) |
| `SCOUT_COMMAND_TIMEOUT` | 30 | Command timeout in seconds |
| `SCOUT_IDLE_TIMEOUT` | 60 | Connection idle timeout |
| `SCOUT_LOG_PAYLOADS` | false | Enable payload logging |
| `SCOUT_SLOW_THRESHOLD_MS` | 1000 | Slow request threshold |
| `SCOUT_INCLUDE_TRACEBACK` | false | Include tracebacks in error logs |
```

**Step 2: Update MCP Client Configuration section**

```markdown
### MCP Client Configuration (HTTP - Default)
```json
{
  "mcpServers": {
    "scout_mcp": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

### MCP Client Configuration (STDIO - Legacy)
```json
{
  "mcpServers": {
    "scout_mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/code/scout_mcp", "python", "-m", "scout_mcp"],
      "env": {
        "SCOUT_TRANSPORT": "stdio"
      }
    }
  }
}
```
```

**Step 3: Add Quick Reference commands**

```markdown
## Quick Reference

```bash
# Run server (HTTP on localhost:8000)
uv run python -m scout_mcp

# Run server on custom port
SCOUT_HTTP_PORT=9000 uv run python -m scout_mcp

# Run server on all interfaces
SCOUT_HTTP_HOST=0.0.0.0 uv run python -m scout_mcp

# Run with STDIO transport (for Claude Desktop)
SCOUT_TRANSPORT=stdio uv run python -m scout_mcp

# Run tests
uv run pytest tests/ -v
```
```

**Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update documentation for HTTP transport"
```

---

## Task 6: Run Full Test Suite

**Files:**
- None (verification only)

**Step 1: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

**Step 2: Run type checking**

Run: `uv run mypy scout_mcp/`
Expected: No errors

**Step 3: Run linting**

Run: `uv run ruff check scout_mcp/ tests/ --fix`
Expected: No errors

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup for streamable HTTP transport"
```

---

## Summary

After completing all tasks:

1. **Default transport** is now HTTP (streamable) instead of STDIO
2. **Server binds** to `127.0.0.1:8000` by default
3. **Environment variables** control transport, host, and port
4. **Health endpoint** at `/health` for monitoring
5. **STDIO still available** via `SCOUT_TRANSPORT=stdio` for backward compatibility
6. **Documentation updated** with new configuration options

**New Environment Variables:**
- `SCOUT_TRANSPORT` - "http" (default) or "stdio"
- `SCOUT_HTTP_HOST` - Bind address (default: "127.0.0.1")
- `SCOUT_HTTP_PORT` - Listen port (default: 8000)

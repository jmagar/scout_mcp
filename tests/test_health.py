"""Tests for health check endpoint."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient


class TestHealthCheck:
    """Tests for health check endpoint."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> TestClient:
        """Create test client for HTTP server."""
        from scout_mcp.config import Config
        from scout_mcp.server import create_server

        ssh_config = tmp_path / "ssh_config"
        ssh_config.write_text("Host test\n    HostName 127.0.0.1\n")
        config = Config.from_ssh_config(ssh_config_path=ssh_config)

        with patch("scout_mcp.server.get_config", return_value=config):
            server = create_server()
            # Get the ASGI app for testing
            app = server.http_app()
            return TestClient(app)

    def test_health_returns_ok(self, client: Any) -> None:
        """Health endpoint returns OK status."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.text == "OK"

    def test_health_returns_plain_text(self, client: Any) -> None:
        """Health endpoint returns plain text content type."""
        response = client.get("/health")
        assert "text/plain" in response.headers["content-type"]

"""Tests for main entry point."""

from unittest.mock import MagicMock, patch

import pytest


class TestMain:
    """Tests for __main__ module."""

    def test_runs_with_http_transport_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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

    def test_runs_with_stdio_when_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Server runs with STDIO transport when configured."""
        mock_mcp = MagicMock()
        mock_config = MagicMock()
        mock_config.transport = "stdio"

        with patch("scout_mcp.__main__.mcp", mock_mcp), \
             patch("scout_mcp.__main__.get_config", return_value=mock_config):
            from scout_mcp.__main__ import run_server
            run_server()

        mock_mcp.run.assert_called_once_with(transport="stdio")

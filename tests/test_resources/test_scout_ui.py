"""Tests for scout resource UI integration."""

import pytest

from scout_mcp.resources.scout import scout_resource


@pytest.mark.asyncio
async def test_scout_resource_returns_ui_for_directory(monkeypatch):
    """Test scout resource returns UI for directory listings."""
    # Mock the dependencies
    from unittest.mock import AsyncMock, MagicMock

    mock_config = MagicMock()
    mock_config.get_host.return_value = {"hostname": "tootie"}
    mock_config.max_file_size = 1048576

    mock_conn = AsyncMock()

    monkeypatch.setattr(
        "scout_mcp.resources.scout.get_config",
        lambda: mock_config
    )
    monkeypatch.setattr(
        "scout_mcp.resources.scout.get_connection_with_retry",
        AsyncMock(return_value=mock_conn)
    )
    monkeypatch.setattr(
        "scout_mcp.resources.scout.stat_path",
        AsyncMock(return_value="directory")
    )
    monkeypatch.setattr(
        "scout_mcp.resources.scout.ls_dir",
        AsyncMock(return_value="total 8\ndrwxr-xr-x 2 user group 4096 Dec 7 10:00 .")
    )

    result = await scout_resource("tootie", "/mnt/cache")

    # Should return UIResource dict, not plain text
    assert isinstance(result, dict)
    assert result["type"] == "resource"
    assert str(result["resource"]["uri"]).startswith("ui://")
    assert result["resource"]["mimeType"] == "text/html"


@pytest.mark.asyncio
async def test_scout_resource_returns_ui_for_markdown(monkeypatch):
    """Test scout resource returns UI for markdown files."""
    from unittest.mock import AsyncMock, MagicMock

    mock_config = MagicMock()
    mock_config.get_host.return_value = {"hostname": "tootie"}
    mock_config.max_file_size = 1048576

    mock_conn = AsyncMock()

    monkeypatch.setattr(
        "scout_mcp.resources.scout.get_config",
        lambda: mock_config
    )
    monkeypatch.setattr(
        "scout_mcp.resources.scout.get_connection_with_retry",
        AsyncMock(return_value=mock_conn)
    )
    monkeypatch.setattr(
        "scout_mcp.resources.scout.stat_path",
        AsyncMock(return_value="file")
    )
    monkeypatch.setattr(
        "scout_mcp.resources.scout.cat_file",
        AsyncMock(return_value=("# Hello", False))
    )

    result = await scout_resource("tootie", "/docs/README.md")

    assert isinstance(result, dict)
    assert result["type"] == "resource"
    assert "markdown" in str(result["resource"]["uri"])


@pytest.mark.asyncio
async def test_scout_resource_returns_ui_for_logs(monkeypatch):
    """Test scout resource returns UI for log files."""
    from unittest.mock import AsyncMock, MagicMock

    mock_config = MagicMock()
    mock_config.get_host.return_value = {"hostname": "tootie"}
    mock_config.max_file_size = 1048576

    mock_conn = AsyncMock()

    monkeypatch.setattr(
        "scout_mcp.resources.scout.get_config",
        lambda: mock_config
    )
    monkeypatch.setattr(
        "scout_mcp.resources.scout.get_connection_with_retry",
        AsyncMock(return_value=mock_conn)
    )
    monkeypatch.setattr(
        "scout_mcp.resources.scout.stat_path",
        AsyncMock(return_value="file")
    )
    monkeypatch.setattr(
        "scout_mcp.resources.scout.cat_file",
        AsyncMock(return_value=("[2025-12-07] INFO: test", False))
    )

    result = await scout_resource("tootie", "/var/log/app.log")

    assert isinstance(result, dict)
    assert result["type"] == "resource"
    assert "logs" in str(result["resource"]["uri"])

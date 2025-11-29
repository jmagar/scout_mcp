"""Tests for Docker Compose executor functions."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from scout_mcp.services.executors import compose_config, compose_logs, compose_ls


@pytest.mark.asyncio
async def test_compose_ls_returns_projects() -> None:
    """compose_ls returns list of compose projects."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout='[{"Name":"plex","Status":"running(1)","ConfigFiles":"/compose/plex/docker-compose.yaml"}]',
            returncode=0,
        )
    )

    projects = await compose_ls(mock_conn)

    assert len(projects) == 1
    assert projects[0]["name"] == "plex"
    assert "running" in projects[0]["status"]
    assert "/compose/plex" in projects[0]["config_file"]


@pytest.mark.asyncio
async def test_compose_ls_returns_empty_on_error() -> None:
    """compose_ls returns empty list on Docker error."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="docker compose not found",
            returncode=127,
        )
    )

    projects = await compose_ls(mock_conn)

    assert projects == []


@pytest.mark.asyncio
async def test_compose_config_returns_content() -> None:
    """compose_config returns config file content."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        side_effect=[
            MagicMock(
                stdout='[{"Name":"plex","Status":"running(1)","ConfigFiles":"/compose/plex/docker-compose.yaml"}]',
                returncode=0,
            ),
            MagicMock(
                stdout="services:\n  plex:\n    image: plex",
                returncode=0,
            ),
        ]
    )

    content, path = await compose_config(mock_conn, "plex")

    assert "services:" in content
    assert path == "/compose/plex/docker-compose.yaml"


@pytest.mark.asyncio
async def test_compose_config_project_not_found() -> None:
    """compose_config returns empty for missing project."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout='[{"Name":"other","Status":"running(1)","ConfigFiles":"/compose/other/docker-compose.yaml"}]',
            returncode=0,
        )
    )

    content, path = await compose_config(mock_conn, "missing")

    assert content == ""
    assert path is None


@pytest.mark.asyncio
async def test_compose_logs_returns_logs() -> None:
    """compose_logs returns stack logs."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="plex  | Starting Plex Media Server",
            returncode=0,
        )
    )

    logs, exists = await compose_logs(mock_conn, "plex")

    assert exists is True
    assert "Starting Plex" in logs


@pytest.mark.asyncio
async def test_compose_logs_project_not_found() -> None:
    """compose_logs returns exists=False for missing project."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="no configuration file provided: not found",
            returncode=1,
        )
    )

    logs, exists = await compose_logs(mock_conn, "missing")

    assert exists is False
    assert logs == ""

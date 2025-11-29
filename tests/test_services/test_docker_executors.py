"""Tests for Docker executor functions."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from scout_mcp.services.executors import docker_inspect, docker_logs, docker_ps


@pytest.mark.asyncio
async def test_docker_logs_returns_logs() -> None:
    """docker_logs returns container logs."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="2024-01-01T00:00:00Z Log line 1\n2024-01-01T00:00:01Z Log line 2",
            returncode=0,
        )
    )

    logs, exists = await docker_logs(mock_conn, "plex")

    assert exists is True
    assert "Log line 1" in logs
    assert "Log line 2" in logs
    mock_conn.run.assert_called_once()


@pytest.mark.asyncio
async def test_docker_logs_container_not_found() -> None:
    """docker_logs returns exists=False for missing container."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="Error: No such container: missing",
            returncode=1,
        )
    )

    logs, exists = await docker_logs(mock_conn, "missing")

    assert exists is False
    assert logs == ""


@pytest.mark.asyncio
async def test_docker_logs_docker_error_raises() -> None:
    """docker_logs raises RuntimeError on Docker daemon errors."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="Cannot connect to Docker daemon",
            returncode=1,
        )
    )

    with pytest.raises(RuntimeError, match="Docker error"):
        await docker_logs(mock_conn, "plex")


@pytest.mark.asyncio
async def test_docker_ps_returns_containers() -> None:
    """docker_ps returns list of containers."""
    mock_conn = AsyncMock()
    docker_output = (
        "plex\tUp 2 days\tplexinc/pms-docker\n"
        "nginx\tExited (0)\tnginx:latest"
    )
    mock_conn.run = AsyncMock(
        return_value=MagicMock(stdout=docker_output, returncode=0)
    )

    containers = await docker_ps(mock_conn)

    assert len(containers) == 2
    assert containers[0]["name"] == "plex"
    assert "Up" in containers[0]["status"]
    assert containers[1]["name"] == "nginx"


@pytest.mark.asyncio
async def test_docker_ps_returns_empty_when_docker_unavailable() -> None:
    """docker_ps returns empty list when Docker not available."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        return_value=MagicMock(
            stdout="docker: command not found",
            returncode=127,
        )
    )

    containers = await docker_ps(mock_conn)

    assert containers == []


@pytest.mark.asyncio
async def test_docker_inspect_returns_true_when_exists() -> None:
    """docker_inspect returns True for existing container."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(return_value=MagicMock(returncode=0))

    exists = await docker_inspect(mock_conn, "plex")

    assert exists is True


@pytest.mark.asyncio
async def test_docker_inspect_returns_false_when_missing() -> None:
    """docker_inspect returns False for missing container."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(return_value=MagicMock(returncode=1))

    exists = await docker_inspect(mock_conn, "missing")

    assert exists is False

"""Tests for syslog executor functions."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from scout_mcp.services.executors import syslog_read


@pytest.mark.asyncio
async def test_syslog_read_uses_journalctl_when_available() -> None:
    """syslog_read uses journalctl when available."""
    mock_conn = AsyncMock()
    # First call: check journalctl exists (returns 0)
    # Second call: get journalctl output
    mock_conn.run = AsyncMock(
        side_effect=[
            MagicMock(returncode=0),  # command -v journalctl
            MagicMock(
                stdout="Nov 29 12:00:00 host sshd[123]: Connection from 10.0.0.1",
                returncode=0,
            ),
        ]
    )

    logs, source = await syslog_read(mock_conn, lines=100)

    assert "sshd" in logs
    assert source == "journalctl"


@pytest.mark.asyncio
async def test_syslog_read_falls_back_to_syslog_file() -> None:
    """syslog_read falls back to /var/log/syslog when no journalctl."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        side_effect=[
            MagicMock(returncode=1),  # command -v journalctl (not found)
            MagicMock(returncode=0),  # test -r /var/log/syslog
            MagicMock(
                stdout="Nov 29 12:00:00 host kernel: Linux version 5.15",
                returncode=0,
            ),
        ]
    )

    logs, source = await syslog_read(mock_conn, lines=100)

    assert "kernel" in logs
    assert source == "syslog"


@pytest.mark.asyncio
async def test_syslog_read_returns_empty_when_no_logs() -> None:
    """syslog_read returns empty when no log source available."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(
        side_effect=[
            MagicMock(returncode=1),  # command -v journalctl (not found)
            MagicMock(returncode=1),  # test -r /var/log/syslog (not readable)
        ]
    )

    logs, source = await syslog_read(mock_conn, lines=100)

    assert logs == ""
    assert source == "none"

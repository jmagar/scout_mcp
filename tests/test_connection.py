"""Tests for connection retry helper."""

from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scout_mcp.services.connection import (
    ConnectionError,
    get_connection_with_retry,
)


@pytest.fixture
def mock_pool() -> Generator[Any, None, None]:
    """Mock connection pool."""
    with patch("scout_mcp.services.state.get_pool") as mock:
        yield mock.return_value


@pytest.fixture
def mock_host() -> MagicMock:
    """Mock SSH host configuration."""
    host = MagicMock()
    host.name = "test-host"
    return host


class TestGetConnectionWithRetry:
    """Test connection retry helper."""

    @pytest.mark.asyncio
    async def test_success_first_try(self, mock_pool: Any, mock_host: Any) -> None:
        """Connection succeeds on first attempt."""
        mock_conn = AsyncMock()
        mock_pool.get_connection = AsyncMock(return_value=mock_conn)

        result = await get_connection_with_retry(mock_host)

        assert result == mock_conn
        mock_pool.get_connection.assert_called_once_with(mock_host)

    @pytest.mark.asyncio
    async def test_success_after_retry(self, mock_pool: Any, mock_host: Any) -> None:
        """Connection fails first, succeeds on retry."""
        mock_conn = AsyncMock()
        mock_pool.get_connection = AsyncMock(
            side_effect=[Exception("First fail"), mock_conn]
        )
        mock_pool.remove_connection = AsyncMock()

        result = await get_connection_with_retry(mock_host)

        assert result == mock_conn
        assert mock_pool.get_connection.call_count == 2
        mock_pool.remove_connection.assert_called_once_with("test-host")

    @pytest.mark.asyncio
    async def test_failure_after_retry(self, mock_pool: Any, mock_host: Any) -> None:
        """Connection fails on both attempts."""
        mock_pool.get_connection = AsyncMock(
            side_effect=[Exception("First"), Exception("Second")]
        )
        mock_pool.remove_connection = AsyncMock()

        with pytest.raises(ConnectionError) as exc_info:
            await get_connection_with_retry(mock_host)

        assert "test-host" in str(exc_info.value)
        assert exc_info.value.host_name == "test-host"
        assert str(exc_info.value.original_error) == "Second"
        assert mock_pool.get_connection.call_count == 2
        mock_pool.remove_connection.assert_called_once_with("test-host")

    @pytest.mark.asyncio
    async def test_connection_error_has_attributes(
        self, mock_pool: Any, mock_host: Any
    ) -> None:
        """ConnectionError stores host name and original error."""
        original_error = Exception("Connection timeout")
        mock_pool.get_connection = AsyncMock(side_effect=[original_error, original_error])
        mock_pool.remove_connection = AsyncMock()

        with pytest.raises(ConnectionError) as exc_info:
            await get_connection_with_retry(mock_host)

        error = exc_info.value
        assert error.host_name == "test-host"
        assert error.original_error is original_error
        assert "test-host" in str(error)
        assert "Connection timeout" in str(error)

    @pytest.mark.asyncio
    async def test_remove_connection_called_on_first_failure(
        self, mock_pool: Any, mock_host: Any
    ) -> None:
        """Pool cleanup is called before retry."""
        mock_conn = AsyncMock()
        mock_pool.get_connection = AsyncMock(
            side_effect=[RuntimeError("Stale"), mock_conn]
        )
        mock_pool.remove_connection = AsyncMock()

        await get_connection_with_retry(mock_host)

        # Verify cleanup was called with correct host name
        mock_pool.remove_connection.assert_called_once_with("test-host")
        # Verify cleanup happened between attempts
        assert mock_pool.get_connection.call_count == 2

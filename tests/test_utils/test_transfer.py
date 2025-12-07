"""Test transfer path detection logic."""

import pytest
from scout_mcp.utils.transfer import (
    TransferPath,
    TransferStrategy,
    determine_transfer_strategy,
)


def test_determine_strategy_local_to_remote():
    """Test detection of local → remote transfer."""
    strategy = determine_transfer_strategy(
        source_host=None,
        target_host="remote1",
        current_hostname="localhost",
    )

    assert strategy.strategy == TransferStrategy.LOCAL_TO_REMOTE
    assert strategy.source_host is None
    assert strategy.target_host == "remote1"


def test_determine_strategy_remote_to_local():
    """Test detection of remote → local transfer."""
    strategy = determine_transfer_strategy(
        source_host="remote1",
        target_host=None,
        current_hostname="localhost",
    )

    assert strategy.strategy == TransferStrategy.REMOTE_TO_LOCAL
    assert strategy.source_host == "remote1"
    assert strategy.target_host is None


def test_determine_strategy_remote_to_remote_via_relay():
    """Test detection of remote → remote transfer requiring relay."""
    strategy = determine_transfer_strategy(
        source_host="remote1",
        target_host="remote2",
        current_hostname="localhost",
    )

    assert strategy.strategy == TransferStrategy.REMOTE_TO_REMOTE_RELAY
    assert strategy.source_host == "remote1"
    assert strategy.target_host == "remote2"


def test_determine_strategy_optimized_current_as_source():
    """Test optimization when MCP server is the source host."""
    strategy = determine_transfer_strategy(
        source_host="tootie",
        target_host="remote1",
        current_hostname="tootie",
    )

    assert strategy.strategy == TransferStrategy.LOCAL_TO_REMOTE
    assert strategy.source_host is None  # Optimized to local
    assert strategy.target_host == "remote1"


def test_determine_strategy_optimized_current_as_target():
    """Test optimization when MCP server is the target host."""
    strategy = determine_transfer_strategy(
        source_host="remote1",
        target_host="tootie",
        current_hostname="tootie",
    )

    assert strategy.strategy == TransferStrategy.REMOTE_TO_LOCAL
    assert strategy.source_host == "remote1"
    assert strategy.target_host is None  # Optimized to local


def test_determine_strategy_same_source_and_target():
    """Test error when source and target are the same."""
    with pytest.raises(ValueError, match="Source and target cannot be the same"):
        determine_transfer_strategy(
            source_host="remote1",
            target_host="remote1",
            current_hostname="localhost",
        )

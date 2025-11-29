"""Tests for scout URI parsing and intent detection."""

import pytest

from scout_mcp.scout import parse_target


def test_parse_target_file_uri() -> None:
    """Parse host:/path/to/file URI."""
    result = parse_target("dookie:/var/log/app.log")

    assert result.host == "dookie"
    assert result.path == "/var/log/app.log"


def test_parse_target_dir_uri() -> None:
    """Parse host:/path/to/dir URI."""
    result = parse_target("tootie:/etc/nginx")

    assert result.host == "tootie"
    assert result.path == "/etc/nginx"


def test_parse_target_home_expansion() -> None:
    """Parse URI with ~ home directory."""
    result = parse_target("squirts:~/code/project")

    assert result.host == "squirts"
    assert result.path == "~/code/project"


def test_parse_target_hosts_command() -> None:
    """Parse 'hosts' as special command."""
    result = parse_target("hosts")

    assert result.host is None
    assert result.is_hosts_command is True


def test_parse_target_invalid_raises() -> None:
    """Invalid URI raises ValueError."""
    with pytest.raises(ValueError, match="Invalid target"):
        parse_target("invalid-no-colon")


def test_parse_target_empty_path_raises() -> None:
    """Empty path raises ValueError."""
    with pytest.raises(ValueError, match="Path cannot be empty"):
        parse_target("dookie:")


def test_parse_target_empty_host_raises() -> None:
    """Empty host raises ValueError."""
    with pytest.raises(ValueError, match="Host cannot be empty"):
        parse_target(":/var/log")

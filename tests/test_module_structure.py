"""Tests for module structure after refactoring.

These tests verify that the new module structure is in place
and all imports work correctly from the new locations.
"""

import pytest


class TestModelsModule:
    """Tests for scout_mcp.models package."""

    def test_import_ssh_host(self) -> None:
        """SSHHost can be imported from models."""
        from scout_mcp.models import SSHHost

        host = SSHHost(name="test", hostname="192.168.1.1")
        assert host.name == "test"
        assert host.hostname == "192.168.1.1"
        assert host.user == "root"  # default
        assert host.port == 22  # default

    def test_import_pooled_connection(self) -> None:
        """PooledConnection can be imported from models."""
        from scout_mcp.models import PooledConnection

        # Just verify import works
        assert PooledConnection is not None

    def test_import_command_result(self) -> None:
        """CommandResult can be imported from models."""
        from scout_mcp.models import CommandResult

        result = CommandResult(output="hello", error="", returncode=0)
        assert result.output == "hello"
        assert result.returncode == 0

    def test_import_scout_target(self) -> None:
        """ScoutTarget can be imported from models."""
        from scout_mcp.models import ScoutTarget

        target = ScoutTarget(host="tootie", path="/etc/hosts")
        assert target.host == "tootie"
        assert target.path == "/etc/hosts"


class TestServicesModule:
    """Tests for scout_mcp.services package."""

    def test_import_get_config(self) -> None:
        """get_config can be imported from services."""
        from scout_mcp.services import get_config

        assert callable(get_config)

    def test_import_get_pool(self) -> None:
        """get_pool can be imported from services."""
        from scout_mcp.services import get_pool

        assert callable(get_pool)

    def test_import_connection_pool(self) -> None:
        """ConnectionPool can be imported from services."""
        from scout_mcp.services import ConnectionPool

        pool = ConnectionPool(idle_timeout=30)
        assert pool.idle_timeout == 30

    def test_import_executors(self) -> None:
        """Executor functions can be imported from services."""
        from scout_mcp.services import (
            cat_file,
            ls_dir,
            run_command,
            stat_path,
            tree_dir,
        )

        assert callable(cat_file)
        assert callable(ls_dir)
        assert callable(run_command)
        assert callable(stat_path)
        assert callable(tree_dir)


class TestUtilsModule:
    """Tests for scout_mcp.utils package."""

    def test_import_parse_target(self) -> None:
        """parse_target can be imported from utils."""
        from scout_mcp.utils import parse_target

        result = parse_target("tootie:/etc/hosts")
        assert result.host == "tootie"
        assert result.path == "/etc/hosts"

    def test_import_ping_functions(self) -> None:
        """Ping functions can be imported from utils."""
        from scout_mcp.utils import check_host_online, check_hosts_online

        assert callable(check_host_online)
        assert callable(check_hosts_online)

    def test_import_get_mime_type(self) -> None:
        """get_mime_type can be imported from utils."""
        from scout_mcp.utils import get_mime_type

        assert get_mime_type("/path/to/file.py") == "text/x-python"
        assert get_mime_type("/path/to/file.json") == "application/json"


class TestToolsModule:
    """Tests for scout_mcp.tools package."""

    def test_import_scout_tool(self) -> None:
        """scout tool function can be imported from tools."""
        from scout_mcp.tools import scout

        assert callable(scout)


class TestResourcesModule:
    """Tests for scout_mcp.resources package."""

    def test_import_scout_resource(self) -> None:
        """scout_resource can be imported from resources."""
        from scout_mcp.resources import scout_resource

        assert callable(scout_resource)

    def test_import_list_hosts_resource(self) -> None:
        """list_hosts_resource can be imported from resources."""
        from scout_mcp.resources import list_hosts_resource

        assert callable(list_hosts_resource)


class TestBackwardCompatibility:
    """Tests for backward-compatible imports from root module."""

    def test_config_still_importable_from_root(self) -> None:
        """Config can still be imported from scout_mcp.config."""
        from scout_mcp.config import Config

        config = Config()
        assert config is not None

    def test_server_exports_mcp(self) -> None:
        """server.py exports the mcp FastMCP instance."""
        from scout_mcp.server import mcp

        assert mcp is not None
        assert mcp.name == "scout_mcp"

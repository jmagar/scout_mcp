"""Tests for resource plugin base class."""
import pytest

from scout_mcp.resources.plugin import ResourcePlugin


def test_plugin_requires_uri_template():
    """Verify ResourcePlugin enforces get_uri_template implementation."""

    class IncompletePlugin(ResourcePlugin):
        async def handle(self, host: str, **params) -> str:
            return "test"

    with pytest.raises(TypeError):
        IncompletePlugin()


def test_plugin_requires_handle():
    """Verify ResourcePlugin enforces handle implementation."""

    class IncompletePlugin(ResourcePlugin):
        def get_uri_template(self) -> str:
            return "{host}://test"

    with pytest.raises(TypeError):
        IncompletePlugin()


def test_plugin_name_generation():
    """Verify plugin generates name from class name."""

    class DockerLogsPlugin(ResourcePlugin):
        def get_uri_template(self) -> str:
            return "{host}://docker/{container}/logs"

        async def handle(self, host: str, **params) -> str:
            return "logs"

    plugin = DockerLogsPlugin()
    assert plugin.get_name() == "dockerlogs"


def test_plugin_description_fallback():
    """Verify plugin uses class name if no docstring."""

    class TestPlugin(ResourcePlugin):
        def get_uri_template(self) -> str:
            return "{host}://test"

        async def handle(self, host: str, **params) -> str:
            return "test"

    plugin = TestPlugin()
    assert "test" in plugin.get_description().lower()


def test_plugin_description_from_docstring():
    """Verify plugin uses docstring for description."""

    class TestPlugin(ResourcePlugin):
        """Custom description for this plugin."""

        def get_uri_template(self) -> str:
            return "{host}://test"

        async def handle(self, host: str, **params) -> str:
            return "test"

    plugin = TestPlugin()
    assert plugin.get_description() == "Custom description for this plugin."


def test_plugin_mime_type_default():
    """Verify plugin defaults to text/plain."""

    class TestPlugin(ResourcePlugin):
        def get_uri_template(self) -> str:
            return "{host}://test"

        async def handle(self, host: str, **params) -> str:
            return "test"

    plugin = TestPlugin()
    assert plugin.get_mime_type() == "text/plain"

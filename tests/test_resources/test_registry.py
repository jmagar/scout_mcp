"""Tests for resource registry."""
import pytest

from scout_mcp.resources.registry import ResourceRegistry
from scout_mcp.resources.plugin import ResourcePlugin


@pytest.fixture
def registry():
    """Create empty resource registry."""
    return ResourceRegistry()


def test_register_resource_plugin(registry):
    """Verify plugins can be registered with registry."""

    class TestPlugin(ResourcePlugin):
        def get_uri_template(self) -> str:
            return "{host}://test/{{item}}"

        async def handle(self, host: str, item: str) -> str:
            return f"test-{host}-{item}"

    plugin = TestPlugin()
    registry.register(plugin)

    assert len(registry.plugins) == 1
    assert registry.plugins[0] == plugin


def test_registry_generates_resources_for_hosts(registry):
    """Verify registry creates resources for each host."""

    class TestPlugin(ResourcePlugin):
        def get_uri_template(self) -> str:
            return "{host}://test/{{item}}"

        async def handle(self, host: str, item: str) -> str:
            return f"test-{host}-{item}"

    hosts = {"host1": object(), "host2": object()}
    registry.register(TestPlugin())

    resources = registry.create_resources(hosts)

    assert len(resources) == 2
    assert any(r["uri"] == "host1://test/{item}" for r in resources)
    assert any(r["uri"] == "host2://test/{item}" for r in resources)

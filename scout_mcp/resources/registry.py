"""Resource registry for dynamic resource registration.

Reduces code duplication by managing resource creation from plugins.
"""
import logging
from collections.abc import Callable
from typing import Any

from scout_mcp.models import SSHHost
from scout_mcp.resources.plugin import ResourcePlugin

logger = logging.getLogger(__name__)


class ResourceRegistry:
    """Registry for resource plugins.

    Manages registration and creation of host-specific resources.
    Eliminates duplication in server.py app_lifespan.
    """

    def __init__(self):
        self.plugins: list[ResourcePlugin] = []

    def register(self, plugin: ResourcePlugin) -> None:
        """Register a resource plugin.

        Args:
            plugin: Plugin instance to register
        """
        self.plugins.append(plugin)
        logger.debug("Registered resource plugin: %s", plugin.get_name())

    def create_resources(
        self,
        hosts: dict[str, SSHHost],
    ) -> list[dict[str, Any]]:
        """Create resource definitions for all hosts.

        Args:
            hosts: Dictionary of hostname -> SSHHost

        Returns:
            List of resource definition dicts for FastMCP
        """
        resources = []

        for plugin in self.plugins:
            for host_name in hosts:
                uri = plugin.get_uri_template().format(host=host_name)
                resources.append({
                    "uri": uri,
                    "name": f"{host_name} {plugin.get_name()}",
                    "description": plugin.get_description(),
                    "mime_type": plugin.get_mime_type(),
                    "handler": self._create_handler(plugin, host_name),
                })

        logger.info(
            "Created %d resources from %d plugins",
            len(resources),
            len(self.plugins),
        )
        return resources

    def _create_handler(
        self,
        plugin: ResourcePlugin,
        host_name: str,
    ) -> Callable:
        """Create handler function for specific host.

        Args:
            plugin: Plugin instance
            host_name: Hostname for this handler

        Returns:
            Async handler function
        """

        async def handler(**params: Any) -> str:
            return await plugin.handle(host_name, **params)

        return handler

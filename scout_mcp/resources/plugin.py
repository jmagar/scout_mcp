"""Resource plugin system for dynamic resource registration.

Enables clean registration of host-specific resources without
code duplication.
"""
from abc import ABC, abstractmethod
from typing import Any


class ResourcePlugin(ABC):
    """Base class for resource plugins.

    Each plugin defines a resource type (docker logs, compose logs, etc.)
    that should be registered for each SSH host.
    """

    @abstractmethod
    def get_uri_template(self) -> str:
        """Get URI template with {host} placeholder.

        Example: "{host}://docker/{container}/logs"
        """
        pass

    @abstractmethod
    async def handle(self, host: str, **params: Any) -> str:
        """Handle resource request.

        Args:
            host: SSH hostname
            **params: URI parameters (container, project, etc.)

        Returns:
            Resource content as string
        """
        pass

    def get_name(self) -> str:
        """Get resource name for metadata."""
        return self.__class__.__name__.replace("Plugin", "").lower()

    def get_description(self) -> str:
        """Get resource description for metadata."""
        return self.__doc__ or f"{self.get_name()} resource"

    def get_mime_type(self) -> str:
        """Get MIME type for resource."""
        return "text/plain"

"""Configuration module for Scout MCP.

Provides focused classes for different configuration concerns:
- Config: Main configuration class (aggregates all components)
- SSHConfigParser: Parses ~/.ssh/config files
- HostKeyVerifier: Manages SSH host key verification
- Settings: Environment variable configuration
"""

from scout_mcp.config.host_keys import HostKeyVerifier
from scout_mcp.config.main import Config
from scout_mcp.config.parser import SSHConfigParser
from scout_mcp.config.settings import Settings

__all__ = ["Config", "SSHConfigParser", "HostKeyVerifier", "Settings"]

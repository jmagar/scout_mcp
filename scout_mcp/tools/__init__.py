"""MCP tools for Scout MCP."""

from scout_mcp.tools.scout import scout
from scout_mcp.tools.ui_tests import (
    test_external_url,
    test_raw_html,
    test_remote_dom,
)

__all__ = ["scout", "test_raw_html", "test_remote_dom", "test_external_url"]

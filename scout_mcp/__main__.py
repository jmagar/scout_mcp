"""Entry point for scout_mcp server."""

from scout_mcp.server import mcp
from scout_mcp.services import get_config


def run_server() -> None:
    """Run the MCP server with configured transport."""
    config = get_config()

    if config.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(
            transport="http",
            host=config.http_host,
            port=config.http_port,
        )


if __name__ == "__main__":
    run_server()

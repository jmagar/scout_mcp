"""Entry point for scout_mcp server."""

import logging
import os

from scout_mcp.server import mcp  # This imports also configures logging
from scout_mcp.services import get_config

logger = logging.getLogger(__name__)


def _quiet_third_party_loggers() -> None:
    """Reduce noise from third-party libraries."""
    logging.getLogger("asyncssh").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)


def configure_logging() -> None:
    """Configure additional logging settings for direct execution.

    Note: Core logging is already configured in server.py at import time.
    This just quiets noisy third-party loggers when running via __main__.
    """
    config = get_config()
    _quiet_third_party_loggers()

    log_level = os.getenv("SCOUT_LOG_LEVEL", "DEBUG").upper()
    logger.info(
        "Logging configured: level=%s, transport=%s",
        log_level,
        config.transport,
    )


def run_server() -> None:
    """Run the MCP server with configured transport."""
    config = get_config()
    configure_logging()

    if config.transport == "stdio":
        logger.info("Starting Scout MCP server (transport=stdio)")
        mcp.run(transport="stdio")
    else:
        logger.info(
            "Starting Scout MCP server (transport=http, host=%s, port=%d)",
            config.http_host,
            config.http_port,
        )
        mcp.run(
            transport="http",
            host=config.http_host,
            port=config.http_port,
        )


if __name__ == "__main__":
    run_server()

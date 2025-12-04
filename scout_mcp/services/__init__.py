"""Services for Scout MCP."""

from scout_mcp.services.connection import (
    ConnectionError,
    get_connection_with_retry,
)
from scout_mcp.services.executors import (
    cat_file,
    ls_dir,
    run_command,
    stat_path,
    tree_dir,
)
from scout_mcp.services.pool import ConnectionPool
from scout_mcp.services.state import (
    get_config,
    get_pool,
    reset_state,
    set_config,
    set_pool,
)

__all__ = [
    "ConnectionError",
    "ConnectionPool",
    "cat_file",
    "get_config",
    "get_connection_with_retry",
    "get_pool",
    "ls_dir",
    "reset_state",
    "run_command",
    "set_config",
    "set_pool",
    "stat_path",
    "tree_dir",
]

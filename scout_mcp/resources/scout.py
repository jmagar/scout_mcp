"""Scout resource for reading remote files and directories."""

import logging
from typing import Any, Union

from fastmcp.exceptions import ResourceError

from scout_mcp.services import (
    ConnectionError,
    get_config,
    get_connection_with_retry,
)
from scout_mcp.services.executors import cat_file, ls_dir, stat_path
from scout_mcp.ui import (
    create_directory_ui,
    create_file_viewer_ui,
    create_log_viewer_ui,
    create_markdown_viewer_ui,
)

logger = logging.getLogger(__name__)


def _detect_file_type(path: str) -> str:
    """Detect file type from path extension.

    Args:
        path: File path

    Returns:
        File type: 'markdown', 'log', 'code', or 'text'
    """
    path_lower = path.lower()

    if path_lower.endswith(('.md', '.markdown')):
        return 'markdown'

    if path_lower.endswith(('.log', '.logs')) or '/log/' in path_lower:
        return 'log'

    code_extensions = (
        '.py', '.js', '.ts', '.jsx', '.tsx', '.json', '.yaml', '.yml',
        '.sh', '.bash', '.html', '.css', '.sql', '.go', '.rs', '.java',
        '.c', '.cpp', '.h', '.hpp'
    )
    if path_lower.endswith(code_extensions):
        return 'code'

    return 'text'


def _get_mime_type(path: str) -> str:
    """Get MIME type from file extension.

    Args:
        path: File path

    Returns:
        MIME type string
    """
    ext_map = {
        '.py': 'text/x-python',
        '.js': 'text/javascript',
        '.ts': 'text/typescript',
        '.json': 'application/json',
        '.yaml': 'text/yaml',
        '.yml': 'text/yaml',
        '.sh': 'text/x-shellscript',
        '.md': 'text/markdown',
        '.html': 'text/html',
        '.css': 'text/css',
        '.sql': 'text/x-sql',
    }

    for ext, mime in ext_map.items():
        if path.lower().endswith(ext):
            return mime

    return 'text/plain'


async def scout_resource(host: str, path: str) -> Union[str, dict[str, Any]]:
    """Read remote files or directories via SSH with UI support.

    This resource provides read-only access to remote filesystems.
    Returns interactive UI resources for directories, markdown files,
    and log files. Returns file viewer UI for code and text files.

    Args:
        host: SSH host name from ~/.ssh/config (e.g., "tootie", "squirts")
        path: Remote path to read (e.g., "var/log/app.log", "etc/nginx")

    Returns:
        UIResource dict for UI-enabled content, or string for plain text.

    Examples:
        scout://tootie/var/log/app.log - Interactive log viewer
        scout://squirts/etc/nginx - Interactive file explorer
        scout://dookie/docs/README.md - Markdown viewer with preview
    """
    config = get_config()

    # Validate host exists
    ssh_host = config.get_host(host)
    if ssh_host is None:
        available = ", ".join(sorted(config.get_hosts().keys()))
        raise ResourceError(f"Unknown host '{host}'. Available: {available}")

    # Normalize path - add leading slash if not present
    normalized_path = f"/{path}" if not path.startswith("/") else path

    # Get connection (with one retry on failure)
    try:
        conn = await get_connection_with_retry(ssh_host)
    except ConnectionError as e:
        raise ResourceError(str(e)) from e

    # Determine if path is file or directory
    try:
        path_type = await stat_path(conn, normalized_path)
    except Exception as e:
        raise ResourceError(f"Cannot stat {normalized_path}: {e}") from e

    if path_type is None:
        raise ResourceError(f"Path not found: {normalized_path}")

    # Handle directories with UI
    if path_type == "directory":
        try:
            listing = await ls_dir(conn, normalized_path)
            return await create_directory_ui(host, normalized_path, listing)
        except Exception as e:
            raise ResourceError(f"Failed to read {normalized_path}: {e}") from e

    # Handle files
    try:
        contents, was_truncated = await cat_file(
            conn, normalized_path, config.max_file_size
        )
        if was_truncated:
            contents += f"\n\n[truncated at {config.max_file_size} bytes]"
    except Exception as e:
        raise ResourceError(f"Failed to read {normalized_path}: {e}") from e

    # Determine file type and return appropriate UI
    file_type = _detect_file_type(normalized_path)

    if file_type == 'markdown':
        return await create_markdown_viewer_ui(host, normalized_path, contents)
    elif file_type == 'log':
        return await create_log_viewer_ui(host, normalized_path, contents)
    elif file_type in ('code', 'text'):
        mime_type = _get_mime_type(normalized_path)
        return await create_file_viewer_ui(host, normalized_path, contents, mime_type)
    else:
        # Fallback to plain text
        return contents

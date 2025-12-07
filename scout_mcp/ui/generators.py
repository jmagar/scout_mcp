"""UI resource generators for different file types."""

from typing import Any

from mcp_ui_server import create_ui_resource  # noqa: F401


async def create_directory_ui(
    host: str, path: str, listing: str
) -> dict[str, Any]:
    """Create interactive file explorer UI for directory listings.

    Args:
        host: SSH hostname
        path: Directory path
        listing: Directory listing output from ls -la

    Returns:
        UIResource dict
    """
    from scout_mcp.ui.templates import get_directory_explorer_html

    html = get_directory_explorer_html(host, path, listing)

    ui_resource = create_ui_resource({
        "uri": f"ui://scout-directory/{host}{path}",
        "content": {"type": "rawHtml", "htmlString": html},
        "encoding": "text",
    })

    return ui_resource.model_dump()


async def create_file_viewer_ui(
    host: str, path: str, content: str, mime_type: str = "text/plain"
) -> dict[str, Any]:
    """Create file viewer UI with syntax highlighting.

    Args:
        host: SSH hostname
        path: File path
        content: File contents
        mime_type: MIME type for syntax highlighting

    Returns:
        UIResource dict
    """
    raise NotImplementedError("TODO: Task 4")


async def create_log_viewer_ui(
    host: str, path: str, content: str
) -> dict[str, Any]:
    """Create log viewer UI with filtering and search.

    Args:
        host: SSH hostname
        path: Log file path
        content: Log file contents

    Returns:
        UIResource dict
    """
    raise NotImplementedError("TODO: Task 5")


async def create_markdown_viewer_ui(
    host: str, path: str, content: str
) -> dict[str, Any]:
    """Create markdown viewer UI with rendered preview.

    Args:
        host: SSH hostname
        path: Markdown file path
        content: Markdown content

    Returns:
        UIResource dict
    """
    raise NotImplementedError("TODO: Task 6")

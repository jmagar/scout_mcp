"""UI resource generators for different file types."""


async def create_directory_ui(host: str, path: str, listing: str) -> str:
    """Create interactive file explorer UI for directory listings.

    Args:
        host: SSH hostname
        path: Directory path
        listing: Directory listing output from ls -la

    Returns:
        HTML string for rendering
    """
    from scout_mcp.ui.templates import get_directory_explorer_html

    return get_directory_explorer_html(host, path, listing)


async def create_file_viewer_ui(
    host: str, path: str, content: str, mime_type: str = "text/plain"
) -> str:
    """Create file viewer UI with syntax highlighting.

    Args:
        host: SSH hostname
        path: File path
        content: File contents
        mime_type: MIME type for syntax highlighting

    Returns:
        HTML string for rendering
    """
    from scout_mcp.ui.templates import get_file_viewer_html

    return get_file_viewer_html(host, path, content, mime_type)


async def create_log_viewer_ui(host: str, path: str, content: str) -> str:
    """Create log viewer UI with filtering and search.

    Args:
        host: SSH hostname
        path: Log file path
        content: Log file contents

    Returns:
        HTML string for rendering
    """
    from scout_mcp.ui.templates import get_log_viewer_html

    return get_log_viewer_html(host, path, content)


async def create_markdown_viewer_ui(host: str, path: str, content: str) -> str:
    """Create markdown viewer UI with rendered preview.

    Args:
        host: SSH hostname
        path: Markdown file path
        content: Markdown content

    Returns:
        HTML string for rendering
    """
    from scout_mcp.ui.templates import get_markdown_viewer_html

    return get_markdown_viewer_html(host, path, content)

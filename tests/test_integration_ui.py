"""Integration tests for UI resources."""

import pytest


@pytest.mark.asyncio
async def test_full_ui_integration(monkeypatch):
    """Test complete UI integration flow."""
    # Verify UI module is importable
    from scout_mcp.ui import (
        create_directory_ui,
        create_file_viewer_ui,
        create_log_viewer_ui,
        create_markdown_viewer_ui,
    )

    # All generators should be callable
    assert callable(create_directory_ui)
    assert callable(create_file_viewer_ui)
    assert callable(create_log_viewer_ui)
    assert callable(create_markdown_viewer_ui)


def test_ui_templates_render():
    """Test all UI templates can render without errors."""
    from scout_mcp.ui.templates import (
        get_base_styles,
        get_directory_explorer_html,
        get_file_viewer_html,
        get_log_viewer_html,
        get_markdown_viewer_html,
    )

    # Base styles
    styles = get_base_styles()
    assert '<style>' in styles
    assert 'font-family' in styles

    # Directory explorer
    listing = "total 8\ndrwxr-xr-x 2 user group 4096 Dec 7 10:00 ."
    dir_html = get_directory_explorer_html("test", "/path", listing)
    assert '<!DOCTYPE html>' in dir_html
    assert 'Directory' in dir_html

    # File viewer
    file_html = get_file_viewer_html("test", "/file.py", "print('hello')")
    assert '<!DOCTYPE html>' in file_html
    assert 'File Viewer' in file_html

    # Log viewer
    log_html = get_log_viewer_html("test", "/app.log", "[2025-12-07] INFO: test")
    assert '<!DOCTYPE html>' in log_html
    assert 'Log Viewer' in log_html

    # Markdown viewer
    md_html = get_markdown_viewer_html("test", "/README.md", "# Title")
    assert '<!DOCTYPE html>' in md_html
    assert 'Markdown' in md_html
    assert 'marked' in md_html  # marked.js library

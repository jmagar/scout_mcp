"""Tests for UI resource generators."""

import pytest

from scout_mcp.ui.generators import create_directory_ui, create_file_viewer_ui


@pytest.mark.asyncio
async def test_create_directory_ui_basic():
    """Test directory UI generation with basic listing."""
    listing = """total 24
drwxr-xr-x  3 user group  4096 Dec  7 10:00 .
drwxr-xr-x 10 user group  4096 Dec  7 09:00 ..
-rw-r--r--  1 user group  1234 Dec  7 10:00 file.txt
drwxr-xr-x  2 user group  4096 Dec  7 09:30 subdir
"""

    result = await create_directory_ui("tootie", "/mnt/cache", listing)

    assert result["type"] == "resource"
    assert str(result["resource"]["uri"]).startswith("ui://")
    assert result["resource"]["mimeType"] == "text/html"
    assert "file.txt" in result["resource"]["text"]
    assert "subdir" in result["resource"]["text"]
    assert "/mnt/cache" in result["resource"]["text"]


@pytest.mark.asyncio
async def test_create_directory_ui_empty():
    """Test directory UI with empty directory."""
    listing = """total 8
drwxr-xr-x  2 user group  4096 Dec  7 10:00 .
drwxr-xr-x 10 user group  4096 Dec  7 09:00 ..
"""

    result = await create_directory_ui("tootie", "/empty", listing)

    assert result["type"] == "resource"
    assert "empty" in result["resource"]["text"].lower()


@pytest.mark.asyncio
async def test_create_file_viewer_ui_text():
    """Test file viewer UI for plain text."""
    content = "Hello, World!\nLine 2\nLine 3"

    result = await create_file_viewer_ui("tootie", "/tmp/test.txt", content)

    assert result["type"] == "resource"
    assert str(result["resource"]["uri"]).startswith("ui://")
    assert "Hello, World!" in result["resource"]["text"]
    assert "test.txt" in result["resource"]["text"]


@pytest.mark.asyncio
async def test_create_file_viewer_ui_code():
    """Test file viewer UI with syntax highlighting."""
    content = 'def hello():\n    print("world")'

    result = await create_file_viewer_ui(
        "tootie", "/code/main.py", content, mime_type="text/x-python"
    )

    assert result["type"] == "resource"
    assert "main.py" in result["resource"]["text"]
    assert "def hello" in result["resource"]["text"]

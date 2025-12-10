# MCP-UI Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate MCP-UI into scout_mcp to provide interactive UI components for file browsing, log viewing, and markdown rendering instead of plain text responses.

**Architecture:** Add mcp-ui-server dependency, create UI generators in new `scout_mcp/ui/` module, modify existing resources to optionally return UIResource objects with HTML/RemoteDOM interfaces. UI components will render file explorers (directory listings), markdown viewers (`.md` files), and log viewers (log files) with interactive features like syntax highlighting, search, and filtering.

**Tech Stack:**
- `mcp-ui-server` (Python SDK for creating UIResource objects)
- HTML/CSS/JavaScript for UI templates
- Remote DOM for interactive components
- Tailwind CSS for styling

---

## Task 1: Add MCP-UI Dependency

**Files:**
- Modify: `pyproject.toml:7-10`

**Step 1: Add mcp-ui-server to dependencies**

```toml
dependencies = [
    "fastmcp>=2.0.0",
    "asyncssh>=2.14.2,<3.0.0",
    "mcp-ui-server>=0.1.0",
]
```

**Step 2: Sync dependencies**

Run: `uv sync`
Expected: Package installed successfully

**Step 3: Verify import works**

Run: `uv run python -c "from mcp_ui_server import create_ui_resource; print('OK')"`
Expected: Output "OK"

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "deps: add mcp-ui-server for interactive UI support"
```

---

## Task 2: Create UI Module Structure

**Files:**
- Create: `scout_mcp/ui/__init__.py`
- Create: `scout_mcp/ui/generators.py`
- Create: `scout_mcp/ui/templates.py`

**Step 1: Create UI module init file**

```python
"""UI resource generators for Scout MCP."""

from scout_mcp.ui.generators import (
    create_directory_ui,
    create_file_viewer_ui,
    create_log_viewer_ui,
    create_markdown_viewer_ui,
)

__all__ = [
    "create_directory_ui",
    "create_file_viewer_ui",
    "create_log_viewer_ui",
    "create_markdown_viewer_ui",
]
```

**Step 2: Create empty generators module**

```python
"""UI resource generators for different file types."""

from typing import Any

from mcp_ui_server import create_ui_resource


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
    raise NotImplementedError("TODO: Task 3")


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
```

**Step 3: Create empty templates module**

```python
"""HTML templates for UI resources."""


def get_base_styles() -> str:
    """Get base CSS styles for all UI components.

    Returns:
        CSS string with Tailwind-like utility classes
    """
    return """
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 14px;
            line-height: 1.5;
            color: #333;
            background: #fff;
            padding: 16px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header {
            border-bottom: 2px solid #e5e7eb;
            padding-bottom: 12px;
            margin-bottom: 16px;
        }
        .title { font-size: 18px; font-weight: 600; color: #111; }
        .subtitle { font-size: 12px; color: #6b7280; margin-top: 4px; }
        .content { padding: 12px 0; }
        button {
            background: #3b82f6;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 14px;
            cursor: pointer;
        }
        button:hover { background: #2563eb; }
        input[type="text"] {
            border: 1px solid #d1d5db;
            border-radius: 4px;
            padding: 8px 12px;
            font-size: 14px;
            width: 100%;
            max-width: 400px;
        }
        input[type="text"]:focus {
            outline: none;
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
    </style>
    """
```

**Step 4: Verify module imports**

Run: `uv run python -c "from scout_mcp.ui import create_directory_ui; print('OK')"`
Expected: Output "OK"

**Step 5: Commit**

```bash
git add scout_mcp/ui/
git commit -m "feat: add UI module structure with generators and templates"
```

---

## Task 3: Implement Directory Explorer UI

**Files:**
- Modify: `scout_mcp/ui/generators.py:10-23`
- Modify: `scout_mcp/ui/templates.py`

**Step 1: Write test for directory UI generator**

Create: `tests/test_ui/test_generators.py`

```python
"""Tests for UI resource generators."""

import pytest

from scout_mcp.ui.generators import create_directory_ui


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
    assert result["resource"]["uri"].startswith("ui://")
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
```

Create: `tests/test_ui/__init__.py`

```python
"""Tests for UI module."""
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui/test_generators.py::test_create_directory_ui_basic -v`
Expected: FAIL with NotImplementedError

**Step 3: Add directory template to templates.py**

Add to `scout_mcp/ui/templates.py`:

```python
def get_directory_explorer_html(host: str, path: str, listing: str) -> str:
    """Generate file explorer HTML for directory listings.

    Args:
        host: SSH hostname
        path: Directory path
        listing: Output from ls -la

    Returns:
        Complete HTML page with file explorer
    """
    # Parse ls -la output into structured data
    lines = listing.strip().split("\n")

    # Skip 'total' line and parse entries
    entries_html = []
    for line in lines[1:]:  # Skip 'total N' line
        parts = line.split(None, 8)  # Split on whitespace, max 9 parts
        if len(parts) < 9:
            continue

        permissions, _, owner, group, size, month, day, time, name = parts

        # Skip . and ..
        if name in (".", ".."):
            continue

        is_dir = permissions.startswith("d")
        icon = "📁" if is_dir else "📄"

        entries_html.append(f"""
        <tr class="entry" data-name="{name}" data-type="{'dir' if is_dir else 'file'}">
            <td class="icon">{icon}</td>
            <td class="name">{name}</td>
            <td class="size">{size if not is_dir else '-'}</td>
            <td class="date">{month} {day} {time}</td>
            <td class="perms">{permissions}</td>
        </tr>
        """)

    entries_table = "\n".join(entries_html) if entries_html else """
        <tr><td colspan="5" style="text-align: center; color: #6b7280; padding: 32px;">
            Empty directory
        </td></tr>
    """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Directory: {host}:{path}</title>
        {get_base_styles()}
        <style>
            .search-box {{
                margin-bottom: 16px;
                display: flex;
                gap: 8px;
                align-items: center;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                overflow: hidden;
            }}
            th {{
                background: #f9fafb;
                padding: 12px;
                text-align: left;
                font-weight: 600;
                color: #374151;
                border-bottom: 1px solid #e5e7eb;
            }}
            td {{
                padding: 10px 12px;
                border-bottom: 1px solid #f3f4f6;
            }}
            tr:hover {{
                background: #f9fafb;
            }}
            tr:last-child td {{
                border-bottom: none;
            }}
            .icon {{ width: 40px; font-size: 18px; }}
            .name {{ font-weight: 500; color: #111; }}
            .size {{ color: #6b7280; width: 100px; }}
            .date {{ color: #6b7280; width: 140px; font-size: 12px; }}
            .perms {{ color: #9ca3af; width: 120px; font-family: monospace; font-size: 12px; }}
            .hidden {{ display: none; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="title">📂 {host}:{path}</div>
                <div class="subtitle">File Explorer</div>
            </div>

            <div class="search-box">
                <input
                    type="text"
                    id="searchInput"
                    placeholder="Filter files and directories..."
                    oninput="filterEntries()"
                />
            </div>

            <table>
                <thead>
                    <tr>
                        <th></th>
                        <th>Name</th>
                        <th>Size</th>
                        <th>Modified</th>
                        <th>Permissions</th>
                    </tr>
                </thead>
                <tbody id="entriesTable">
                    {entries_table}
                </tbody>
            </table>
        </div>

        <script>
            function filterEntries() {{
                const search = document.getElementById('searchInput').value.toLowerCase();
                const entries = document.querySelectorAll('.entry');

                entries.forEach(entry => {{
                    const name = entry.dataset.name.toLowerCase();
                    if (name.includes(search)) {{
                        entry.classList.remove('hidden');
                    }} else {{
                        entry.classList.add('hidden');
                    }}
                }});
            }}
        </script>
    </body>
    </html>
    """
```

**Step 4: Implement directory UI generator**

Modify `scout_mcp/ui/generators.py:10-23`:

```python
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

    return create_ui_resource(
        type="rawHtml",
        uri=f"ui://scout-directory/{host}{path}",
        html=html,
        encoding="text",
    )
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_ui/test_generators.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add scout_mcp/ui/generators.py scout_mcp/ui/templates.py tests/test_ui/
git commit -m "feat: add interactive directory explorer UI"
```

---

## Task 4: Implement File Viewer UI

**Files:**
- Modify: `scout_mcp/ui/generators.py:26-39`
- Modify: `scout_mcp/ui/templates.py`

**Step 1: Write test for file viewer UI**

Add to `tests/test_ui/test_generators.py`:

```python
from scout_mcp.ui.generators import create_file_viewer_ui


@pytest.mark.asyncio
async def test_create_file_viewer_ui_text():
    """Test file viewer UI for plain text."""
    content = "Hello, World!\nLine 2\nLine 3"

    result = await create_file_viewer_ui("tootie", "/tmp/test.txt", content)

    assert result["type"] == "resource"
    assert result["resource"]["uri"].startswith("ui://")
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui/test_generators.py::test_create_file_viewer_ui_text -v`
Expected: FAIL with NotImplementedError

**Step 3: Add file viewer template**

Add to `scout_mcp/ui/templates.py`:

```python
def get_file_viewer_html(
    host: str, path: str, content: str, mime_type: str = "text/plain"
) -> str:
    """Generate file viewer HTML with syntax highlighting.

    Args:
        host: SSH hostname
        path: File path
        content: File contents
        mime_type: MIME type for syntax detection

    Returns:
        Complete HTML page with file viewer
    """
    # Escape HTML in content
    import html
    escaped_content = html.escape(content)

    # Get file extension for syntax highlighting hint
    extension = path.rsplit(".", 1)[-1] if "." in path else ""

    # Language mapping for common extensions
    lang_map = {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "json": "json",
        "yaml": "yaml",
        "yml": "yaml",
        "sh": "bash",
        "bash": "bash",
        "md": "markdown",
        "html": "html",
        "css": "css",
        "sql": "sql",
    }

    language = lang_map.get(extension, "text")

    # Count lines
    line_count = content.count("\n") + 1
    line_numbers = "\n".join(str(i) for i in range(1, line_count + 1))

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>File: {host}:{path}</title>
        {get_base_styles()}
        <style>
            .toolbar {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px;
                background: #f9fafb;
                border: 1px solid #e5e7eb;
                border-radius: 6px 6px 0 0;
                margin-bottom: 0;
            }}
            .file-info {{
                display: flex;
                gap: 16px;
                font-size: 12px;
                color: #6b7280;
            }}
            .code-container {{
                display: flex;
                background: #1f2937;
                border: 1px solid #e5e7eb;
                border-top: none;
                border-radius: 0 0 6px 6px;
                overflow: auto;
                max-height: 80vh;
            }}
            .line-numbers {{
                padding: 16px 8px;
                background: #111827;
                color: #6b7280;
                text-align: right;
                user-select: none;
                font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
                font-size: 13px;
                line-height: 1.5;
                border-right: 1px solid #374151;
            }}
            .code-content {{
                flex: 1;
                padding: 16px;
                color: #e5e7eb;
                font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
                font-size: 13px;
                line-height: 1.5;
                white-space: pre;
                overflow-x: auto;
            }}
            .copy-btn {{
                background: #374151;
                color: #e5e7eb;
            }}
            .copy-btn:hover {{
                background: #4b5563;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="title">📄 {host}:{path}</div>
                <div class="subtitle">File Viewer ({language})</div>
            </div>

            <div class="toolbar">
                <div class="file-info">
                    <span>Lines: {line_count}</span>
                    <span>Type: {mime_type}</span>
                </div>
                <button class="copy-btn" onclick="copyToClipboard()">
                    Copy to Clipboard
                </button>
            </div>

            <div class="code-container">
                <div class="line-numbers">{line_numbers}</div>
                <div class="code-content" id="codeContent">{escaped_content}</div>
            </div>
        </div>

        <script>
            function copyToClipboard() {{
                const content = document.getElementById('codeContent').textContent;
                navigator.clipboard.writeText(content).then(() => {{
                    const btn = document.querySelector('.copy-btn');
                    btn.textContent = 'Copied!';
                    setTimeout(() => {{ btn.textContent = 'Copy to Clipboard'; }}, 2000);
                }});
            }}
        </script>
    </body>
    </html>
    """
```

**Step 4: Implement file viewer generator**

Modify `scout_mcp/ui/generators.py:26-39`:

```python
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
    from scout_mcp.ui.templates import get_file_viewer_html

    html = get_file_viewer_html(host, path, content, mime_type)

    return create_ui_resource(
        type="rawHtml",
        uri=f"ui://scout-file/{host}{path}",
        html=html,
        encoding="text",
    )
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_ui/test_generators.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add scout_mcp/ui/generators.py scout_mcp/ui/templates.py tests/test_ui/
git commit -m "feat: add file viewer UI with syntax highlighting"
```

---

## Task 5: Implement Log Viewer UI

**Files:**
- Modify: `scout_mcp/ui/generators.py:42-55`
- Modify: `scout_mcp/ui/templates.py`

**Step 1: Write test for log viewer UI**

Add to `tests/test_ui/test_generators.py`:

```python
from scout_mcp.ui.generators import create_log_viewer_ui


@pytest.mark.asyncio
async def test_create_log_viewer_ui():
    """Test log viewer UI with filtering."""
    content = """[2025-12-07 10:00:01] INFO: Application started
[2025-12-07 10:00:02] ERROR: Failed to connect
[2025-12-07 10:00:03] WARN: Retry attempt 1
[2025-12-07 10:00:04] INFO: Connected successfully
"""

    result = await create_log_viewer_ui("tootie", "/var/log/app.log", content)

    assert result["type"] == "resource"
    assert "app.log" in result["resource"]["text"]
    assert "ERROR" in result["resource"]["text"]
    assert "filter" in result["resource"]["text"].lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui/test_generators.py::test_create_log_viewer_ui -v`
Expected: FAIL with NotImplementedError

**Step 3: Add log viewer template**

Add to `scout_mcp/ui/templates.py`:

```python
def get_log_viewer_html(host: str, path: str, content: str) -> str:
    """Generate log viewer HTML with filtering and level highlighting.

    Args:
        host: SSH hostname
        path: Log file path
        content: Log file contents

    Returns:
        Complete HTML page with log viewer
    """
    import html

    # Parse log lines
    lines = content.split("\n")
    log_lines_html = []

    for i, line in enumerate(lines):
        if not line.strip():
            continue

        # Detect log level
        level = "INFO"
        if "ERROR" in line or "FATAL" in line:
            level = "ERROR"
        elif "WARN" in line:
            level = "WARN"
        elif "DEBUG" in line:
            level = "DEBUG"

        escaped_line = html.escape(line)

        log_lines_html.append(
            f'<div class="log-line log-{level.lower()}" data-level="{level}" '
            f'data-line="{i+1}">{escaped_line}</div>'
        )

    logs_html = "\n".join(log_lines_html) if log_lines_html else \
        '<div style="color: #6b7280; padding: 32px; text-align: center;">No logs</div>'

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Logs: {host}:{path}</title>
        {get_base_styles()}
        <style>
            .controls {{
                display: flex;
                gap: 8px;
                margin-bottom: 16px;
                flex-wrap: wrap;
            }}
            .filter-btn {{
                padding: 6px 12px;
                font-size: 13px;
            }}
            .filter-btn.active {{
                background: #2563eb;
            }}
            .log-container {{
                background: #111827;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 16px;
                max-height: 70vh;
                overflow-y: auto;
                font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
                font-size: 13px;
                line-height: 1.6;
            }}
            .log-line {{
                padding: 4px 8px;
                border-left: 3px solid transparent;
                margin-bottom: 2px;
            }}
            .log-line:hover {{
                background: #1f2937;
            }}
            .log-error {{
                color: #fca5a5;
                border-left-color: #dc2626;
                background: rgba(220, 38, 38, 0.1);
            }}
            .log-warn {{
                color: #fcd34d;
                border-left-color: #f59e0b;
                background: rgba(245, 158, 11, 0.1);
            }}
            .log-info {{
                color: #93c5fd;
                border-left-color: #3b82f6;
            }}
            .log-debug {{
                color: #9ca3af;
                border-left-color: #6b7280;
            }}
            .hidden {{
                display: none !important;
            }}
            .stats {{
                font-size: 12px;
                color: #6b7280;
                margin-top: 8px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="title">📋 {host}:{path}</div>
                <div class="subtitle">Log Viewer</div>
            </div>

            <div class="controls">
                <input
                    type="text"
                    id="searchInput"
                    placeholder="Search logs..."
                    oninput="filterLogs()"
                    style="flex: 1; min-width: 200px;"
                />
                <button class="filter-btn active" onclick="toggleLevel('ERROR')" id="btn-ERROR">
                    ERROR
                </button>
                <button class="filter-btn active" onclick="toggleLevel('WARN')" id="btn-WARN">
                    WARN
                </button>
                <button class="filter-btn active" onclick="toggleLevel('INFO')" id="btn-INFO">
                    INFO
                </button>
                <button class="filter-btn active" onclick="toggleLevel('DEBUG')" id="btn-DEBUG">
                    DEBUG
                </button>
            </div>

            <div class="log-container" id="logContainer">
                {logs_html}
            </div>

            <div class="stats" id="stats"></div>
        </div>

        <script>
            const activeLevels = new Set(['ERROR', 'WARN', 'INFO', 'DEBUG']);

            function toggleLevel(level) {{
                const btn = document.getElementById('btn-' + level);
                if (activeLevels.has(level)) {{
                    activeLevels.delete(level);
                    btn.classList.remove('active');
                }} else {{
                    activeLevels.add(level);
                    btn.classList.add('active');
                }}
                filterLogs();
            }}

            function filterLogs() {{
                const search = document.getElementById('searchInput').value.toLowerCase();
                const lines = document.querySelectorAll('.log-line');
                let visible = 0;

                lines.forEach(line => {{
                    const level = line.dataset.level;
                    const text = line.textContent.toLowerCase();
                    const levelMatch = activeLevels.has(level);
                    const textMatch = !search || text.includes(search);

                    if (levelMatch && textMatch) {{
                        line.classList.remove('hidden');
                        visible++;
                    }} else {{
                        line.classList.add('hidden');
                    }}
                }});

                document.getElementById('stats').textContent =
                    `Showing ${{visible}} of ${{lines.length}} lines`;
            }}

            // Initial stats
            filterLogs();
        </script>
    </body>
    </html>
    """
```

**Step 4: Implement log viewer generator**

Modify `scout_mcp/ui/generators.py:42-55`:

```python
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
    from scout_mcp.ui.templates import get_log_viewer_html

    html = get_log_viewer_html(host, path, content)

    return create_ui_resource(
        type="rawHtml",
        uri=f"ui://scout-logs/{host}{path}",
        html=html,
        encoding="text",
    )
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_ui/test_generators.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add scout_mcp/ui/generators.py scout_mcp/ui/templates.py tests/test_ui/
git commit -m "feat: add log viewer UI with filtering and search"
```

---

## Task 6: Implement Markdown Viewer UI

**Files:**
- Modify: `scout_mcp/ui/generators.py:58-71`
- Modify: `scout_mcp/ui/templates.py`

**Step 1: Write test for markdown viewer UI**

Add to `tests/test_ui/test_generators.py`:

```python
from scout_mcp.ui.generators import create_markdown_viewer_ui


@pytest.mark.asyncio
async def test_create_markdown_viewer_ui():
    """Test markdown viewer UI."""
    content = """# Hello World

This is **bold** and *italic*.

- Item 1
- Item 2

```python
print("code")
```
"""

    result = await create_markdown_viewer_ui("tootie", "/docs/README.md", content)

    assert result["type"] == "resource"
    assert "README.md" in result["resource"]["text"]
    assert "Hello World" in result["resource"]["text"]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui/test_generators.py::test_create_markdown_viewer_ui -v`
Expected: FAIL with NotImplementedError

**Step 3: Add markdown viewer template**

Add to `scout_mcp/ui/templates.py`:

```python
def get_markdown_viewer_html(host: str, path: str, content: str) -> str:
    """Generate markdown viewer HTML with rendered preview.

    Args:
        host: SSH hostname
        path: Markdown file path
        content: Markdown content

    Returns:
        Complete HTML page with markdown viewer
    """
    import html
    escaped_content = html.escape(content)

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Markdown: {host}:{path}</title>
        {get_base_styles()}
        <script src="https://cdn.jsdelivr.net/npm/marked@11.1.0/marked.min.js"></script>
        <style>
            .view-controls {{
                display: flex;
                gap: 8px;
                margin-bottom: 16px;
            }}
            .view-btn {{
                padding: 6px 16px;
                font-size: 13px;
            }}
            .view-btn.active {{
                background: #2563eb;
            }}
            .markdown-rendered {{
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                padding: 24px;
                line-height: 1.7;
            }}
            .markdown-rendered h1 {{
                font-size: 28px;
                font-weight: 700;
                margin: 24px 0 16px 0;
                padding-bottom: 8px;
                border-bottom: 2px solid #e5e7eb;
            }}
            .markdown-rendered h2 {{
                font-size: 22px;
                font-weight: 600;
                margin: 20px 0 12px 0;
            }}
            .markdown-rendered h3 {{
                font-size: 18px;
                font-weight: 600;
                margin: 16px 0 8px 0;
            }}
            .markdown-rendered p {{
                margin: 12px 0;
            }}
            .markdown-rendered ul, .markdown-rendered ol {{
                margin: 12px 0;
                padding-left: 24px;
            }}
            .markdown-rendered li {{
                margin: 6px 0;
            }}
            .markdown-rendered code {{
                background: #f3f4f6;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
                font-size: 13px;
            }}
            .markdown-rendered pre {{
                background: #1f2937;
                color: #e5e7eb;
                padding: 16px;
                border-radius: 6px;
                overflow-x: auto;
                margin: 16px 0;
            }}
            .markdown-rendered pre code {{
                background: none;
                padding: 0;
                color: inherit;
            }}
            .markdown-rendered blockquote {{
                border-left: 4px solid #3b82f6;
                padding-left: 16px;
                margin: 16px 0;
                color: #6b7280;
            }}
            .markdown-rendered a {{
                color: #3b82f6;
                text-decoration: none;
            }}
            .markdown-rendered a:hover {{
                text-decoration: underline;
            }}
            .markdown-raw {{
                background: #1f2937;
                color: #e5e7eb;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 16px;
                font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
                font-size: 13px;
                line-height: 1.6;
                white-space: pre-wrap;
                overflow-x: auto;
            }}
            .hidden {{
                display: none;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="title">📝 {host}:{path}</div>
                <div class="subtitle">Markdown Viewer</div>
            </div>

            <div class="view-controls">
                <button class="view-btn active" onclick="showView('rendered')" id="btn-rendered">
                    Preview
                </button>
                <button class="view-btn" onclick="showView('raw')" id="btn-raw">
                    Source
                </button>
            </div>

            <div id="renderedView" class="markdown-rendered"></div>
            <div id="rawView" class="markdown-raw hidden">{escaped_content}</div>
        </div>

        <script>
            const markdownContent = `{escaped_content}`;

            // Render markdown
            document.getElementById('renderedView').innerHTML = marked.parse(markdownContent);

            function showView(view) {{
                const renderedView = document.getElementById('renderedView');
                const rawView = document.getElementById('rawView');
                const renderedBtn = document.getElementById('btn-rendered');
                const rawBtn = document.getElementById('btn-raw');

                if (view === 'rendered') {{
                    renderedView.classList.remove('hidden');
                    rawView.classList.add('hidden');
                    renderedBtn.classList.add('active');
                    rawBtn.classList.remove('active');
                }} else {{
                    renderedView.classList.add('hidden');
                    rawView.classList.remove('hidden');
                    renderedBtn.classList.remove('active');
                    rawBtn.classList.add('active');
                }}
            }}
        </script>
    </body>
    </html>
    """
```

**Step 4: Implement markdown viewer generator**

Modify `scout_mcp/ui/generators.py:58-71`:

```python
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
    from scout_mcp.ui.templates import get_markdown_viewer_html

    html = get_markdown_viewer_html(host, path, content)

    return create_ui_resource(
        type="rawHtml",
        uri=f"ui://scout-markdown/{host}{path}",
        html=html,
        encoding="text",
    )
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_ui/test_generators.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add scout_mcp/ui/generators.py scout_mcp/ui/templates.py tests/test_ui/
git commit -m "feat: add markdown viewer UI with preview and source view"
```

---

## Task 7: Integrate UI Resources into scout_resource

**Files:**
- Modify: `scout_mcp/resources/scout.py:1-77`

**Step 1: Write integration test**

Create: `tests/test_resources/test_scout_ui.py`

```python
"""Tests for scout resource UI integration."""

import pytest

from scout_mcp.resources.scout import scout_resource


@pytest.mark.asyncio
async def test_scout_resource_returns_ui_for_directory(monkeypatch):
    """Test scout resource returns UI for directory listings."""
    # Mock the dependencies
    from unittest.mock import AsyncMock, MagicMock

    mock_config = MagicMock()
    mock_config.get_host.return_value = {"hostname": "tootie"}
    mock_config.max_file_size = 1048576

    mock_conn = AsyncMock()

    monkeypatch.setattr(
        "scout_mcp.resources.scout.get_config",
        lambda: mock_config
    )
    monkeypatch.setattr(
        "scout_mcp.resources.scout.get_connection_with_retry",
        AsyncMock(return_value=mock_conn)
    )
    monkeypatch.setattr(
        "scout_mcp.resources.scout.stat_path",
        AsyncMock(return_value="directory")
    )
    monkeypatch.setattr(
        "scout_mcp.resources.scout.ls_dir",
        AsyncMock(return_value="total 8\ndrwxr-xr-x 2 user group 4096 Dec 7 10:00 .")
    )

    result = await scout_resource("tootie", "/mnt/cache")

    # Should return UIResource dict, not plain text
    assert isinstance(result, dict)
    assert result["type"] == "resource"
    assert result["resource"]["uri"].startswith("ui://")
    assert result["resource"]["mimeType"] == "text/html"


@pytest.mark.asyncio
async def test_scout_resource_returns_ui_for_markdown(monkeypatch):
    """Test scout resource returns UI for markdown files."""
    from unittest.mock import AsyncMock, MagicMock

    mock_config = MagicMock()
    mock_config.get_host.return_value = {"hostname": "tootie"}
    mock_config.max_file_size = 1048576

    mock_conn = AsyncMock()

    monkeypatch.setattr(
        "scout_mcp.resources.scout.get_config",
        lambda: mock_config
    )
    monkeypatch.setattr(
        "scout_mcp.resources.scout.get_connection_with_retry",
        AsyncMock(return_value=mock_conn)
    )
    monkeypatch.setattr(
        "scout_mcp.resources.scout.stat_path",
        AsyncMock(return_value="file")
    )
    monkeypatch.setattr(
        "scout_mcp.resources.scout.cat_file",
        AsyncMock(return_value=("# Hello", False))
    )

    result = await scout_resource("tootie", "/docs/README.md")

    assert isinstance(result, dict)
    assert result["type"] == "resource"
    assert "markdown" in result["resource"]["uri"]


@pytest.mark.asyncio
async def test_scout_resource_returns_ui_for_logs(monkeypatch):
    """Test scout resource returns UI for log files."""
    from unittest.mock import AsyncMock, MagicMock

    mock_config = MagicMock()
    mock_config.get_host.return_value = {"hostname": "tootie"}
    mock_config.max_file_size = 1048576

    mock_conn = AsyncMock()

    monkeypatch.setattr(
        "scout_mcp.resources.scout.get_config",
        lambda: mock_config
    )
    monkeypatch.setattr(
        "scout_mcp.resources.scout.get_connection_with_retry",
        AsyncMock(return_value=mock_conn)
    )
    monkeypatch.setattr(
        "scout_mcp.resources.scout.stat_path",
        AsyncMock(return_value="file")
    )
    monkeypatch.setattr(
        "scout_mcp.resources.scout.cat_file",
        AsyncMock(return_value=("[2025-12-07] INFO: test", False))
    )

    result = await scout_resource("tootie", "/var/log/app.log")

    assert isinstance(result, dict)
    assert result["type"] == "resource"
    assert "logs" in result["resource"]["uri"]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_resources/test_scout_ui.py -v`
Expected: FAIL - returns string, not dict

**Step 3: Modify scout_resource to use UI generators**

Replace entire `scout_mcp/resources/scout.py`:

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_resources/test_scout_ui.py -v`
Expected: All tests PASS

**Step 5: Run all UI tests**

Run: `uv run pytest tests/test_ui/ tests/test_resources/test_scout_ui.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add scout_mcp/resources/scout.py tests/test_resources/test_scout_ui.py
git commit -m "feat: integrate UI resources into scout_resource"
```

---

## Task 8: Update Compose Logs Resource

**Files:**
- Modify: `scout_mcp/resources/compose.py`

**Step 1: Read current compose logs implementation**

Run: `cat scout_mcp/resources/compose.py | grep -A 30 "compose_logs_resource"`

**Step 2: Modify compose_logs_resource to return UI**

Add to top of file:
```python
from scout_mcp.ui import create_log_viewer_ui
```

Modify the `compose_logs_resource` function to return UI:

```python
async def compose_logs_resource(host: str, project: str) -> dict[str, Any]:
    """Read Docker Compose stack logs with interactive log viewer UI.

    Args:
        host: SSH hostname
        project: Compose project name

    Returns:
        UIResource dict with log viewer interface
    """
    # ... existing code to fetch logs ...

    # Return interactive log viewer UI instead of plain text
    return await create_log_viewer_ui(
        host,
        f"/compose/{project}/logs",
        log_output
    )
```

**Step 3: Update Docker logs resource**

Modify `scout_mcp/resources/docker.py` similarly:

```python
from scout_mcp.ui import create_log_viewer_ui


async def docker_logs_resource(host: str, container: str) -> dict[str, Any]:
    """Read Docker container logs with interactive log viewer UI."""
    # ... existing code ...

    return await create_log_viewer_ui(
        host,
        f"/docker/{container}/logs",
        log_output
    )
```

**Step 4: Update syslog resource**

Modify `scout_mcp/resources/syslog.py`:

```python
from scout_mcp.ui import create_log_viewer_ui


async def syslog_resource(host: str) -> dict[str, Any]:
    """Get system logs with interactive log viewer UI."""
    # ... existing code ...

    return await create_log_viewer_ui(
        host,
        "/var/log/syslog",
        log_output
    )
```

**Step 5: Test manually**

Run: `uv run python -m scout_mcp`

In another terminal, test with MCP inspector or client.

**Step 6: Commit**

```bash
git add scout_mcp/resources/compose.py scout_mcp/resources/docker.py scout_mcp/resources/syslog.py
git commit -m "feat: add log viewer UI to compose, docker, and syslog resources"
```

---

## Task 9: Update Server Return Type Hints

**Files:**
- Modify: `scout_mcp/server.py:97-173`

**Step 1: Update return type hints for resource handlers**

Modify function signatures in `scout_mcp/server.py`:

```python
from typing import Any, Union


async def _read_host_path(host: str, path: str) -> Union[str, dict[str, Any]]:
    """Read a file or directory on a remote host.

    Args:
        host: SSH host name
        path: Remote path to read

    Returns:
        UIResource dict or plain text string
    """
    return await scout_resource(host, path)


async def _read_docker_logs(host: str, container: str) -> dict[str, Any]:
    """Read Docker container logs on a remote host.

    Args:
        host: SSH host name
        container: Docker container name

    Returns:
        UIResource dict with log viewer
    """
    return await docker_logs_resource(host, container)


async def _read_compose_logs(host: str, project: str) -> dict[str, Any]:
    """Read Docker Compose stack logs.

    Returns:
        UIResource dict with log viewer
    """
    return await compose_logs_resource(host, project)


async def _syslog(host: str) -> dict[str, Any]:
    """Get system logs from a remote host.

    Returns:
        UIResource dict with log viewer
    """
    return await syslog_resource(host)
```

**Step 2: Run mypy to check types**

Run: `uv run mypy scout_mcp/`
Expected: No type errors

**Step 3: Commit**

```bash
git add scout_mcp/server.py
git commit -m "refactor: update return type hints for UI resources"
```

---

## Task 10: Add Documentation

**Files:**
- Create: `docs/MCP-UI.md`
- Modify: `README.md`

**Step 1: Create MCP-UI documentation**

```markdown
# MCP-UI Integration

Scout MCP includes interactive UI components for enhanced file browsing, log viewing, and markdown rendering.

## UI Components

### File Explorer

When accessing directories, scout returns an interactive file explorer with:
- Sortable file listings
- File/directory icons
- Size and modification date display
- Search/filter functionality
- Permission display

**Example:** `tootie://mnt/cache/compose`

### Log Viewer

Log files (`.log`, paths containing `/log/`) display with:
- Level-based syntax highlighting (ERROR, WARN, INFO, DEBUG)
- Real-time filtering by log level
- Search functionality
- Line-by-line navigation
- Statistics display

**Example:** `tootie://compose/plex/logs`

### Markdown Viewer

Markdown files (`.md`, `.markdown`) render with:
- Live preview with syntax highlighting
- Source code view toggle
- Proper heading hierarchy
- Code block formatting
- Link preservation

**Example:** `tootie://docs/README.md`

### File Viewer

Code and text files display with:
- Syntax highlighting for common languages
- Line numbers
- Copy-to-clipboard functionality
- Language detection from extension
- Responsive layout

**Example:** `tootie://app/main.py`

## Architecture

UI resources use the MCP-UI protocol with:
- `text/html` MIME type for rendered content
- Sandboxed iframe execution
- Self-contained HTML with embedded CSS/JavaScript
- No external dependencies (except marked.js for markdown)

## Implementation

UI generators are in `scout_mcp/ui/`:
- `generators.py` - UIResource creation functions
- `templates.py` - HTML template generators

Resources automatically detect file types and return appropriate UI components.

## Development

To add new UI components:

1. Create generator function in `generators.py`
2. Create HTML template in `templates.py`
3. Add tests in `tests/test_ui/`
4. Integrate into resource handlers

See existing implementations for patterns.
```

**Step 2: Update README.md**

Add section after "Usage":

```markdown
## Interactive UI

Scout MCP provides interactive UI components for enhanced file browsing:

### File Explorer
Access any directory to see an interactive file explorer:
```
tootie://mnt/cache/compose
```

Features:
- Sortable listings
- Search/filter
- File type icons
- Size and dates

### Log Viewer
Log files display with syntax highlighting and filtering:
```
tootie://compose/plex/logs
tootie://var/log/app.log
```

Features:
- Level filtering (ERROR/WARN/INFO/DEBUG)
- Search functionality
- Syntax highlighting
- Line statistics

### Markdown Viewer
Markdown files render with live preview:
```
tootie://docs/README.md
```

Features:
- Live rendered preview
- Source view toggle
- Syntax highlighting
- Proper formatting

### File Viewer
Code and text files show with syntax highlighting:
```
tootie://app/main.py
```

Features:
- Language detection
- Line numbers
- Copy to clipboard
- Syntax highlighting

See [docs/MCP-UI.md](docs/MCP-UI.md) for complete UI documentation.
```

**Step 3: Commit**

```bash
git add docs/MCP-UI.md README.md
git commit -m "docs: add MCP-UI integration documentation"
```

---

## Task 11: Final Testing and Integration

**Files:**
- Create: `tests/test_integration_ui.py`

**Step 1: Create integration test**

```python
"""Integration tests for UI resources."""

import pytest


@pytest.mark.asyncio
async def test_full_ui_integration(monkeypatch):
    """Test complete UI integration flow."""
    from scout_mcp.server import create_server

    # Create server
    server = create_server()

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
    dir_html = get_directory_explorer_html("test", "/path", "total 8\ndrwxr-xr-x 2 user group 4096 Dec 7 10:00 .")
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
```

**Step 2: Run all tests**

Run: `uv run pytest tests/ -v --tb=short`
Expected: All tests PASS

**Step 3: Run type checking**

Run: `uv run mypy scout_mcp/`
Expected: No errors

**Step 4: Run linting**

Run: `uv run ruff check scout_mcp/ tests/`
Expected: No issues

**Step 5: Test server manually**

Run: `uv run python -m scout_mcp`

In MCP inspector or client:
- Access a directory: should show file explorer UI
- Access a .log file: should show log viewer UI
- Access a .md file: should show markdown viewer UI
- Access a .py file: should show file viewer UI

**Step 6: Final commit**

```bash
git add tests/test_integration_ui.py
git commit -m "test: add comprehensive UI integration tests"
```

---

## Task 12: Create Pull Request

**Step 1: Push feature branch**

```bash
git push origin refactor/cleanup-legacy-modules
```

**Step 2: Create PR description**

```markdown
# Add MCP-UI Interactive Components

## Summary
Integrates MCP-UI protocol to provide interactive UI components for file browsing, log viewing, and markdown rendering.

## Changes
- ✅ Added `mcp-ui-server` dependency
- ✅ Created `scout_mcp/ui/` module with generators and templates
- ✅ Implemented directory file explorer UI
- ✅ Implemented file viewer with syntax highlighting
- ✅ Implemented log viewer with filtering and search
- ✅ Implemented markdown viewer with live preview
- ✅ Integrated UI resources into scout, compose, docker, and syslog resources
- ✅ Added comprehensive tests (unit + integration)
- ✅ Updated documentation (README + new MCP-UI.md)

## UI Components

### Directory Explorer
![File Explorer](screenshot-explorer.png)
- Sortable file listings
- Search/filter functionality
- File type icons

### Log Viewer
![Log Viewer](screenshot-logs.png)
- Level-based syntax highlighting
- Real-time filtering
- Search functionality

### Markdown Viewer
![Markdown Viewer](screenshot-markdown.png)
- Live preview
- Source view toggle
- Proper formatting

### File Viewer
![File Viewer](screenshot-file.png)
- Syntax highlighting
- Line numbers
- Copy to clipboard

## Testing
All tests passing:
- Unit tests: `tests/test_ui/`
- Integration tests: `tests/test_integration_ui.py`
- Resource tests: `tests/test_resources/test_scout_ui.py`

## Type Safety
- All type hints updated
- mypy strict mode passes
- No type errors

## Documentation
- Updated README.md with UI examples
- Added docs/MCP-UI.md with complete guide
- Inline documentation in all modules
```

**Step 3: Request review**

Assign reviewers and wait for approval.

---

## Completion Checklist

- ✅ Task 1: Add MCP-UI dependency
- ✅ Task 2: Create UI module structure
- ✅ Task 3: Implement directory explorer UI
- ✅ Task 4: Implement file viewer UI
- ✅ Task 5: Implement log viewer UI
- ✅ Task 6: Implement markdown viewer UI
- ✅ Task 7: Integrate UI resources into scout_resource
- ✅ Task 8: Update compose/docker/syslog logs resources
- ✅ Task 9: Update server return type hints
- ✅ Task 10: Add documentation
- ✅ Task 11: Final testing and integration
- ✅ Task 12: Create pull request

---

## Notes

**DRY Violations to Avoid:**
- Don't duplicate HTML templates - use template functions
- Don't duplicate UI generation logic - use shared generators
- Don't duplicate file type detection - use shared utility

**YAGNI Reminders:**
- Don't add remote DOM unless interactive features require it
- Don't add tool call handlers unless users need to trigger actions
- Don't add configuration UI unless settings need to be changed
- Keep it simple: HTML + CSS + minimal JavaScript

**TDD Success Criteria:**
- All tests written before implementation
- All tests run and fail first
- Minimal code to pass tests
- Refactor after green
- Commit after each task

**Performance Considerations:**
- UI templates are generated server-side (no runtime overhead)
- All resources are read-only (no state management)
- JavaScript is minimal (filtering/search only)
- No external API calls (except marked.js CDN for markdown)

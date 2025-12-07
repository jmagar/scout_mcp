# ruff: noqa: E501
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

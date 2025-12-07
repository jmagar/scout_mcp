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

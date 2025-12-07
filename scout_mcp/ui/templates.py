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

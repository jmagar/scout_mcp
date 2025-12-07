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

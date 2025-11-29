"""MIME type detection utilities."""


def get_mime_type(path: str) -> str:
    """Infer MIME type from file extension.

    Args:
        path: File path to analyze.

    Returns:
        MIME type string, defaults to 'text/plain'.
    """
    ext_map = {
        # Config files
        ".conf": "text/plain",
        ".cfg": "text/plain",
        ".ini": "text/plain",
        ".yaml": "text/yaml",
        ".yml": "text/yaml",
        ".toml": "text/plain",
        ".json": "application/json",
        ".xml": "application/xml",
        # Scripts
        ".sh": "text/x-shellscript",
        ".bash": "text/x-shellscript",
        ".zsh": "text/x-shellscript",
        ".py": "text/x-python",
        ".js": "text/javascript",
        ".ts": "text/typescript",
        ".rb": "text/x-ruby",
        ".go": "text/x-go",
        ".rs": "text/x-rust",
        # Web
        ".html": "text/html",
        ".htm": "text/html",
        ".css": "text/css",
        # Docs
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".log": "text/plain",
        ".csv": "text/csv",
    }
    path_lower = path.lower()
    for ext, mime in ext_map.items():
        if path_lower.endswith(ext):
            return mime
    return "text/plain"

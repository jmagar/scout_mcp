# MCP-UI Integration

Scout MCP includes optional interactive UI components for enhanced file browsing, log viewing, and markdown rendering.

## Configuration

**By default, MCP-UI is disabled** for better compatibility with MCP clients that don't support the MCP-UI protocol.

To enable interactive HTML UIs, set the environment variable:

```bash
SCOUT_ENABLE_UI=true uv run python -m scout_mcp
```

**With UI disabled (default):**
- Files return raw text content
- Directories return `ls -la` output
- Compatible with all MCP clients

**With UI enabled:**
- Files display in an interactive viewer with line numbers and syntax highlighting
- Directories show a clickable file explorer with breadcrumb navigation
- Log files get level-based highlighting and filtering
- Markdown files render with live preview

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

# MCP-Cat

MCP server for remote file operations via SSH.

## Installation

```bash
uv sync
```

## Usage

```bash
uv run python -m mcp_cat
```

## Tool: scout

- `scout("hosts")` - List available SSH hosts
- `scout("hostname:/path/to/file")` - Cat a file
- `scout("hostname:/path/to/dir")` - List directory contents
- `scout("hostname:/path", "rg 'pattern'")` - Execute command

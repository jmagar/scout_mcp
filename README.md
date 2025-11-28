# MCP-Cat

MCP server for remote file operations via SSH. Scout your fleet of machines with a single tool.

## Installation

```bash
# Clone and install
git clone <repo-url>
cd mcp-cat
uv sync
```

## Configuration

MCP-Cat reads your `~/.ssh/config` to discover available hosts. Optionally configure limits:

```bash
# Environment variables (not currently implemented - uses defaults)
export MCP_CAT_MAX_FILE_SIZE=5242880  # 5MB (default: 1MB)
export MCP_CAT_COMMAND_TIMEOUT=60      # seconds (default: 30)
export MCP_CAT_IDLE_TIMEOUT=120        # seconds (default: 60)
```

**Current defaults:**
- Max file size: 1MB (1,048,576 bytes)
- Command timeout: 30 seconds
- Idle timeout: 60 seconds

## Usage

Add to your Claude Code MCP config:

```json
{
  "mcpServers": {
    "mcp-cat": {
      "command": "uv",
      "args": ["run", "--directory", "/code/mcp-cat", "python", "-m", "mcp_cat"]
    }
  }
}
```

## Tool: scout

### List available hosts

```
scout("hosts")
```

### Cat a file

```
scout("hostname:/path/to/file.log")
```

### List a directory

```
scout("hostname:/path/to/directory")
```

### Run a command

```
scout("hostname:/working/dir", "rg 'pattern' -t py")
scout("hostname:~/code", "find . -name '*.md' -mtime -1")
scout("hostname:/var/log", "tail -100 app.log | grep ERROR")
```

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Lint and type check
uv run ruff check scout_mcp/ tests/
uv run mypy scout_mcp/

# Run server locally
uv run python -m mcp_cat
```

## License

MIT

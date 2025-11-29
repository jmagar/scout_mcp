# Scout MCP

MCP server for remote file operations via SSH. Scout your fleet of machines with a single tool.

## Installation

```bash
# Clone and install
git clone <repo-url>
cd scout_mcp
uv sync
```

## Configuration

Scout MCP reads your `~/.ssh/config` to discover available hosts. Optionally configure limits:

```bash
# Environment variables (optional)
export SCOUT_MAX_FILE_SIZE=5242880   # 5MB (default: 1MB)
export SCOUT_COMMAND_TIMEOUT=60      # seconds (default: 30)
export SCOUT_IDLE_TIMEOUT=120        # seconds (default: 60)

# Legacy MCP_CAT_* prefix still supported for backward compatibility
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
    "scout_mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/code/scout_mcp", "python", "-m", "scout_mcp"]
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
uv run python -m scout_mcp
```

## License

MIT

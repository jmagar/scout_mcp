# Scout MCP

MCP server for remote file operations via SSH. Scout your fleet of machines with a single tool.

## Installation

```bash
# Clone and install
git clone https://github.com/jmagar/scout_mcp
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
export SCOUT_MAX_POOL_SIZE=200       # max connections (default: 100)

# Legacy MCP_CAT_* prefix still supported for backward compatibility
```

**Current defaults:**
- Max file size: 1MB (1,048,576 bytes)
- Command timeout: 30 seconds
- Idle timeout: 60 seconds
- Max pool size: 100 connections

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

## File Transfers

Scout includes `beam` - a simple file transfer feature using SFTP:

```python
# Upload: local file exists → transfer to remote
mcp__scout__scout(
    target="shart:/mnt/cache/docs/report.pdf",
    beam="/tmp/local-report.pdf"
)

# Download: local file doesn't exist → download from remote
mcp__scout__scout(
    target="squirts:/var/log/app.log",
    beam="/tmp/app.log"
)
```

Direction is auto-detected:
- Local file exists → Upload (local → remote)
- Local file doesn't exist → Download (remote → local)

## Security

> **Warning**: Scout MCP provides remote shell access. Deploy with care.

### Quick Security Checklist

- [ ] Enable API key authentication (`SCOUT_API_KEYS`)
- [ ] Enable rate limiting (`SCOUT_RATE_LIMIT_PER_MINUTE`)
- [ ] Verify SSH host keys are in `~/.ssh/known_hosts`
- [ ] Set `SCOUT_STRICT_HOST_KEY_CHECKING=true` (default)
- [ ] Bind to `127.0.0.1` if local-only access needed
- [ ] Use SSH keys, not passwords
- [ ] Limit SSH user permissions on remote hosts
- [ ] Review `~/.ssh/config` for only necessary hosts

### Security Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `SCOUT_API_KEYS` | (none) | Comma-separated API keys for authentication |
| `SCOUT_RATE_LIMIT_PER_MINUTE` | 60 | Rate limit per client (requests/minute) |
| `SCOUT_KNOWN_HOSTS` | ~/.ssh/known_hosts | SSH host key verification |
| `SCOUT_STRICT_HOST_KEY_CHECKING` | true | Reject unknown host keys |
| `SCOUT_HTTP_HOST` | 0.0.0.0 | Bind address (use 127.0.0.1 for local only) |
| `SCOUT_MAX_FILE_SIZE` | 1048576 | Max file size in bytes (1MB) |
| `SCOUT_COMMAND_TIMEOUT` | 30 | Command timeout in seconds |

### Built-in Security Features

Scout MCP includes multiple layers of security protection:

- **API Key Authentication**: Optional HTTP header-based authentication (production recommended)
- **Rate Limiting**: Prevents abuse with configurable per-client request limits
- **SSH Host Key Verification**: Validates remote host identity to prevent MITM attacks
- **Path Traversal Protection**: Blocks `../` and other escape sequences
- **Command Injection Protection**: Uses `shlex.quote()` for all paths and arguments
- **Input Validation**: Validates hostnames and paths for malicious patterns
- **File Size Limits**: Prevents memory exhaustion attacks
- **Command Timeouts**: Prevents hanging operations

### Example: Secure Configuration

```bash
# Production deployment (localhost only, strict security)
export SCOUT_API_KEYS="$(openssl rand -hex 32)"  # Enable authentication
export SCOUT_RATE_LIMIT_PER_MINUTE=60            # Rate limiting
export SCOUT_HTTP_HOST="127.0.0.1"
export SCOUT_STRICT_HOST_KEY_CHECKING=true
export SCOUT_MAX_FILE_SIZE=5242880  # 5MB
uv run python -m scout_mcp
```

See [SECURITY.md](SECURITY.md) for complete security documentation, threat model, and deployment best practices.

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

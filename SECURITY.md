# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting Vulnerabilities

Please report security vulnerabilities by opening a GitHub issue with the "security" label.

## Security Model

Scout MCP provides SSH access to remote hosts. It is designed for trusted
environments where the MCP client is authenticated.

### Trust Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                     MCP Client                               │
│  (Claude Desktop, IDE Extension, etc.)                       │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ HTTP/SSE or STDIO
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Scout MCP Server                          │
│  - Validates paths (blocks traversal)                        │
│  - Validates hostnames (blocks injection)                    │
│  - Quotes shell arguments                                    │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ SSH (Key-based auth, host verification)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Remote SSH Hosts                          │
│  - File system access controls                               │
│  - Command execution permissions                             │
│  - User-based authorization                                  │
└─────────────────────────────────────────────────────────────┘
```

### Security Features

| Feature | Status | Configuration |
|---------|--------|---------------|
| API Key Authentication | Optional | `SCOUT_API_KEYS` |
| Rate Limiting | Optional | `SCOUT_RATE_LIMIT_PER_MINUTE` |
| SSH Host Key Verification | Default On | `SCOUT_KNOWN_HOSTS` |
| Path Traversal Protection | Default On | Built-in |
| Command Injection Protection | Default On | Uses shlex.quote() |
| Input Validation | Default On | Built-in |
| File Size Limits | Default On | `SCOUT_MAX_FILE_SIZE` |
| Command Timeout | Default On | `SCOUT_COMMAND_TIMEOUT` |

### Security Recommendations

1. **Enable API key authentication for production:**
   ```bash
   # Generate secure random key
   export SCOUT_API_KEYS="$(openssl rand -hex 32)"
   ```

2. **Always verify SSH host keys:**
   ```bash
   # Add hosts to known_hosts before connecting
   ssh-keyscan your-host >> ~/.ssh/known_hosts
   ```

3. **Bind to localhost for local-only access:**
   ```bash
   export SCOUT_HTTP_HOST="127.0.0.1"
   ```

4. **Enable rate limiting to prevent abuse:**
   ```bash
   export SCOUT_RATE_LIMIT_PER_MINUTE=60  # 60 requests/minute per client
   ```

5. **Use SSH key-based authentication only** (no passwords)

6. **Limit SSH user permissions** on remote hosts
   - Use dedicated service accounts with minimal privileges
   - Restrict file system access via SSH server configuration
   - Use `chroot` or `restricted shell` if appropriate

7. **Review SSH configuration:**
   ```bash
   # Verify your SSH config hosts
   cat ~/.ssh/config

   # Check known_hosts entries
   cat ~/.ssh/known_hosts
   ```

8. **Consider network isolation:**
   - Run scout_mcp in a restricted network zone
   - Use firewall rules to limit SSH access
   - Avoid exposing SSH to the public internet

### Known Limitations

- **STDIO transport:** Relies on local process security (no network-level auth)
- **Command execution:** Allows arbitrary shell commands on remote hosts (by design)
- **File access:** Limited only by SSH user permissions
- **Optional authentication:** API key auth must be explicitly enabled
- **In-memory rate limiting:** Rate limits reset on server restart

### What Scout MCP Protects Against

- **Path traversal attacks:** Blocks `../` and other escape sequences
- **Command injection:** Uses `shlex.quote()` for all paths and arguments
- **Host name injection:** Validates hostnames for suspicious characters
- **Null byte attacks:** Rejects paths containing null bytes
- **MITM attacks:** Verifies SSH host keys (if configured)
- **Memory exhaustion:** Enforces file size limits

### What Scout MCP Does NOT Protect Against

- **Malicious MCP clients:** Assumes client is trusted
- **Privilege escalation:** Relies on SSH server security
- **Data exfiltration:** User can read any file accessible via SSH
- **Resource exhaustion:** Rate limiting is in-memory and per-process
- **Lateral movement:** Commands can access network from remote host

## Configuration Reference

### API Key Authentication

| Variable | Default | Purpose |
|----------|---------|---------|
| `SCOUT_API_KEYS` | (none) | Comma-separated list of API keys |
| `SCOUT_AUTH_ENABLED` | true | Enable/disable auth (if keys set) |

**Security Note:** API key authentication is OPTIONAL but RECOMMENDED for production deployments, especially when exposing the HTTP transport over a network.

**Behavior:**
- **No keys set:** Authentication disabled, all requests allowed
- **Keys set:** All requests require valid `X-API-Key` header
- **SCOUT_AUTH_ENABLED=false:** Disable auth even if keys are set (for testing)

**Example - Enable authentication:**
```bash
# Single key
export SCOUT_API_KEYS="your-secret-key-here"

# Multiple keys (comma-separated)
export SCOUT_API_KEYS="key1,key2,key3"

# Generate secure random key
export SCOUT_API_KEYS="$(openssl rand -hex 32)"
```

**MCP Client Configuration (with auth):**
```json
{
  "mcpServers": {
    "scout_mcp": {
      "url": "http://127.0.0.1:8000/mcp",
      "headers": {
        "X-API-Key": "your-secret-key-here"
      }
    }
  }
}
```

### Rate Limiting

| Variable | Default | Purpose |
|----------|---------|---------|
| `SCOUT_RATE_LIMIT_PER_MINUTE` | 60 | Requests per minute per client |
| `SCOUT_RATE_LIMIT_BURST` | 10 | Maximum burst size |

**Security Note:** Rate limiting protects against abuse and denial-of-service attacks. Limits are per client IP address.

**Behavior:**
- **Default:** 60 requests/minute per client (1 req/second sustained)
- **Burst:** Allows short bursts up to 10 requests
- **Set to 0:** Disables rate limiting
- **Health checks:** Not rate limited

**Example - Strict rate limiting:**
```bash
export SCOUT_RATE_LIMIT_PER_MINUTE=30  # 30 req/min
export SCOUT_RATE_LIMIT_BURST=5        # Allow burst of 5
```

**Response on rate limit:**
```json
{
  "error": "Rate limit exceeded",
  "retry_after": 2
}
```
HTTP 429 status with `Retry-After` header

### SSH Host Key Verification

| Variable | Default | Purpose |
|----------|---------|---------|
| `SCOUT_KNOWN_HOSTS` | ~/.ssh/known_hosts | Path to known_hosts file (must exist) |
| `SCOUT_STRICT_HOST_KEY_CHECKING` | true | Reject unknown host keys |

**Security Warning:** Setting `SCOUT_KNOWN_HOSTS=none` disables host key verification, making connections vulnerable to man-in-the-middle attacks. Only use this in trusted networks or for testing.

**Behavior (Fail-Closed Security):**
- **Default:** Uses `~/.ssh/known_hosts` - **raises FileNotFoundError if file doesn't exist**
- **Custom path:** Set `SCOUT_KNOWN_HOSTS=/path/to/known_hosts` - **raises FileNotFoundError if file doesn't exist**
- **Explicit disable:** Set `SCOUT_KNOWN_HOSTS=none` - logs critical warning and disables verification
- **Strict mode (default):** Connection fails if host key is unknown or mismatched
- **Non-strict mode:** Warns but allows connection if host key verification fails

**Creating known_hosts file:**
```bash
# Add a specific host's key
ssh-keyscan hostname >> ~/.ssh/known_hosts

# Or connect once interactively (answer 'yes' when prompted)
ssh hostname

# Or create empty file (will need to add keys later)
touch ~/.ssh/known_hosts
```

**Example - Disable verification (NOT RECOMMENDED):**
```bash
export SCOUT_KNOWN_HOSTS=none
uv run python -m scout_mcp
```

**Example - Use custom known_hosts location:**
```bash
export SCOUT_KNOWN_HOSTS=/custom/path/known_hosts
uv run python -m scout_mcp
```

**Example - Allow unknown hosts with warning:**
```bash
export SCOUT_STRICT_HOST_KEY_CHECKING=false
uv run python -m scout_mcp
```

**Troubleshooting:**

If you see `FileNotFoundError: SSH host key verification required but ~/.ssh/known_hosts not found`:

1. **Create the file and add host keys:**
   ```bash
   ssh-keyscan your-server-hostname >> ~/.ssh/known_hosts
   ```

2. **Or connect once interactively:**
   ```bash
   ssh your-server-hostname
   # Answer 'yes' when prompted to add the key
   ```

3. **Or disable verification (NOT RECOMMENDED for production):**
   ```bash
   export SCOUT_KNOWN_HOSTS=none
   ```

### Resource Limits

| Variable | Default | Purpose |
|----------|---------|---------|
| `SCOUT_MAX_FILE_SIZE` | 1048576 (1MB) | Maximum file size to read |
| `SCOUT_COMMAND_TIMEOUT` | 30 | Command timeout in seconds |
| `SCOUT_IDLE_TIMEOUT` | 60 | Connection idle timeout |

### Transport Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `SCOUT_TRANSPORT` | http | Transport protocol: "http" or "stdio" |
| `SCOUT_HTTP_HOST` | 0.0.0.0 | HTTP server bind address |
| `SCOUT_HTTP_PORT` | 8000 | HTTP server port |

## Deployment Best Practices

### Development Environment
```bash
# Local development (localhost only)
export SCOUT_HTTP_HOST="127.0.0.1"
export SCOUT_HTTP_PORT="8000"
export SCOUT_STRICT_HOST_KEY_CHECKING=true
uv run python -m scout_mcp
```

### Production Environment
```bash
# Production with strict security
export SCOUT_API_KEYS="$(openssl rand -hex 32)"  # Enable auth
export SCOUT_RATE_LIMIT_PER_MINUTE=60            # Rate limiting
export SCOUT_HTTP_HOST="127.0.0.1"               # Localhost only
export SCOUT_STRICT_HOST_KEY_CHECKING=true
export SCOUT_KNOWN_HOSTS="$HOME/.ssh/known_hosts"
export SCOUT_MAX_FILE_SIZE=5242880  # 5MB limit
export SCOUT_COMMAND_TIMEOUT=60     # 60s timeout
uv run python -m scout_mcp
```

### Testing/Development (Relaxed)
```bash
# WARNING: Less secure, for testing only
export SCOUT_STRICT_HOST_KEY_CHECKING=false
export SCOUT_KNOWN_HOSTS=none  # NOT RECOMMENDED
uv run python -m scout_mcp
```

## Vulnerability Disclosure

Responsibly disclosed vulnerabilities will be addressed within:
- **Critical:** 24 hours
- **High:** 72 hours
- **Medium:** 1 week
- **Low:** Next release

## Security Checklist

Use this checklist before deploying scout_mcp:

- [ ] API key authentication enabled (`SCOUT_API_KEYS` set)
- [ ] Rate limiting configured (`SCOUT_RATE_LIMIT_PER_MINUTE`)
- [ ] SSH host keys verified and in `~/.ssh/known_hosts`
- [ ] `SCOUT_STRICT_HOST_KEY_CHECKING=true` (default)
- [ ] Bind to `127.0.0.1` if local-only access needed
- [ ] SSH user accounts have minimal necessary privileges
- [ ] File size and timeout limits configured appropriately
- [ ] SSH config reviewed for only necessary hosts
- [ ] Network firewall rules restrict SSH access
- [ ] MCP client is trusted (Claude Desktop, etc.)
- [ ] Log monitoring enabled for suspicious activity
- [ ] Regular security updates applied to dependencies

## Security Updates

Check for security updates regularly:
```bash
# Update dependencies
uv lock --upgrade
uv sync

# Check for known vulnerabilities (if using pip-audit)
uv run pip-audit
```

## Additional Resources

- [asyncssh Security](https://asyncssh.readthedocs.io/en/latest/api.html#security)
- [SSH Best Practices](https://www.ssh.com/academy/ssh/best-practices)
- [OWASP Command Injection](https://owasp.org/www-community/attacks/Command_Injection)

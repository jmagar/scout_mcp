# Scout MCP: Data Models and Utilities Research

## Summary

Scout MCP uses a lightweight dataclass-based architecture with minimal validation. All models use standard `@dataclass` (not Pydantic) for simplicity and performance. The system employs lazy singleton patterns for global state and follows a functional approach for utilities. Models flow from user input through parsers, config, and connection pool to SSH executors, with clear separation between data containers and business logic.

**Key Finding:** Zero Pydantic usage - all validation is manual through simple checks. This is intentional for performance and minimal dependencies.

## Key Components

### Models
- `/mnt/cache/code/scout_mcp/scout_mcp/models/target.py` - ScoutTarget: parsed user input
- `/mnt/cache/code/scout_mcp/scout_mcp/models/ssh.py` - SSHHost, PooledConnection: SSH config and connection wrapper
- `/mnt/cache/code/scout_mcp/scout_mcp/models/command.py` - CommandResult: command execution result
- `/mnt/cache/code/scout_mcp/scout_mcp/models/__init__.py` - Public exports

### Configuration
- `/mnt/cache/code/scout_mcp/scout_mcp/config.py` - Config dataclass with SSH config parsing and env var overrides

### Utilities
- `/mnt/cache/code/scout_mcp/scout_mcp/utils/parser.py` - parse_target(): URI parsing
- `/mnt/cache/code/scout_mcp/scout_mcp/utils/ping.py` - check_host_online(), check_hosts_online(): TCP connectivity
- `/mnt/cache/code/scout_mcp/scout_mcp/utils/mime.py` - get_mime_type(): extension-based MIME detection
- `/mnt/cache/code/scout_mcp/scout_mcp/utils/console.py` - ColorfulFormatter, MCPRequestFormatter: logging formatters
- `/mnt/cache/code/scout_mcp/scout_mcp/utils/__init__.py` - Public exports

### State Management
- `/mnt/cache/code/scout_mcp/scout_mcp/services/state.py` - Global singleton accessors (get_config, get_pool)

## Data Model Definitions

### ScoutTarget (models/target.py)
```python
@dataclass
class ScoutTarget:
    """Parsed scout target."""
    host: str | None             # None for 'hosts' command
    path: str = ""               # Remote path (may be empty for hosts command)
    is_hosts_command: bool = False
```

**Purpose:** Intermediate representation of parsed user input after URI parsing.

**Validation:** None at model level - parser does all validation.

**Usage Pattern:**
```python
# Created by parse_target()
ScoutTarget(host="dookie", path="/var/log")           # Normal target
ScoutTarget(host=None, is_hosts_command=True)         # Hosts command
```

### SSHHost (models/ssh.py)
```python
@dataclass
class SSHHost:
    """SSH host configuration."""
    name: str                    # Alias from ssh config (e.g., "dookie")
    hostname: str                # IP or FQDN (e.g., "100.122.19.93")
    user: str = "root"           # Default user
    port: int = 22               # Default SSH port
    identity_file: str | None = None
```

**Purpose:** Immutable configuration for SSH connections, parsed from `~/.ssh/config`.

**Validation:** None at model level - config parser validates hostname required, port defaults to 22 on parse error.

**Usage Pattern:**
```python
# Created by Config._parse_ssh_config()
hosts = config.get_hosts()
ssh_host = config.get_host("dookie")
conn = await pool.get_connection(ssh_host)
```

### PooledConnection (models/ssh.py)
```python
@dataclass
class PooledConnection:
    """A pooled SSH connection with last-used timestamp."""
    connection: "asyncssh.SSHClientConnection"
    last_used: datetime = field(default_factory=datetime.now)

    def touch(self) -> None:
        """Update last-used timestamp."""
        self.last_used = datetime.now()

    @property
    def is_stale(self) -> bool:
        """Check if connection was closed."""
        is_closed: bool = self.connection.is_closed  # type: ignore[assignment]
        return is_closed
```

**Purpose:** Wraps asyncssh connection with metadata for connection pooling lifecycle.

**Methods:**
- `touch()` - Updates last_used timestamp when connection is reused
- `is_stale` property - Checks if underlying SSH connection is closed

**Usage Pattern:**
```python
# Created and managed by ConnectionPool
pooled = PooledConnection(connection=ssh_conn)
pooled.touch()  # On reuse
if not pooled.is_stale:
    return pooled.connection
```

### CommandResult (models/command.py)
```python
@dataclass
class CommandResult:
    """Result of a remote command execution."""
    output: str      # stdout
    error: str       # stderr
    returncode: int  # Exit code (0 = success)
```

**Purpose:** Structured result from SSH command execution.

**Validation:** None - executor captures raw asyncssh output.

**Usage Pattern:**
```python
# Created by executors.run_command()
result = await run_command(conn, working_dir, command, timeout)
if result.returncode != 0:
    return f"Command failed: {result.error}"
return result.output
```

## Configuration Model (config.py)

### Config Dataclass
```python
@dataclass
class Config:
    """Scout MCP configuration."""
    ssh_config_path: Path = field(default_factory=lambda: Path.home() / ".ssh" / "config")
    allowlist: list[str] = field(default_factory=list)
    blocklist: list[str] = field(default_factory=list)
    max_file_size: int = 1_048_576  # 1MB
    command_timeout: int = 30
    idle_timeout: int = 60
    transport: str = "http"         # "http" or "stdio"
    http_host: str = "0.0.0.0"
    http_port: int = 8000

    _hosts: dict[str, SSHHost] = field(default_factory=dict, init=False, repr=False)
    _parsed: bool = field(default=False, init=False, repr=False)
```

**Key Features:**
1. **Environment Variable Overrides** - Applied in `__post_init__()`
2. **Lazy SSH Config Parsing** - Only parses on first `get_hosts()` call
3. **Legacy Prefix Support** - Both `SCOUT_*` and `MCP_CAT_*` prefixes (SCOUT takes precedence)
4. **Filtering** - Allowlist (inclusive) or blocklist (exclusive) via fnmatch patterns

### Environment Variables
| Variable | Type | Default | Legacy Alias |
|----------|------|---------|--------------|
| SCOUT_MAX_FILE_SIZE | int | 1048576 | MCP_CAT_MAX_FILE_SIZE |
| SCOUT_COMMAND_TIMEOUT | int | 30 | MCP_CAT_COMMAND_TIMEOUT |
| SCOUT_IDLE_TIMEOUT | int | 60 | MCP_CAT_IDLE_TIMEOUT |
| SCOUT_TRANSPORT | str | "http" | - |
| SCOUT_HTTP_HOST | str | "0.0.0.0" | - |
| SCOUT_HTTP_PORT | int | 8000 | - |

**Validation:** All env vars use `contextlib.suppress(ValueError)` - invalid values fall back to defaults.

### SSH Config Parsing Logic
```python
def _parse_ssh_config(self) -> None:
    """Parse SSH config file and populate hosts."""
    # 1. Check if already parsed (idempotent)
    # 2. Check file exists (warn if missing)
    # 3. Read file (treat unreadable as empty)
    # 4. Regex parse: Host directive + key-value pairs
    # 5. Build SSHHost objects (skip if no hostname)
    # 6. Store in _hosts dict
```

**Parsing Rules:**
- Case-insensitive directives (Host, HostName, User, Port, IdentityFile)
- Port defaults to 22 if invalid
- User defaults to "root"
- Hosts without HostName are skipped
- Comments and empty lines ignored

**Filtering:**
```python
def _is_host_allowed(self, name: str) -> bool:
    """Check if host passes allowlist/blocklist filters."""
    # Allowlist takes precedence (explicit inclusion)
    # If no allowlist, check blocklist (explicit exclusion)
    # Default: allow all
```

## Utility Functions

### parser.py - URI Parsing
```python
def parse_target(target: str) -> ScoutTarget:
    """Parse a scout target URI.

    Formats:
        - "hosts" -> list available hosts
        - "hostname:/path" -> target a specific path on host

    Returns:
        ScoutTarget with parsed components.

    Raises:
        ValueError: If target format is invalid.
    """
```

**Validation Logic:**
1. Strip whitespace
2. Case-insensitive check for "hosts" special command
3. Check for colon separator
4. Split on first colon only (paths may contain colons)
5. Validate host and path are not empty

**Error Messages:**
- "Invalid target 'X'. Expected 'host:/path' or 'hosts'" - no colon
- "Host cannot be empty" - empty host part
- "Path cannot be empty" - empty path part

**Performance:** <0.01ms average (benchmarked in test_uri_parsing.py)

### ping.py - Host Connectivity
```python
async def check_host_online(hostname: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a host is reachable via TCP connection."""
    # Attempts asyncio.open_connection() with timeout
    # Returns True if connection succeeds, False on timeout/OSError
    # Properly closes writer to avoid resource leaks

async def check_hosts_online(
    hosts: dict[str, tuple[str, int]],
    timeout: float = 2.0,
) -> dict[str, bool]:
    """Check multiple hosts concurrently."""
    # Uses asyncio.gather() for concurrent checks
    # Returns dict mapping host names to online status
```

**Implementation Details:**
- Pure TCP connection test (no SSH auth)
- Timeout defaults to 2 seconds
- Returns False for ANY exception (TimeoutError, OSError, etc.)
- Concurrent execution via gather() - scales O(1) time for N hosts
- Properly closes connections to avoid resource leaks

**Performance:** Concurrent checks complete in ~timeout seconds regardless of host count (verified in test_ping.py with 3 hosts at 0.1s each completing in <0.2s)

### mime.py - MIME Type Detection
```python
def get_mime_type(path: str) -> str:
    """Infer MIME type from file extension.

    Args:
        path: File path to analyze.

    Returns:
        MIME type string, defaults to 'text/plain'.
    """
```

**Supported Extensions:**
- **Config:** .conf, .cfg, .ini → text/plain
- **Config (special):** .yaml/.yml → text/yaml, .json → application/json, .xml → application/xml
- **Scripts:** .sh/.bash/.zsh → text/x-shellscript, .py → text/x-python, .js → text/javascript, etc.
- **Web:** .html/.htm → text/html, .css → text/css
- **Docs:** .md → text/markdown, .txt/.log → text/plain, .csv → text/csv

**Implementation:** Simple dict lookup on lowercase extension, defaults to "text/plain".

**Usage:** Currently used for setting MIME types on MCP resource responses.

### console.py - Logging Formatters
```python
class ColorfulFormatter(logging.Formatter):
    """Colorful log formatter with EST timestamps and component highlighting."""
    # Formats: timestamp | level | component | message
    # Uses ANSI color codes for visual hierarchy
    # EST timezone with milliseconds
    # Highlights tool names, URIs, durations, SSH patterns

class MCPRequestFormatter(ColorfulFormatter):
    """Extended formatter with MCP request/response details."""
    # Adds visual indicators: >>>, <<<, !!, OK, +, -, ~
    # Highlights lifecycle events (starting, shutdown, errors, etc.)
```

**Color Scheme:**
- DEBUG → bright_black (dim)
- INFO → bright_green
- WARNING → bright_yellow
- ERROR → bright_red
- CRITICAL → red background + white text + bold

**Component Colors:**
- scout_mcp.server → bright_cyan
- scout_mcp.services.pool → bright_magenta
- scout_mcp.tools.scout → bright_blue
- scout_mcp.resources → cyan
- scout_mcp.middleware → yellow
- scout_mcp.config → green

**Message Highlighting:**
- Tool names (tool:scout) → bright_cyan
- URIs (host://path) → bright_blue
- Durations (123.45ms) → bright_yellow
- SSH connection info (user@host:port) → bright_magenta
- Pool size (pool_size=N) → cyan

**Timestamp Format:** `HH:MM:SS.mmm MM/DD` (EST timezone)

## Data Flow Through System

### Request Lifecycle
```
1. User Input (string)
   └→ "dookie:/var/log/app.log"

2. URI Parsing
   └→ parse_target(target)
   └→ ScoutTarget(host="dookie", path="/var/log/app.log")

3. Config Lookup
   └→ config.get_host("dookie")
   └→ SSHHost(name="dookie", hostname="100.122.19.93", user="jmagar", port=22)

4. Connection Pool
   └→ pool.get_connection(ssh_host)
   └→ PooledConnection(connection=asyncssh_conn, last_used=datetime.now())
   └→ Returns: asyncssh.SSHClientConnection

5. Executor
   └→ stat_path(conn, "/var/log/app.log") → "file"
   └→ cat_file(conn, "/var/log/app.log", max_size=1048576)
   └→ Returns: (contents, was_truncated)

6. Response Formatting
   └→ Return file contents as string
```

### Hosts Command Flow
```
1. User Input: "hosts"
   └→ parse_target("hosts")
   └→ ScoutTarget(host=None, is_hosts_command=True)

2. Get All Hosts
   └→ config.get_hosts()
   └→ dict[str, SSHHost]

3. Concurrent Connectivity Check
   └→ check_hosts_online({name: (hostname, port)})
   └→ dict[str, bool]

4. Format Response
   └→ "[✓] dookie (online) -> jmagar@100.122.19.93:22"
   └→ "[✗] offline-host (offline) -> root@10.0.0.5:22"
```

### Command Execution Flow
```
1. User Input: "dookie:/var/log", query="grep ERROR app.log"
   └→ ScoutTarget(host="dookie", path="/var/log")

2. Connection + Execution
   └→ run_command(conn, working_dir="/var/log", command="grep ERROR app.log", timeout=30)
   └→ CommandResult(output="...", error="...", returncode=0)

3. Format Response
   └→ output + "\n---\nErrors:\n" + error + "\n\nExit code: 0"
```

## Implementation Patterns

### Lazy Singleton Pattern
Used for global state (config and pool):

```python
# services/state.py
_config: Config | None = None

def get_config() -> Config:
    """Get or create config."""
    global _config
    if _config is None:
        _config = Config()
    return _config
```

**Benefits:**
- Deferred initialization (config only parsed when first accessed)
- Single source of truth across codebase
- Easy to inject mocks in tests via set_config()/set_pool()

**Testing Support:**
```python
def reset_state() -> None:
    """Reset global state for testing."""
    global _config, _pool
    _config = None
    _pool = None
```

### Validation Strategy
No Pydantic or validation libraries - manual checks at boundary:

**Parser Level:**
```python
if ":" not in target:
    raise ValueError("Invalid target")
if not host:
    raise ValueError("Host cannot be empty")
```

**Config Level:**
```python
# Invalid port → default to 22
try:
    port = int(current_data.get("port", "22"))
except ValueError:
    port = 22

# Missing hostname → skip host entirely
if current_host and current_data.get("hostname"):
    self._hosts[current_host] = SSHHost(...)
```

**Env Var Level:**
```python
# Invalid value → ignore and use default
with suppress(ValueError):
    return int(val)
```

### Error Handling Philosophy
**Tools:** Return error strings (never raise)
```python
try:
    parsed = parse_target(target)
except ValueError as e:
    return f"Error: {e}"
```

**Resources:** Raise ResourceError (MCP standard)
```python
if ssh_host is None:
    raise ResourceError(f"Unknown host '{host}'")
```

**Connection Retry Pattern:**
```python
try:
    conn = await pool.get_connection(ssh_host)
except Exception as first_error:
    await pool.remove_connection(ssh_host.name)  # Clear stale
    conn = await pool.get_connection(ssh_host)   # Retry once
```

### Immutability vs Mutability
**Immutable Models:**
- ScoutTarget - created once by parser
- SSHHost - config snapshot
- CommandResult - execution snapshot

**Mutable State:**
- Config._hosts - populated on first parse
- PooledConnection.last_used - updated on reuse

**Design Rationale:** Models are data containers (immutable), state is tracked separately (mutable).

## Considerations

### No Pydantic
**Why:**
- Performance: dataclasses are faster than Pydantic for simple cases
- Simplicity: No validation DSL to learn
- Dependencies: Fewer external dependencies

**Trade-offs:**
- Manual validation scattered across parsers/config
- No automatic type coercion
- No built-in serialization helpers

**When to reconsider:**
- If adding API endpoints that need request validation
- If adding configuration files (YAML/JSON) that need schema validation
- If model complexity increases significantly

### Type Hints vs Runtime Validation
**Current approach:** Type hints for IDE/mypy, no runtime enforcement

**Example:**
```python
@dataclass
class SSHHost:
    name: str  # Type hint only - no runtime check
    port: int  # Can be any type at runtime
```

**Rationale:** Trust boundaries are at parser/config level, internal code assumes valid data.

### Connection Pool Lifecycle
**Model involvement:**
- PooledConnection wraps connection + metadata
- touch() updates timestamp
- is_stale property checks connection state

**Not in model:**
- Pool cleanup logic (services/pool.py)
- Connection creation (services/pool.py)
- Idle timeout enforcement (background task)

**Design:** Model is passive wrapper, pool owns lifecycle.

### Environment Variable Pattern
**Two-prefix strategy:**
1. Check SCOUT_* prefix (new)
2. Fall back to MCP_CAT_* prefix (legacy)
3. Use default if both missing/invalid

**Validation:** Always use `with suppress(ValueError)` to prevent crashes from invalid env vars.

**Example:**
```python
def get_env_int(scout_key: str, legacy_key: str) -> int | None:
    if val := os.getenv(scout_key):
        with suppress(ValueError):
            return int(val)
    if val := os.getenv(legacy_key):
        with suppress(ValueError):
            return int(val)
    return None
```

### SSH Config Parsing Edge Cases
**Handled:**
- Missing file (empty hosts dict)
- Unreadable file (treat as empty)
- Invalid port (default to 22)
- Host without HostName (skip)
- Comments and empty lines (ignore)
- Case-insensitive directives
- Multiple spaces in directives

**Not handled:**
- Include directives (no recursive parsing)
- Wildcards in Host patterns (treated as literal names)
- Match directives (SSH conditional blocks)
- Complex IdentityFile paths with ~ expansion

**Rationale:** Covers 95% of SSH configs, avoids complexity of full SSH config spec.

### Performance Characteristics
**URI Parsing:** <0.01ms (simple string operations)

**Host Connectivity Check:**
- Single host: ~timeout duration (default 2s)
- Multiple hosts: ~timeout duration (concurrent via gather)

**SSH Config Parsing:**
- Lazy: only on first get_hosts() call
- Cached: stored in _hosts dict
- Fast: simple regex matching

**MIME Detection:** O(N) where N = number of extensions (42 entries), case-insensitive string comparison

## Testing Patterns

### Config Testing
Uses tmp_path fixture for isolated SSH configs:
```python
def test_parse_ssh_config_extracts_hosts(tmp_path: Path):
    ssh_config = tmp_path / "config"
    ssh_config.write_text("Host dookie\n    HostName 100.122.19.93")
    config = Config(ssh_config_path=ssh_config)
    hosts = config.get_hosts()
```

### Parser Testing
Direct unit tests with pytest.raises:
```python
def test_parse_target_invalid_raises():
    with pytest.raises(ValueError, match="Invalid target"):
        parse_target("invalid-no-colon")
```

### Async Utilities Testing
Uses pytest.mark.asyncio and mocks:
```python
@pytest.mark.asyncio
async def test_check_host_online_reachable():
    with patch("asyncio.open_connection", new_callable=AsyncMock):
        result = await check_host_online("192.168.1.1", 22)
```

### State Management Testing
Uses reset_state() fixture:
```python
@pytest.fixture(autouse=True)
def reset_global_state():
    reset_state()
    yield
    reset_state()
```

## Next Steps

### For New Features
1. **Check existing models first** - likely already have what you need
2. **Consider dataclass vs Pydantic** - stick with dataclass for simple cases
3. **Validate at boundaries** - parser/config level, not in models
4. **Use lazy singletons** - follow get_config()/get_pool() pattern

### If Adding Configuration
1. Add field to Config dataclass with default
2. Add env var override in __post_init__()
3. Document in CLAUDE.md
4. Add test in test_config.py

### If Adding Models
1. Create in appropriate models/ file (target, ssh, command, or new file)
2. Use @dataclass decorator
3. Add to models/__init__.py exports
4. Add tests showing creation and usage
5. Document in models/CLAUDE.md

### If Adding Utilities
1. Create in utils/ (prefer pure functions)
2. Add to utils/__init__.py exports
3. Write unit tests
4. Document in utils/CLAUDE.md
5. Benchmark if performance-critical

### If Refactoring to Pydantic
**Motivation required:**
- Complex nested validation needed
- API request/response validation
- Configuration file schemas (YAML/JSON)

**Migration path:**
1. Start with one model (e.g., Config)
2. Add pydantic to dependencies
3. Convert dataclass → BaseModel
4. Add validators
5. Update tests
6. Repeat for other models if beneficial

**Keep in mind:** Current approach is intentionally minimal - only add complexity if clear benefit.

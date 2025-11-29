# models/

Dataclasses representing core domain entities. Lightweight data containers with minimal behavior.

## Dataclasses

### ScoutTarget (`target.py`)
Parsed scout URI from user input.
```python
@dataclass
class ScoutTarget:
    host: str | None            # SSH host name (None if hosts command)
    path: str = ""              # Remote path
    is_hosts_command: bool = False
```

**Usage:**
```python
ScoutTarget(host="dookie", path="/var/log")      # Normal target
ScoutTarget(host=None, is_hosts_command=True)    # "hosts" command
```

### SSHHost (`ssh.py`)
SSH connection configuration parsed from ~/.ssh/config.
```python
@dataclass
class SSHHost:
    name: str                   # Alias (e.g., "dookie")
    hostname: str               # IP or hostname
    user: str = "root"
    port: int = 22
    identity_file: str | None = None
```

### PooledConnection (`ssh.py`)
Wraps asyncssh connection with lifetime tracking.
```python
@dataclass
class PooledConnection:
    connection: asyncssh.SSHClientConnection
    last_used: datetime = field(default_factory=datetime.now)

    def touch(self) -> None:        # Update last_used
    @property
    def is_stale(self) -> bool:     # Check if connection closed
```

### CommandResult (`command.py`)
Result of remote command execution.
```python
@dataclass
class CommandResult:
    output: str      # stdout
    error: str       # stderr
    returncode: int  # Exit code (0 = success)
```

## Relationships

```
User Input → parse_target() → ScoutTarget
                                  ↓
                            config.get_host()
                                  ↓
                              SSHHost
                                  ↓
                         pool.get_connection()
                                  ↓
                          PooledConnection
                                  ↓
                      executors.run_command()
                                  ↓
                          CommandResult
```

## Import

```python
from scout_mcp.models import ScoutTarget, SSHHost, PooledConnection, CommandResult
```

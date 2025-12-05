# AsyncSSH Best Practices Research Report

**Date:** 2025-12-03
**Focus:** Production-ready SSH client patterns for Python
**Library:** AsyncSSH 2.21+ (Python 3.11+)

## Executive Summary

This report provides comprehensive best practices for building robust SSH clients using the AsyncSSH library, based on official documentation, maintainer recommendations, and real-world production patterns. Includes specific recommendations for the Scout MCP connection pooling implementation.

---

## 1. Connection Pooling

### Current Scout MCP Implementation Analysis

**Strengths:**
- Dictionary-based pooling (maintainer-recommended pattern)
- Lock-based thread safety
- Automatic idle timeout cleanup
- One connection per host with reuse

**Areas for Enhancement:**

#### 1.1 Connection Timeout Configuration

**Issue:** Current implementation lacks timeout on TCP connection establishment.

**Current Code:**
```python
conn = await asyncssh.connect(
    host.hostname,
    port=host.port,
    username=host.user,
    known_hosts=None,
    client_keys=client_keys,
)
```

**Recommended Pattern (AsyncSSH 2.8.1+):**
```python
conn = await asyncssh.connect(
    host.hostname,
    port=host.port,
    username=host.user,
    known_hosts=None,
    client_keys=client_keys,
    connect_timeout=30,  # Timeout for TCP + SSH handshake
    login_timeout=30,    # Timeout for authentication
    keepalive_interval=60,  # Send keepalive every 60s
    keepalive_count_max=3,  # Disconnect after 3 failed keepalives
)
```

**Alternative Pattern (Pre-2.8.1):**
```python
import asyncio

try:
    conn = await asyncio.wait_for(
        asyncssh.connect(
            host.hostname,
            port=host.port,
            username=host.user,
            known_hosts=None,
            client_keys=client_keys,
            login_timeout=30,
            keepalive_interval=60,
            keepalive_count_max=3,
        ),
        timeout=30  # Total connection timeout
    )
except asyncio.TimeoutError:
    raise RuntimeError(f"Connection to {host.name} timed out")
```

**Source:** [AsyncSSH Discussion #409](https://github.com/ronf/asyncssh/discussions/409)

#### 1.2 Connection State Detection

**Issue:** Detecting stale connections is challenging with connection pooling.

**Current Implementation:**
```python
if pooled and not pooled.is_stale:
    # is_stale checks: conn._transport is None
```

**Known Limitation:** `_transport is None` doesn't reliably detect server-closed connections, especially with firewall/idle timeouts.

**Recommended Solutions:**

**Option A: Keepalive Configuration (Preferred)**
```python
# In pool.py get_connection()
conn = await asyncssh.connect(
    host.hostname,
    port=host.port,
    username=host.user,
    known_hosts=None,
    client_keys=client_keys,
    keepalive_interval=60,      # Ping server every 60s
    keepalive_count_max=3,      # Disconnect after 3 failures
    server_host_key_algs='default',  # Advertise all supported algorithms
)
```

**Option B: Connection Validation Before Use**
```python
async def _validate_connection(self, conn: asyncssh.SSHClientConnection) -> bool:
    """Test if connection is still alive."""
    try:
        # Quick no-op command to verify connection
        result = await asyncio.wait_for(
            conn.run('true', check=False),
            timeout=2
        )
        return result.returncode == 0
    except (asyncssh.Error, asyncio.TimeoutError):
        return False

async def get_connection(self, host: "SSHHost") -> asyncssh.SSHClientConnection:
    async with self._lock:
        pooled = self._connections.get(host.name)

        # Validate existing connection
        if pooled and not pooled.is_stale:
            if await self._validate_connection(pooled.connection):
                pooled.touch()
                return pooled.connection
            else:
                logger.info("Connection to %s failed validation, reconnecting", host.name)
                pooled.connection.close()
                del self._connections[host.name]

        # Create new connection...
```

**Source:** [AsyncSSH Issue #172](https://github.com/ronf/asyncssh/issues/172)

#### 1.3 Connection Retry Pattern

**Current Pattern:**
```python
# In tools/resources
try:
    conn = await pool.get_connection(ssh_host)
except Exception:
    await pool.remove_connection(ssh_host.name)
    conn = await pool.get_connection(ssh_host)  # Retry once
```

**Enhanced Pattern with Exponential Backoff:**
```python
async def get_connection_with_retry(
    pool: ConnectionPool,
    host: SSHHost,
    max_retries: int = 2,
    base_delay: float = 1.0
) -> asyncssh.SSHClientConnection:
    """Get connection with exponential backoff retry."""
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            conn = await pool.get_connection(host)
            if attempt > 0:
                logger.info(
                    "Connection to %s succeeded on retry %d",
                    host.name, attempt
                )
            return conn
        except Exception as e:
            last_error = e
            logger.warning(
                "Connection to %s failed (attempt %d/%d): %s",
                host.name, attempt + 1, max_retries + 1, e
            )

            if attempt < max_retries:
                await pool.remove_connection(host.name)
                delay = base_delay * (2 ** attempt)  # 1s, 2s, 4s...
                await asyncio.sleep(delay)

    raise RuntimeError(
        f"Failed to connect to {host.name} after {max_retries + 1} attempts"
    ) from last_error
```

---

## 2. Error Handling & Reconnection Strategies

### 2.1 Exception Handling Patterns

**Key AsyncSSH Exceptions:**
```python
import asyncssh

# Connection errors
asyncssh.DisconnectError       # SSH connection closed
asyncssh.ConnectionLost        # Connection dropped unexpectedly
asyncssh.ChannelOpenError      # Failed to open SSH channel

# Authentication errors
asyncssh.PermissionDenied      # Auth failed
asyncssh.PublicKeyNotAccepted  # Key rejected

# SFTP errors
asyncssh.SFTPError            # Base SFTP error
asyncssh.SFTPNoConnection     # SFTP connection closed
asyncssh.SFTPFailure          # Generic SFTP failure
```

**Recommended Error Handler:**
```python
async def execute_ssh_operation(
    conn: asyncssh.SSHClientConnection,
    operation: callable,
    *args,
    **kwargs
) -> Any:
    """Execute SSH operation with comprehensive error handling."""
    try:
        return await operation(conn, *args, **kwargs)

    except asyncssh.ChannelOpenError as e:
        # Server closed connection or killed SSH process
        logger.error("SSH channel error: %s", e)
        raise RuntimeError(f"SSH channel closed: {e}") from e

    except asyncssh.DisconnectError as e:
        # Clean disconnect with reason
        logger.error("SSH disconnect (code=%s): %s", e.code, e.reason)
        raise RuntimeError(f"SSH disconnected: {e.reason}") from e

    except asyncssh.ConnectionLost as e:
        # Unexpected connection loss
        logger.error("SSH connection lost: %s", e)
        raise RuntimeError("SSH connection lost unexpectedly") from e

    except asyncio.TimeoutError:
        logger.error("SSH operation timed out")
        raise RuntimeError("SSH operation timed out")

    except asyncssh.Error as e:
        # Generic AsyncSSH error
        logger.error("SSH error: %s", e)
        raise RuntimeError(f"SSH error: {e}") from e
```

### 2.2 Graceful Shutdown & Cleanup

**Current Implementation:**
```python
async def close_all(self) -> None:
    """Close all connections."""
    async with self._lock:
        for name, pooled in self._connections.items():
            pooled.connection.close()
        self._connections.clear()

        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
```

**Enhanced Pattern with Proper Cleanup:**
```python
async def close_all(self) -> None:
    """Close all connections gracefully."""
    async with self._lock:
        count = len(self._connections)
        if count > 0:
            logger.info("Shutting down connection pool (%d connections)", count)

            # Close all connections
            close_tasks = []
            for name, pooled in self._connections.items():
                logger.debug("Closing connection to %s", name)
                pooled.connection.close()
                # Wait for connection cleanup
                close_tasks.append(pooled.connection.wait_closed())

            # Wait for all connections to close (with timeout)
            try:
                await asyncio.wait_for(
                    asyncio.gather(*close_tasks, return_exceptions=True),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning("Connection cleanup timed out")

            self._connections.clear()

        # Cancel cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass  # Expected
            logger.debug("Cleanup task cancelled")
```

**Application Shutdown Pattern:**
```python
# In __main__.py or server shutdown handler
async def shutdown_handler(pool: ConnectionPool):
    """Handle graceful shutdown on SIGTERM/SIGINT."""
    logger.info("Received shutdown signal, cleaning up...")

    # Close all SSH connections
    await pool.close_all()

    # Cancel any remaining tasks
    tasks = [t for t in asyncio.all_tasks() if not t.done()]
    logger.debug("Cancelling %d remaining tasks", len(tasks))

    for task in tasks:
        task.cancel()

    # Wait for cancellation with timeout
    try:
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=3.0
        )
    except asyncio.TimeoutError:
        logger.warning("Task cancellation timed out")

# Register signal handlers
import signal
loop = asyncio.get_event_loop()
for sig in (signal.SIGTERM, signal.SIGINT):
    loop.add_signal_handler(
        sig,
        lambda: asyncio.create_task(shutdown_handler(pool))
    )
```

**Source:** [AsyncSSH API Documentation](https://asyncssh.readthedocs.io/en/latest/api.html)

---

## 3. Security Best Practices

### 3.1 Host Key Verification

**Current Implementation (INSECURE):**
```python
conn = await asyncssh.connect(
    host.hostname,
    known_hosts=None,  # ⚠️ DISABLES HOST KEY VERIFICATION
)
```

**Risk:** Vulnerable to man-in-the-middle (MITM) attacks.

**Recommended Solutions:**

**Option A: Use known_hosts File (Simplest)**
```python
# Default behavior - uses ~/.ssh/known_hosts
conn = await asyncssh.connect(
    host.hostname,
    port=host.port,
    username=host.user,
    client_keys=client_keys,
    # known_hosts parameter omitted = uses default
)
```

**Pre-population Strategy:**
```bash
# Users should manually SSH to hosts first to populate known_hosts
ssh user@hostname

# Or use ssh-keyscan for automation
ssh-keyscan -H hostname >> ~/.ssh/known_hosts
```

**Option B: Bundle Host Keys with Application**
```python
from pathlib import Path

# Store host keys in application config
HOST_KEYS_PATH = Path(__file__).parent / "config" / "trusted_host_keys"

conn = await asyncssh.connect(
    host.hostname,
    port=host.port,
    username=host.user,
    client_keys=client_keys,
    known_hosts=([str(HOST_KEYS_PATH)], [], []),  # (trusted_keys, ca_keys, revoked_keys)
)
```

**Option C: Callback-Based Validation (Most Flexible)**
```python
from asyncssh import SSHClient, SSHKey

class HostKeyValidator(SSHClient):
    """Custom SSH client with host key validation."""

    def __init__(self, trusted_keys: dict[str, SSHKey]):
        self._trusted_keys = trusted_keys

    async def validate_host_public_key(
        self,
        host: str,
        addr: str,
        port: int,
        key: SSHKey
    ) -> bool:
        """Validate server host key."""
        # Check against trusted keys
        fingerprint = key.get_fingerprint()

        if host in self._trusted_keys:
            trusted_fingerprint = self._trusted_keys[host].get_fingerprint()
            if fingerprint == trusted_fingerprint:
                logger.debug("Host key verified for %s", host)
                return True
            else:
                logger.error(
                    "Host key mismatch for %s! Expected %s, got %s",
                    host, trusted_fingerprint, fingerprint
                )
                return False

        # Unknown host - log and reject (or prompt user)
        logger.warning(
            "Unknown host %s with fingerprint %s",
            host, fingerprint
        )
        return False

# Usage
trusted_keys = load_trusted_keys()  # Load from config
conn = await asyncssh.connect(
    host.hostname,
    port=host.port,
    username=host.user,
    client_keys=client_keys,
    client_factory=lambda: HostKeyValidator(trusted_keys)
)
```

**Configuration Option:**
```python
# In config.py
@dataclass
class Config:
    verify_host_keys: bool = True  # Disable for dev/testing only
    trusted_host_keys_path: Path | None = None

# In pool.py
if config.verify_host_keys:
    known_hosts_arg = {}  # Use default ~/.ssh/known_hosts
else:
    known_hosts_arg = {"known_hosts": None}  # Disable verification
    logger.warning("⚠️  Host key verification DISABLED - insecure!")

conn = await asyncssh.connect(
    host.hostname,
    port=host.port,
    username=host.user,
    client_keys=client_keys,
    **known_hosts_arg,
)
```

**Sources:**
- [Stack Overflow: Host key not trusted](https://stackoverflow.com/questions/67222941/can-not-connect-via-asyncssh-error-host-key-is-not-trusted)
- [AsyncSSH Issue #179](https://github.com/ronf/asyncssh/issues/179)

### 3.2 Key Management

**Current Implementation:**
```python
client_keys = [host.identity_file] if host.identity_file else None
```

**Enhancement for PKCS#11 Security Tokens:**
```python
from asyncssh import load_pkcs11_keys

# For applications opening multiple SSH connections with PKCS#11 keys,
# load keys once to avoid repeated token access
class ConnectionPool:
    def __init__(self, idle_timeout: int = 60):
        self.idle_timeout = idle_timeout
        self._connections: dict[str, PooledConnection] = {}
        self._lock = asyncio.Lock()
        self._pkcs11_keys = None  # Cache PKCS#11 keys

    async def _load_pkcs11_keys_once(self):
        """Load PKCS#11 keys once and cache."""
        if self._pkcs11_keys is None:
            try:
                self._pkcs11_keys = await load_pkcs11_keys()
                logger.info("Loaded PKCS#11 keys from security tokens")
            except Exception as e:
                logger.warning("Failed to load PKCS#11 keys: %s", e)
                self._pkcs11_keys = []
        return self._pkcs11_keys

    async def get_connection(self, host: "SSHHost") -> asyncssh.SSHClientConnection:
        # Prepare client keys
        client_keys = []
        if host.identity_file:
            client_keys.append(host.identity_file)

        # Add PKCS#11 keys if available
        pkcs11_keys = await self._load_pkcs11_keys_once()
        client_keys.extend(pkcs11_keys)

        conn = await asyncssh.connect(
            host.hostname,
            port=host.port,
            username=host.user,
            client_keys=client_keys or None,
            # ...
        )
```

**Source:** [AsyncSSH Documentation](https://asyncssh.readthedocs.io/)

---

## 4. Performance Optimization

### 4.1 Session Multiplexing

**Key Insight:** AsyncSSH supports multiple concurrent channels (sessions) over a single SSH connection.

**Current Approach:** Scout MCP uses one connection per host (correct pattern).

**Session Limit Management:**

SSH servers typically limit sessions per connection (default: 10 for OpenSSH's `MaxSessions`).

**Pattern: Semaphore for Session Limiting**
```python
import asyncio

class ConnectionPool:
    def __init__(self, idle_timeout: int = 60):
        self.idle_timeout = idle_timeout
        self._connections: dict[str, PooledConnection] = {}
        self._session_semaphores: dict[str, asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()
        self._max_sessions_per_host = 8  # Conservative (server default is 10)

    async def execute_on_host(
        self,
        host: SSHHost,
        operation: callable,
        *args,
        **kwargs
    ):
        """Execute operation with session limit enforcement."""
        # Get or create semaphore for this host
        if host.name not in self._session_semaphores:
            self._session_semaphores[host.name] = asyncio.Semaphore(
                self._max_sessions_per_host
            )

        sem = self._session_semaphores[host.name]

        # Acquire session slot
        async with sem:
            conn = await self.get_connection(host)
            return await operation(conn, *args, **kwargs)
```

**Usage:**
```python
# Instead of:
conn = await pool.get_connection(host)
result = await cat_file(conn, path, max_size)

# Use:
result = await pool.execute_on_host(host, cat_file, path, max_size)
```

**Parallel Operations Example:**
```python
async def read_multiple_files(pool: ConnectionPool, host: SSHHost, paths: list[str]):
    """Read multiple files in parallel on same host."""
    tasks = [
        pool.execute_on_host(host, cat_file, path, 1_048_576)
        for path in paths
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

**Sources:**
- [AsyncSSH Issue #456](https://github.com/ronf/asyncssh/issues/456)
- [AsyncSSH Issue #241](https://github.com/ronf/asyncssh/issues/241)

### 4.2 Parallel Command Execution

**Current Pattern:** Sequential execution via connection reuse.

**Enhanced Pattern: Parallel Execution Across Hosts**
```python
async def execute_on_multiple_hosts(
    pool: ConnectionPool,
    hosts: list[SSHHost],
    command: str,
    timeout: int = 30
):
    """Execute command on multiple hosts in parallel."""
    async def run_on_host(host: SSHHost):
        try:
            result = await pool.execute_on_host(
                host,
                run_command,
                "/",  # working_dir
                command,
                timeout
            )
            return (host.name, result)
        except Exception as e:
            logger.error("Command failed on %s: %s", host.name, e)
            return (host.name, None)

    tasks = [run_on_host(host) for host in hosts]
    results = await asyncio.gather(*tasks)
    return dict(results)
```

**Performance Benchmark (from research):**
- AsyncSSH is ~15x faster than other libraries for multi-host operations
- Single-host performance is roughly equivalent across libraries
- Best performance when using one event loop with multiple tasks

**Source:** [A Tale of Five Python SSH Libraries](https://elegantnetwork.github.io/posts/comparing-ssh/)

### 4.3 Keepalive Configuration

**Purpose:** Prevent firewall/NAT timeout disconnections.

**Recommended Settings:**
```python
conn = await asyncssh.connect(
    host.hostname,
    port=host.port,
    username=host.user,
    client_keys=client_keys,
    keepalive_interval=60,      # Send keepalive every 60 seconds
    keepalive_count_max=3,      # Disconnect after 3 consecutive failures
    # Server will disconnect after ~3 minutes of no response
)
```

**Important:** Keepalives only work within active async context. Connections outside event loop won't send keepalives.

**Source:** [Google Groups: Keep alive an idle connection](https://groups.google.com/g/asyncssh-users/c/wjSmLMFRit0)

---

## 5. Memory Management & Large File Transfers

### 5.1 Current Implementation Analysis

**Strengths:**
- Uses `head -c` to limit file reads
- Checks for truncation
- Max file size configurable

**Limitations:**
- Loads entire file into memory
- No streaming for large files

### 5.2 SFTP Streaming for Large Files

**For files > 1MB, use SFTP instead of `cat`:**

```python
async def stream_large_file(
    conn: asyncssh.SSHClientConnection,
    remote_path: str,
    max_size: int,
    chunk_size: int = 65536,  # 64KB chunks
) -> tuple[str, bool]:
    """Stream large file via SFTP with chunked reads."""
    try:
        async with conn.start_sftp_client() as sftp:
            # Get file size
            attrs = await sftp.stat(remote_path)
            file_size = attrs.size

            if file_size > max_size:
                # Read only first max_size bytes
                bytes_to_read = max_size
                was_truncated = True
            else:
                bytes_to_read = file_size
                was_truncated = False

            # Open file and read in chunks
            async with sftp.open(remote_path, 'rb') as f:
                chunks = []
                bytes_read = 0

                while bytes_read < bytes_to_read:
                    remaining = bytes_to_read - bytes_read
                    to_read = min(chunk_size, remaining)

                    chunk = await f.read(to_read)
                    if not chunk:
                        break

                    chunks.append(chunk)
                    bytes_read += len(chunk)

                content = b''.join(chunks).decode('utf-8', errors='replace')
                return (content, was_truncated)

    except asyncssh.SFTPError as e:
        raise RuntimeError(f"SFTP error reading {remote_path}: {e}") from e
```

### 5.3 Parallel SFTP Reads (Advanced)

**For maximum performance on large files:**

```python
async def parallel_sftp_read(
    conn: asyncssh.SSHClientConnection,
    remote_path: str,
    max_size: int,
    block_size: int = 262144,  # 256KB blocks (server-optimized)
    max_requests: int = 128,   # Parallel read requests
) -> tuple[str, bool]:
    """Read file with parallel SFTP requests for maximum throughput."""
    try:
        async with conn.start_sftp_client() as sftp:
            attrs = await sftp.stat(remote_path)
            file_size = attrs.size

            if file_size > max_size:
                bytes_to_read = max_size
                was_truncated = True
            else:
                bytes_to_read = file_size
                was_truncated = False

            # Use asyncssh's optimized get() with custom parameters
            local_buffer = io.BytesIO()
            await sftp.get(
                remote_path,
                local_buffer,
                block_size=block_size,
                max_requests=max_requests,
            )

            content = local_buffer.getvalue()[:bytes_to_read]
            return (content.decode('utf-8', errors='replace'), was_truncated)

    except asyncssh.SFTPError as e:
        raise RuntimeError(f"SFTP error: {e}") from e
```

**Performance Notes:**
- Default AsyncSSH settings: 128 parallel requests × 16KB blocks
- Increasing block_size to 256KB can give ~3x speedup
- Server's max block size is auto-detected in newer AsyncSSH versions

**Sources:**
- [AsyncSSH Issue #374](https://github.com/ronf/asyncssh/issues/374)
- [AsyncSSH Issue #725](https://github.com/ronf/asyncssh/issues/725)

### 5.4 Flow Control with drain()

**For writing large amounts of data:**

```python
async def write_large_file_sftp(
    conn: asyncssh.SSHClientConnection,
    remote_path: str,
    data: bytes,
    chunk_size: int = 65536,
):
    """Write large file with proper flow control."""
    async with conn.start_sftp_client() as sftp:
        async with sftp.open(remote_path, 'wb') as f:
            for i in range(0, len(data), chunk_size):
                chunk = data[i:i+chunk_size]
                await f.write(chunk)

                # Yield control if buffer is full
                # AsyncSSH handles this internally, but for custom
                # stream writers, use drain():
                # await writer.drain()
```

**Source:** [Google Groups: AsyncSSH pattern for copying text files](https://groups.google.com/g/asyncssh-users/c/ebA7eUVzuSI)

---

## 6. Production Patterns: Monitoring, Logging, Debugging

### 6.1 Logging Configuration

**Current Implementation:** Good basic logging.

**Enhanced AsyncSSH Debug Logging:**

```python
import logging
import asyncssh

# Configure AsyncSSH logging
asyncssh_logger = logging.getLogger('asyncssh')
asyncssh_logger.setLevel(logging.DEBUG)

# Set AsyncSSH debug level (1-3)
# 1: Minimal logging
# 2: Standard debug (recommended)
# 3: Verbose with raw packets (⚠️ EXPOSES PASSWORDS!)
asyncssh.set_debug_level(2)

# Separate SFTP logging
sftp_logger = logging.getLogger('asyncssh.sftp')
sftp_logger.setLevel(logging.INFO)  # Less verbose for SFTP

# Or use asyncssh.set_sftp_log_level()
asyncssh.set_sftp_log_level(logging.INFO)
```

**Security Warning:** Debug level 3 exposes passwords in clear text. Use only for debugging malformed packets in isolated environments.

**Environment-Based Configuration:**
```python
# In config.py
import os

@dataclass
class Config:
    log_level: str = "INFO"
    asyncssh_debug_level: int = 0  # 0 = disabled, 1-3 = debug levels

    def __post_init__(self):
        # Configure logging
        log_level = os.getenv("SCOUT_LOG_LEVEL", self.log_level)
        logging.basicConfig(level=log_level)

        # Configure AsyncSSH debugging
        debug_level = int(os.getenv("SCOUT_ASYNCSSH_DEBUG", self.asyncssh_debug_level))
        if debug_level > 0:
            asyncssh_logger = logging.getLogger('asyncssh')
            asyncssh_logger.setLevel(logging.DEBUG)
            asyncssh.set_debug_level(debug_level)
            logging.warning("AsyncSSH debug level %d enabled", debug_level)
```

**Sources:**
- [AsyncSSH Logging Module](https://asyncssh.readthedocs.io/en/latest/_modules/asyncssh/logging.html)
- [Google Groups: Logging - how to enable debug logging](https://groups.google.com/g/asyncssh-users/c/tqc_UFHBH2w)

### 6.2 Connection Pool Metrics

**Enhanced pool.py with metrics:**

```python
from dataclasses import dataclass, field
from datetime import datetime
import time

@dataclass
class ConnectionMetrics:
    """Metrics for a pooled connection."""
    created_at: datetime
    last_used: datetime
    use_count: int = 0
    error_count: int = 0
    total_bytes_sent: int = 0
    total_bytes_received: int = 0

class ConnectionPool:
    def __init__(self, idle_timeout: int = 60):
        self.idle_timeout = idle_timeout
        self._connections: dict[str, PooledConnection] = {}
        self._metrics: dict[str, ConnectionMetrics] = {}
        self._lock = asyncio.Lock()

        # Pool-level metrics
        self.total_connections_created = 0
        self.total_connections_closed = 0
        self.total_connection_errors = 0

    async def get_connection(self, host: "SSHHost") -> asyncssh.SSHClientConnection:
        async with self._lock:
            pooled = self._connections.get(host.name)

            if pooled and not pooled.is_stale:
                # Update metrics
                self._metrics[host.name].last_used = datetime.now()
                self._metrics[host.name].use_count += 1
                pooled.touch()
                return pooled.connection

            # Create new connection
            try:
                conn = await asyncssh.connect(...)

                self._connections[host.name] = PooledConnection(connection=conn)
                self._metrics[host.name] = ConnectionMetrics(
                    created_at=datetime.now(),
                    last_used=datetime.now(),
                    use_count=1,
                )
                self.total_connections_created += 1

                return conn

            except Exception as e:
                self.total_connection_errors += 1
                raise

    def get_pool_stats(self) -> dict:
        """Get current pool statistics."""
        return {
            "active_connections": len(self._connections),
            "total_created": self.total_connections_created,
            "total_closed": self.total_connections_closed,
            "total_errors": self.total_connection_errors,
            "hosts": [
                {
                    "name": name,
                    "created_at": metrics.created_at.isoformat(),
                    "last_used": metrics.last_used.isoformat(),
                    "use_count": metrics.use_count,
                    "error_count": metrics.error_count,
                }
                for name, metrics in self._metrics.items()
            ]
        }
```

**Expose metrics via MCP resource:**
```python
# In resources/
@mcp.resource("scout://pool/stats")
async def pool_stats_resource() -> str:
    """Expose connection pool statistics."""
    pool = get_pool()
    stats = pool.get_pool_stats()
    import json
    return json.dumps(stats, indent=2)
```

### 6.3 Health Checks

**Enhanced health endpoint with pool status:**

```python
# In server.py or main HTTP handler
from fastapi import FastAPI
from scout_mcp.services import get_pool

app = FastAPI()

@app.get("/health")
async def health_check():
    """Health check with pool status."""
    pool = get_pool()
    stats = pool.get_pool_stats()

    # Check if pool is healthy
    is_healthy = (
        stats["active_connections"] < 100 and  # Not overloaded
        stats["total_errors"] < stats["total_created"] * 0.1  # < 10% error rate
    )

    return {
        "status": "healthy" if is_healthy else "degraded",
        "pool": stats,
    }

@app.get("/health/ready")
async def readiness_check():
    """Kubernetes readiness check."""
    pool = get_pool()
    return {
        "ready": pool.pool_size >= 0,  # Pool initialized
    }
```

### 6.4 Structured Logging with Context

**Enhanced logging with request context:**

```python
import contextvars
import logging
from uuid import uuid4

# Context variable for request ID
request_id_var = contextvars.ContextVar('request_id', default=None)

class ContextFilter(logging.Filter):
    """Add request context to log records."""

    def filter(self, record):
        request_id = request_id_var.get()
        record.request_id = request_id if request_id else "-"
        return True

# Configure logger
logger = logging.getLogger(__name__)
logger.addFilter(ContextFilter())

# Format with context
logging.basicConfig(
    format='%(asctime)s [%(request_id)s] %(name)s %(levelname)s: %(message)s',
    level=logging.INFO
)

# In tool/resource handlers
async def scout_tool(target: str, command: str | None = None):
    """Scout tool with request context."""
    request_id = str(uuid4())[:8]
    request_id_var.set(request_id)

    logger.info("Scout request: target=%s, command=%s", target, command)
    # ... rest of implementation
```

---

## 7. Testing Patterns

### 7.1 Mocking AsyncSSH Connections

**Current Scout MCP approach:** Uses real SSH in integration tests.

**Unit testing with mocks:**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
import asyncssh

@pytest.fixture
def mock_ssh_connection():
    """Mock SSH connection for unit tests."""
    conn = AsyncMock(spec=asyncssh.SSHClientConnection)

    # Mock run() method
    async def mock_run(cmd, check=False):
        result = MagicMock()
        result.returncode = 0
        result.stdout = "mock output"
        result.stderr = ""
        return result

    conn.run = mock_run
    conn.close = MagicMock()
    return conn

@pytest.mark.asyncio
async def test_cat_file(mock_ssh_connection):
    """Test cat_file with mocked connection."""
    from scout_mcp.services.executors import cat_file

    content, truncated = await cat_file(mock_ssh_connection, "/test/file", 1024)

    assert content == "mock output"
    assert truncated is False
```

### 7.2 Integration Testing with Local SSH Server

**AsyncSSH provides built-in test server:**

```python
import pytest
import asyncssh
from pathlib import Path

@pytest.fixture
async def ssh_server():
    """Start local SSH server for testing."""
    import tempfile

    # Generate temporary host key
    with tempfile.TemporaryDirectory() as tmpdir:
        host_key = Path(tmpdir) / "host_key"
        asyncssh.generate_private_key('ssh-rsa').write_private_key(str(host_key))

        # Start server
        server = await asyncssh.create_server(
            lambda: asyncssh.SSHServer(),
            '',
            0,  # Random port
            server_host_keys=[str(host_key)],
            allow_pty=True,
        )

        port = server.sockets[0].getsockname()[1]

        yield ('localhost', port, str(host_key))

        server.close()
        await server.wait_closed()

@pytest.mark.asyncio
async def test_connection_pool_with_server(ssh_server):
    """Test connection pool against real SSH server."""
    host, port, host_key = ssh_server

    # Test connection pool
    from scout_mcp.services import ConnectionPool
    from scout_mcp.models import SSHHost

    pool = ConnectionPool(idle_timeout=30)
    ssh_host = SSHHost(
        name="test-server",
        hostname=host,
        port=port,
        user="testuser"
    )

    conn = await pool.get_connection(ssh_host)
    assert conn is not None

    # Test reuse
    conn2 = await pool.get_connection(ssh_host)
    assert conn is conn2  # Same connection reused

    await pool.close_all()
```

---

## 8. Specific Recommendations for Scout MCP

### 8.1 Immediate Improvements (High Priority)

1. **Add connection timeout configuration:**
   ```python
   # In pool.py get_connection()
   conn = await asyncssh.connect(
       host.hostname,
       port=host.port,
       username=host.user,
       known_hosts=None,  # TODO: Enable in separate PR
       client_keys=client_keys,
       connect_timeout=30,      # ✅ ADD
       login_timeout=30,        # ✅ ADD
       keepalive_interval=60,   # ✅ ADD
       keepalive_count_max=3,   # ✅ ADD
   )
   ```

2. **Enhance graceful shutdown:**
   ```python
   # In pool.py close_all()
   # Add wait_closed() for each connection
   close_tasks = [conn.wait_closed() for conn in connections]
   await asyncio.gather(*close_tasks, return_exceptions=True)
   ```

3. **Add connection validation:**
   ```python
   # Implement _validate_connection() method
   # Use before returning pooled connections
   ```

### 8.2 Medium Priority Improvements

4. **Enable host key verification (security):**
   ```python
   # Add config option
   verify_host_keys: bool = True

   # Update connection logic
   known_hosts_arg = {} if config.verify_host_keys else {"known_hosts": None}
   ```

5. **Add AsyncSSH debug logging:**
   ```python
   # In config.py __post_init__
   asyncssh_debug = int(os.getenv("SCOUT_ASYNCSSH_DEBUG", "0"))
   if asyncssh_debug > 0:
       asyncssh.set_debug_level(asyncssh_debug)
   ```

6. **Implement session semaphore:**
   ```python
   # In pool.py
   # Add execute_on_host() method with semaphore
   # Protects against MaxSessions limit
   ```

### 8.3 Future Enhancements (Low Priority)

7. **SFTP streaming for large files:**
   - Replace `head -c` with SFTP for files > 1MB
   - Implement chunked reading
   - Better performance and memory usage

8. **Connection pool metrics:**
   - Track connection usage statistics
   - Expose via MCP resource
   - Enable monitoring/debugging

9. **Retry with exponential backoff:**
   - Replace simple one-retry with backoff strategy
   - Configurable max retries

10. **Connection validation before use:**
    - Ping connection with quick no-op command
    - Detect stale connections more reliably

---

## 9. Quick Reference

### AsyncSSH Connection Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `known_hosts` | `~/.ssh/known_hosts` | Host key verification |
| `client_keys` | Agent + default paths | Authentication keys |
| `connect_timeout` | None | TCP + handshake timeout (2.8.1+) |
| `login_timeout` | None | Authentication timeout |
| `keepalive_interval` | None | Keepalive frequency (seconds) |
| `keepalive_count_max` | 3 | Failed keepalives before disconnect |
| `server_host_key_algs` | Matched | Host key algorithms to advertise |
| `preferred_auth` | All | Authentication methods preference |

### Common AsyncSSH Methods

| Method | Purpose |
|--------|---------|
| `conn.run(cmd)` | Execute command, return result |
| `conn.create_process()` | Get streaming process (stdin/stdout/stderr) |
| `conn.start_sftp_client()` | Open SFTP session |
| `conn.close()` | Close connection |
| `conn.wait_closed()` | Wait for connection cleanup |

### AsyncSSH Exceptions

| Exception | Meaning |
|-----------|---------|
| `DisconnectError` | Clean SSH disconnect |
| `ConnectionLost` | Unexpected connection loss |
| `ChannelOpenError` | Failed to open SSH channel |
| `PermissionDenied` | Authentication failed |
| `TimeoutError` | Operation timeout |
| `SFTPError` | SFTP operation failed |

---

## 10. Sources & Further Reading

### Official Documentation
- [AsyncSSH Documentation](https://asyncssh.readthedocs.io/)
- [AsyncSSH API Reference](https://asyncssh.readthedocs.io/en/latest/api.html)
- [AsyncSSH Change Log](https://asyncssh.readthedocs.io/en/latest/changes.html)
- [AsyncSSH GitHub Repository](https://github.com/ronf/asyncssh)

### Key GitHub Issues & Discussions
- [Issue #172: How do I create a ssh connection pool?](https://github.com/ronf/asyncssh/issues/172)
- [Issue #456: Problem with >10 parallel SSH connections](https://github.com/ronf/asyncssh/issues/456)
- [Discussion #409: How to change connection timeout interval?](https://github.com/ronf/asyncssh/discussions/409)
- [Issue #179: Add option to disable strict host key checking](https://github.com/ronf/asyncssh/issues/179)
- [Issue #374: How to do faster transfers for a single big file through SFTP](https://github.com/ronf/asyncssh/issues/374)
- [Issue #565: Reuse session for multiple commands](https://github.com/ronf/asyncssh/issues/565)

### Community Resources
- [A Tale of Five Python SSH Libraries](https://elegantnetwork.github.io/posts/comparing-ssh/) - Performance comparison
- [AsyncSSH Examples Directory](https://github.com/ronf/asyncssh/tree/master/examples) - Official examples
- [AsyncSSH Google Group](https://groups.google.com/g/asyncssh-users) - Community support

### Stack Overflow Questions
- [Can not connect via AsyncSSH, error Host key is not trusted](https://stackoverflow.com/questions/67222941/can-not-connect-via-asyncssh-error-host-key-is-not-trusted)
- [Use connection pooling with python sshfs](https://stackoverflow.com/questions/75562085/use-connection-pooling-with-python-sshfs-fsspec-in-python)

---

## Appendix: Complete Example Implementation

### Enhanced ConnectionPool with All Best Practices

```python
"""Production-ready SSH connection pool with all best practices."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Callable
from dataclasses import dataclass

import asyncssh

from scout_mcp.models import PooledConnection

if TYPE_CHECKING:
    from scout_mcp.models import SSHHost

logger = logging.getLogger(__name__)


@dataclass
class ConnectionMetrics:
    """Metrics for monitoring connection health."""
    created_at: datetime
    last_used: datetime
    use_count: int = 0
    error_count: int = 0


class EnhancedConnectionPool:
    """Production-ready SSH connection pool.

    Features:
    - Connection timeout and keepalive
    - Session limit enforcement via semaphore
    - Comprehensive error handling
    - Connection validation
    - Metrics collection
    - Graceful shutdown
    """

    def __init__(
        self,
        idle_timeout: int = 60,
        connect_timeout: int = 30,
        keepalive_interval: int = 60,
        max_sessions_per_host: int = 8,
        verify_host_keys: bool = False,  # TODO: Enable in production
    ) -> None:
        """Initialize enhanced connection pool.

        Args:
            idle_timeout: Seconds before closing idle connection.
            connect_timeout: Timeout for connection establishment.
            keepalive_interval: Seconds between keepalive messages.
            max_sessions_per_host: Max concurrent sessions per connection.
            verify_host_keys: Enable host key verification (recommended).
        """
        self.idle_timeout = idle_timeout
        self.connect_timeout = connect_timeout
        self.keepalive_interval = keepalive_interval
        self.max_sessions_per_host = max_sessions_per_host
        self.verify_host_keys = verify_host_keys

        self._connections: dict[str, PooledConnection] = {}
        self._metrics: dict[str, ConnectionMetrics] = {}
        self._session_semaphores: dict[str, asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task[Any] | None = None

        # Pool-level metrics
        self.total_connections_created = 0
        self.total_connections_closed = 0
        self.total_connection_errors = 0

        if not verify_host_keys:
            logger.warning("⚠️  Host key verification DISABLED - insecure!")

    async def _validate_connection(
        self,
        conn: asyncssh.SSHClientConnection
    ) -> bool:
        """Test if connection is still alive.

        Args:
            conn: Connection to validate.

        Returns:
            True if connection is alive, False otherwise.
        """
        try:
            result = await asyncio.wait_for(
                conn.run('true', check=False),
                timeout=2
            )
            return result.returncode == 0
        except (asyncssh.Error, asyncio.TimeoutError):
            return False

    async def get_connection(
        self,
        host: "SSHHost"
    ) -> asyncssh.SSHClientConnection:
        """Get or create a connection to the host.

        Args:
            host: SSH host configuration.

        Returns:
            Active SSH connection.

        Raises:
            RuntimeError: If connection fails.
        """
        async with self._lock:
            pooled = self._connections.get(host.name)

            # Validate existing connection
            if pooled and not pooled.is_stale:
                if await self._validate_connection(pooled.connection):
                    pooled.touch()
                    self._metrics[host.name].last_used = datetime.now()
                    self._metrics[host.name].use_count += 1
                    logger.debug(
                        "Reusing validated connection to %s (pool_size=%d)",
                        host.name,
                        len(self._connections),
                    )
                    return pooled.connection
                else:
                    logger.info(
                        "Connection to %s failed validation, reconnecting",
                        host.name
                    )
                    pooled.connection.close()
                    del self._connections[host.name]

            # Create new connection
            try:
                logger.info(
                    "Opening SSH connection to %s (%s@%s:%d)",
                    host.name,
                    host.user,
                    host.hostname,
                    host.port,
                )

                client_keys = [host.identity_file] if host.identity_file else None
                known_hosts_arg = {} if self.verify_host_keys else {"known_hosts": None}

                conn = await asyncssh.connect(
                    host.hostname,
                    port=host.port,
                    username=host.user,
                    client_keys=client_keys,
                    connect_timeout=self.connect_timeout,
                    login_timeout=self.connect_timeout,
                    keepalive_interval=self.keepalive_interval,
                    keepalive_count_max=3,
                    **known_hosts_arg,
                )

                self._connections[host.name] = PooledConnection(connection=conn)
                self._metrics[host.name] = ConnectionMetrics(
                    created_at=datetime.now(),
                    last_used=datetime.now(),
                    use_count=1,
                )
                self.total_connections_created += 1

                logger.info(
                    "SSH connection established to %s (pool_size=%d)",
                    host.name,
                    len(self._connections),
                )

                # Start cleanup task if not running
                if self._cleanup_task is None or self._cleanup_task.done():
                    self._cleanup_task = asyncio.create_task(self._cleanup_loop())

                return conn

            except Exception as e:
                self.total_connection_errors += 1
                logger.error("Failed to connect to %s: %s", host.name, e)
                raise RuntimeError(f"SSH connection failed: {e}") from e

    async def execute_on_host(
        self,
        host: "SSHHost",
        operation: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute operation on host with session limit enforcement.

        Args:
            host: Target SSH host.
            operation: Async callable to execute with connection.
            *args: Positional arguments for operation.
            **kwargs: Keyword arguments for operation.

        Returns:
            Result from operation.
        """
        # Get or create semaphore for this host
        if host.name not in self._session_semaphores:
            self._session_semaphores[host.name] = asyncio.Semaphore(
                self.max_sessions_per_host
            )

        sem = self._session_semaphores[host.name]

        # Acquire session slot
        async with sem:
            try:
                conn = await self.get_connection(host)
                return await operation(conn, *args, **kwargs)
            except Exception as e:
                # Track errors in metrics
                if host.name in self._metrics:
                    self._metrics[host.name].error_count += 1
                raise

    async def _cleanup_loop(self) -> None:
        """Periodically clean up idle connections."""
        logger.debug("Cleanup loop started (interval=%ds)", self.idle_timeout // 2)

        while True:
            await asyncio.sleep(self.idle_timeout // 2)
            await self._cleanup_idle()

            # Stop if no connections left
            if not self._connections:
                logger.debug("Cleanup loop stopped - no connections remaining")
                break

    async def _cleanup_idle(self) -> None:
        """Close connections that have been idle too long."""
        async with self._lock:
            cutoff = datetime.now() - timedelta(seconds=self.idle_timeout)
            to_remove = []

            for name, pooled in self._connections.items():
                if pooled.last_used < cutoff or pooled.is_stale:
                    reason = "stale" if pooled.is_stale else "idle"
                    logger.info(
                        "Closing %s connection to %s (pool_size=%d)",
                        reason,
                        name,
                        len(self._connections) - 1,
                    )
                    pooled.connection.close()
                    to_remove.append(name)

            for name in to_remove:
                del self._connections[name]
                self.total_connections_closed += 1

            if to_remove:
                logger.debug(
                    "Cleanup complete: removed %d connection(s), %d remaining",
                    len(to_remove),
                    len(self._connections),
                )

    async def close_all(self) -> None:
        """Close all connections gracefully."""
        async with self._lock:
            count = len(self._connections)
            if count > 0:
                logger.info("Shutting down connection pool (%d connections)", count)

                # Close all connections and wait for cleanup
                close_tasks = []
                for name, pooled in self._connections.items():
                    logger.debug("Closing connection to %s", name)
                    pooled.connection.close()
                    close_tasks.append(pooled.connection.wait_closed())

                # Wait for all connections to close (with timeout)
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*close_tasks, return_exceptions=True),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("Connection cleanup timed out")

                self._connections.clear()
                self.total_connections_closed += count

            # Cancel cleanup task
            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
                logger.debug("Cleanup task cancelled")

    async def remove_connection(self, host_name: str) -> None:
        """Remove a specific connection from the pool.

        Args:
            host_name: Name of the host to remove.
        """
        async with self._lock:
            if host_name in self._connections:
                logger.info(
                    "Removing connection to %s (pool_size=%d)",
                    host_name,
                    len(self._connections) - 1,
                )
                pooled = self._connections[host_name]
                pooled.connection.close()
                await pooled.connection.wait_closed()
                del self._connections[host_name]
                self.total_connections_closed += 1

    def get_pool_stats(self) -> dict:
        """Get current pool statistics.

        Returns:
            Dictionary with pool metrics.
        """
        return {
            "active_connections": len(self._connections),
            "total_created": self.total_connections_created,
            "total_closed": self.total_connections_closed,
            "total_errors": self.total_connection_errors,
            "error_rate": (
                self.total_connection_errors / self.total_connections_created
                if self.total_connections_created > 0 else 0.0
            ),
            "hosts": [
                {
                    "name": name,
                    "created_at": metrics.created_at.isoformat(),
                    "last_used": metrics.last_used.isoformat(),
                    "use_count": metrics.use_count,
                    "error_count": metrics.error_count,
                    "uptime_seconds": (
                        datetime.now() - metrics.created_at
                    ).total_seconds(),
                }
                for name, metrics in self._metrics.items()
                if name in self._connections
            ]
        }

    @property
    def pool_size(self) -> int:
        """Return the current number of connections in the pool."""
        return len(self._connections)

    @property
    def active_hosts(self) -> list[str]:
        """Return list of hosts with active connections."""
        return list(self._connections.keys())
```

---

**End of Report**

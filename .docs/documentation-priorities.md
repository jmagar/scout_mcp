# Scout MCP Documentation Priorities - Quick Reference
**Date:** December 7, 2025
**Status:** Action Required

---

## CRITICAL - Do This Week ⚠️

### 1. Fix File Permissions (30 minutes)
**Issue:** CLAUDE.md and 11 Python files have 600 permissions (root-owned)
**Impact:** Cannot read documentation, blocks audit completion
**Action:**
```bash
chmod 644 /mnt/cache/code/scout_mcp/CLAUDE.md
find /mnt/cache/code/scout_mcp -name "*.py" -perm 600 -exec chmod 644 {} \;
```

### 2. Create .docs/deployment-log.md (1 hour)
**Issue:** Missing required standards file
**Impact:** Violates CLAUDE.md standards, no deployment history
**Template:**
```markdown
# Deployment Log

## 2025-12-07

### 14:23:15 | Deploy scout_mcp v0.1.0
**Service:** scout_mcp
**Port:** 8000
**Status:** Success
**Notes:** Initial deployment with HTTP transport
```

### 3. Create .docs/services-ports.md (1 hour)
**Issue:** Missing required standards file
**Impact:** Violates CLAUDE.md standards, no port registry
**Template:**
```markdown
# Services & Ports Registry

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| scout_mcp | 8000 | HTTP | MCP server (default) |
| scout_mcp | 53000+ | HTTP | MCP server (recommended, high ports) |
```

### 4. Update README Security Warnings (2 hours)
**Issue:** Security section doesn't reflect CRITICAL audit findings
**Impact:** Users unaware of SEC-001, SEC-002 critical risks
**Action:**
- Add CRITICAL warning box at top
- Update checklist to mark auth as REQUIRED (not optional)
- Add link to security audit report
- Update default binding warning (0.0.0.0 is dangerous)

### 5. Create DEPLOYMENT.md (1 day)
**Issue:** No production deployment guide
**Impact:** Cannot deploy safely to production
**Sections:**
- Prerequisites
- Docker deployment
- systemd service
- Reverse proxy config
- Security hardening
- Verification steps

### 6. Create docker-compose.yaml (4 hours)
**Issue:** No deployment automation
**Impact:** Inconsistent deployments, hard to reproduce
**Requirements:**
- Secure defaults (auth required, localhost binding)
- Environment variable configuration
- Health checks
- Logging configuration
- Volume mounts

**Total Effort:** 2-3 days

---

## HIGH PRIORITY - Do Next Week 📋

### 7. Create Architecture Decision Records (2 days)
**Issue:** No rationale for design decisions
**Impact:** Cannot understand why choices were made
**Create 7 ADRs:**
1. `docs/adr/001-global-singletons.md`
2. `docs/adr/002-lru-connection-pool.md`
3. `docs/adr/003-http-transport-default.md`
4. `docs/adr/004-optional-authentication.md` (DEPRECATED)
5. `docs/adr/005-no-resource-auth.md`
6. `docs/adr/006-middleware-stack.md`
7. `docs/adr/007-no-output-limits.md` (TEMPORARY)

### 8. Create ARCHITECTURE.md (1 day)
**Issue:** No system overview documentation
**Impact:** Hard to understand system design
**Sections:**
- System overview diagram
- Component architecture
- Deployment architecture
- Security architecture
- Performance characteristics
- Data flow diagrams

### 9. Create OPERATIONS.md (1 day)
**Issue:** No operational documentation
**Impact:** Cannot troubleshoot production issues
**Sections:**
- Monitoring setup
- Logging configuration
- Alerting thresholds
- Health check integration
- Backup/restore
- Upgrade procedures

### 10. Update SECURITY.md (4 hours)
**Issue:** Doesn't reflect security audit findings
**Impact:** Users unaware of vulnerabilities
**Action:**
- Add "Known Vulnerabilities" section with CVSS scores
- Update threat model
- Add SEC-001 through SEC-007 findings
- Link to full audit report

### 11. Create Runbooks (2 days)
**Issue:** No incident response procedures
**Impact:** Cannot respond to production issues
**Create 5 runbooks:**
1. `docs/runbooks/server-wont-start.md`
2. `docs/runbooks/connection-refused.md`
3. `docs/runbooks/rate-limit-exceeded.md`
4. `docs/runbooks/high-memory-usage.md`
5. `docs/runbooks/slow-requests.md`

### 12. Add Known Issues to README (2 hours)
**Issue:** No "Known Issues" section
**Impact:** Users unaware of limitations
**Document:**
- P0-4: No output size limits (production blocker)
- P1-1: No SSH connection timeout
- SEC-001: Auth disabled by default (CVSS 9.1)
- SEC-002: Binds to 0.0.0.0 (CVSS 8.6)
- Link to full audit reports

**Total Effort:** 1 week

---

## MEDIUM PRIORITY - Do This Month 📅

### 13. Create API.md (1 day)
**Issue:** No complete API reference
**Impact:** Limited API discovery
**Sections:**
- Complete endpoint reference
- Request/response schemas
- Error codes and messages
- Authentication headers
- Rate limit headers
- Examples for all operations

### 14. Create CONTRIBUTING.md (4 hours)
**Issue:** No contribution guidelines
**Impact:** Contributors don't know process
**Sections:**
- Code style guide
- PR process
- Testing requirements
- Documentation standards
- Review criteria

### 15. Create CHANGELOG.md (4 hours)
**Issue:** No version history
**Impact:** Cannot track changes
**Format:** Keep-a-changelog
**Backfill:** Recent changes from session logs

### 16. Create examples/ Directory (1 day)
**Issue:** Limited usage examples
**Impact:** Users need more examples
**Create:**
- `examples/basic-usage.py`
- `examples/advanced-features.py`
- `examples/docker-deployment/`
- `examples/monitoring-setup/`

### 17. Expand Troubleshooting (4 hours)
**Issue:** FAQ section insufficient
**Impact:** Common errors not documented
**Add:**
- Permission denied (SSH keys)
- Connection refused (port conflicts)
- Unknown host (SSH config)
- Rate limit exceeded
- High memory usage

**Total Effort:** 1 week

---

## Standards Compliance Checklist

### Required by CLAUDE.md Standards

- [ ] `.docs/deployment-log.md` - **MISSING** ❌
- [ ] `.docs/services-ports.md` - **MISSING** ❌
- [x] `.docs/sessions/` - **EXISTS** ✅ (12 logs)
- [ ] `README.md` - **INCOMPLETE** ⚠️ (missing sections)
- [ ] `CLAUDE.md` - **PERMISSION DENIED** ❌ (600, root-owned)
- [ ] Module `CLAUDE.md` files - **EXCELLENT** ✅ (8/8)
- [ ] Architecture Decision Records - **MISSING** ❌
- [ ] Deployment guide - **MISSING** ❌
- [ ] Operational runbooks - **MISSING** ❌

**Compliance:** 33% (1/3 core requirements met)
**Target:** 100%

---

## Documentation Gaps by Severity

### CRITICAL (Cannot ship to production without these)

1. **Security warnings outdated** - Users unaware of SEC-001, SEC-002
2. **No deployment guide** - Cannot deploy safely
3. **No operational runbooks** - Cannot troubleshoot
4. **Standards violations** - Missing deployment-log.md, services-ports.md
5. **File permissions** - Cannot access documentation

### HIGH (Significant impact, should have)

6. **No ADRs** - Cannot understand design rationale
7. **No ARCHITECTURE.md** - Hard to onboard new developers
8. **No API reference** - Limited API discovery
9. **No known issues section** - Users hit undocumented limits
10. **Performance undocumented** - No capacity planning

### MEDIUM (Nice to have, improves experience)

11. **No CONTRIBUTING.md** - Contributors confused
12. **No CHANGELOG.md** - Cannot track changes
13. **Limited examples** - Users need more guidance
14. **Troubleshooting insufficient** - Common errors not covered

---

## Quick Wins (High Impact, Low Effort)

### 1. Fix File Permissions (30 min, huge impact)
```bash
chmod 644 /mnt/cache/code/scout_mcp/CLAUDE.md
find /mnt/cache/code/scout_mcp -name "*.py" -perm 600 -exec chmod 644 {} \;
```

### 2. Create Standards Files (2 hours, high compliance)
```bash
touch .docs/deployment-log.md
touch .docs/services-ports.md
# Fill in templates from audit report
```

### 3. Add Security Warning to README (1 hour, critical)
```markdown
> **CRITICAL SECURITY WARNING**
>
> Scout MCP has authentication DISABLED by default. This is a CRITICAL
> security risk (CVSS 9.1). See SECURITY.md for details.
>
> **REQUIRED for production:**
> - Set SCOUT_API_KEYS (enable authentication)
> - Set SCOUT_HTTP_HOST=127.0.0.1 (bind to localhost)
> - Set SCOUT_RATE_LIMIT_PER_MINUTE=60 (enable rate limiting)
```

### 4. Add Known Issues to README (1 hour, improves UX)
```markdown
## Known Issues

- **No output size limits** (P0-4) - Large outputs can cause memory issues
- **Auth disabled by default** (SEC-001) - CVSS 9.1 critical
- See [security audit](.docs/security-audit-2025-12-07.md) for details
```

### 5. Create docker-compose.yaml (4 hours, easy deployment)
```yaml
services:
  scout_mcp:
    build: .
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      - SCOUT_API_KEYS=${SCOUT_API_KEYS:?API key required}
      - SCOUT_HTTP_HOST=0.0.0.0
      - SCOUT_RATE_LIMIT_PER_MINUTE=60
```

**Total Quick Wins Effort:** 1 day
**Total Impact:** Massive (compliance + security)

---

## Documentation Review Checklist

Use this checklist when reviewing documentation PRs:

### Content
- [ ] Accurate (matches implementation)
- [ ] Complete (no critical omissions)
- [ ] Clear (easy to understand)
- [ ] Examples provided
- [ ] Error cases documented

### Consistency
- [ ] Consistent with other docs
- [ ] Consistent terminology
- [ ] Matches code audit findings
- [ ] Version-specific (if applicable)

### Standards
- [ ] Follows project style guide
- [ ] Proper markdown formatting
- [ ] Links work
- [ ] Code blocks syntax highlighted
- [ ] Tables formatted correctly

### Security
- [ ] Security warnings present
- [ ] No secrets exposed
- [ ] Secure defaults shown
- [ ] Threat model accurate

---

## Next Actions

1. **This Week (P0):**
   - Fix file permissions
   - Create standards files
   - Update security warnings
   - Create DEPLOYMENT.md
   - Create docker-compose.yaml

2. **Next Week (P1):**
   - Create 7 ADRs
   - Create ARCHITECTURE.md
   - Create OPERATIONS.md
   - Create runbooks
   - Update SECURITY.md

3. **This Month (P2):**
   - Create API.md
   - Create CONTRIBUTING.md
   - Create CHANGELOG.md
   - Create examples/
   - Expand troubleshooting

4. **Ongoing:**
   - Keep session logs updated
   - Update deployment log
   - Review docs with each PR
   - Quarterly documentation audit

---

**For detailed analysis:** See `.docs/documentation-audit-2025-12-07.md` (16 sections)
**For quick summary:** See `.docs/documentation-audit-summary.md`
**For this quick ref:** Keep handy during documentation work

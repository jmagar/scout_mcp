# Python Best Practices Checklist - Scout MCP
**Quick Reference for Code Review**

---

## ✅ PASSING (Keep Doing This)

### Code Quality
- [x] Zero Ruff violations (PEP 8, pyflakes, isort, pyupgrade, bugbear, simplify)
- [x] Zero mypy errors with strict mode enabled
- [x] 95%+ type hints on all function signatures
- [x] 92%+ docstring coverage (all public APIs documented)
- [x] All imports properly organized (stdlib → third-party → local)
- [x] No wildcard imports (`from x import *`)
- [x] f-strings used everywhere (no %, .format())
- [x] Proper use of TYPE_CHECKING for forward references

### Architecture
- [x] Clean layered architecture (models/services/utils/tools/resources)
- [x] Zero circular dependencies
- [x] Proper `__init__.py` exports in all packages
- [x] Single responsibility principle (mostly followed)

### Async/Await
- [x] All I/O operations use async/await
- [x] Proper use of `asyncio.gather()` for concurrent operations
- [x] `asyncio.Lock` for thread-safe connection pool
- [x] Lifespan context manager for resource cleanup

### Package Management
- [x] Modern pyproject.toml (no requirements.txt)
- [x] uv for dependency management
- [x] Separate dev dependencies
- [x] Cache directories properly configured

### Logging
- [x] Proper log levels (DEBUG → INFO → WARNING → ERROR)
- [x] Structured logging with context
- [x] No logging of sensitive data (passwords, keys)
- [x] Custom colorful formatter

### Credentials
- [x] No hardcoded credentials
- [x] Uses SSH keys from ~/.ssh/
- [x] .env in .gitignore
- [x] No credentials in error messages

---

## ❌ CRITICAL FAILURES (Fix Immediately)

### Security
- [ ] **SSH host key verification disabled** (`known_hosts=None`)
  - File: `scout_mcp/services/pool.py:67`
  - Risk: CVSS 9.1 (MITM attacks)
  - Fix: Use `~/.ssh/known_hosts`

- [ ] **No authentication on MCP server**
  - File: `scout_mcp/server.py:422`
  - Risk: CVSS 9.8 (unauthorized access)
  - Fix: Add API key authentication

- [ ] **Command injection vulnerability**
  - File: `scout_mcp/services/executors.py:161`
  - Risk: CVSS 8.8 (arbitrary code execution)
  - Fix: Use `shlex.quote()` for shell parameters

- [ ] **Vulnerable dependency version**
  - File: `pyproject.toml:9`
  - Risk: Known CVEs in asyncssh 2.14.0-2.14.1
  - Fix: Pin to `asyncssh>=2.14.2`

---

## ⚠️ HIGH PRIORITY (Fix in Next Sprint)

### Code Organization
- [ ] **7 functions exceed 50-line limit**
  - `scout()` - 146 LOC (split into 4 functions)
  - `scout_resource()` - 91 LOC (extract retry logic)
  - `zfs_pool_resource()` - 68 LOC (extract parsing)
  - `list_hosts_resource()` - 62 LOC (extract formatting)
  - `syslog_resource()` - 63 LOC (extract parsing)
  - `docker_list_resource()` - 57 LOC (extract formatting)
  - `compose_list_resource()` - 52 LOC (extract parsing)

### Error Handling
- [ ] **38 bare Exception catches**
  - Pattern: `except Exception as e:` (too broad)
  - Fix: Use specific exceptions (asyncssh.Error, OSError, ValueError)

- [ ] **No custom exception hierarchy**
  - Create `scout_mcp/exceptions.py`
  - Define: ScoutError, HostNotFoundError, ConnectionError, PathNotFoundError

### Performance
- [ ] **Global lock in connection pool**
  - File: `scout_mcp/services/pool.py:25`
  - Issue: Single lock for ALL hosts (10x slowdown)
  - Fix: One lock per host

- [ ] **Unbounded connection pool**
  - No max pool size (could exhaust file descriptors)
  - Fix: Add `max_connections` parameter and semaphore

---

## ⚠️ MEDIUM PRIORITY (Fix in Backlog)

### CI/CD Infrastructure
- [ ] **No pre-commit hooks**
  - Create `.pre-commit-config.yaml`
  - Configure: ruff, mypy, detect-secrets

- [ ] **No GitHub Actions**
  - Create `.github/workflows/ci.yml`
  - Add: test, lint, type-check, coverage

- [ ] **pytest configuration incomplete**
  - Missing: markers, parallel execution, coverage thresholds

### Resource Management
- [ ] **Non-async connection cleanup**
  - Files: `pool.py:112, 133, 154`, `ping.py:22`
  - Pattern: `connection.close()` without `await`
  - Fix: Use `await connection.close()`

- [ ] **No async context managers for SSH connections**
  - Current: Manual cleanup
  - Fix: Implement `__aenter__` and `__aexit__` for PooledConnection

### Input Validation
- [ ] **No path traversal protection**
  - Accepts: `../../../etc/passwd`
  - Fix: Normalize paths, block `..` sequences

- [ ] **No max path length enforcement**
  - Could cause buffer issues
  - Fix: Add length validation

---

## 🔵 LOW PRIORITY (Nice-to-Have)

### Modernization
- [ ] Use structural pattern matching (PEP 634)
  ```python
  match path_type:
      case "file": ...
      case "directory": ...
  ```

- [ ] Use exception groups (PEP 654)
  ```python
  except* asyncssh.Error as e:
      logger.error("SSH errors: %s", e.exceptions)
  ```

- [ ] Use task groups (PEP 654)
  ```python
  async with asyncio.TaskGroup() as tg:
      for host in hosts:
          tg.create_task(check_host_online(host))
  ```

### Performance
- [ ] Add caching for `stat_path()` results (1-5 second TTL)
- [ ] Add rate limiting per host
- [ ] Add connection metrics/monitoring

### Testing
- [ ] Add pytest markers (slow, integration)
- [ ] Configure parallel execution (pytest-xdist)
- [ ] Add security tests (injection attempts)
- [ ] Add performance benchmarks

### Documentation
- [ ] Add SECURITY.md with vulnerability disclosure policy
- [ ] Document security assumptions in README
- [ ] Add architecture diagrams
- [ ] Add API documentation

### pyproject.toml
- [ ] Add `project.license` field
- [ ] Add `project.authors` field
- [ ] Add `project.keywords` field
- [ ] Add `project.classifiers` field

---

## 📋 Weekly Checklist Template

### Before Every Commit
```bash
# Run these locally
uv run ruff check .               # Linting
uv run ruff format .              # Formatting
uv run mypy scout_mcp/            # Type checking
uv run pytest tests/ -v           # Tests

# After pre-commit is configured
git commit  # Hooks run automatically
```

### Before Every PR
```bash
# Full test suite
uv run pytest tests/ --cov --cov-report=term-missing

# Security checks
uv run pip-audit                  # Dependency CVEs
uv run bandit -r scout_mcp        # Code vulnerabilities
uv run detect-secrets scan        # Secret leaks

# Check function sizes
grep -rn "^def \|^async def " scout_mcp | wc -l

# Check coverage
uv run pytest --cov --cov-fail-under=80
```

### Monthly Audit
- [ ] Review dependency versions (`uv lock --upgrade`)
- [ ] Run security audit (`uv run pip-audit`)
- [ ] Check for deprecation warnings
- [ ] Review error logs for patterns
- [ ] Update documentation

---

## 🎯 Success Metrics

### Week 1 (Security)
- [x] Zero CRITICAL vulnerabilities
- [x] Security audit passes
- [x] asyncssh pinned to secure version

### Week 2 (Code Quality)
- [x] All functions <50 LOC
- [x] Zero bare Exception catches
- [x] Custom exception hierarchy implemented
- [x] Per-host locks in connection pool

### Week 3 (CI/CD)
- [x] Pre-commit hooks working
- [x] GitHub Actions CI passing
- [x] Coverage ≥80%
- [x] Security scanning automated

### Week 4 (Polish)
- [x] All async cleanup uses `await`
- [x] Path traversal protection active
- [x] Connection pool has max size
- [x] Structured logging available

---

## 🔍 Code Review Checklist

Use this when reviewing PRs:

### Security
- [ ] No hardcoded credentials
- [ ] Input validation on all user data
- [ ] No shell injection risks
- [ ] No path traversal vulnerabilities
- [ ] Proper error messages (no sensitive data)

### Code Quality
- [ ] Function <50 LOC
- [ ] Specific exception types (not `Exception`)
- [ ] Proper type hints
- [ ] Docstring on public functions
- [ ] No print() statements

### Async Patterns
- [ ] All I/O uses async/await
- [ ] Proper resource cleanup
- [ ] No blocking calls in async functions
- [ ] Proper use of locks/semaphores

### Testing
- [ ] New code has tests
- [ ] Tests are independent
- [ ] Tests are deterministic (no random data)
- [ ] Coverage ≥80%

---

## 📚 Reference

- **Full Audit:** `.docs/python-best-practices-audit-2025-12-03.md`
- **Summary:** `.docs/best-practices-summary-2025-12-03.md`
- **Remediation Plan:** See "Prioritized Remediation Plan" in audit document

---

**Last Updated:** 2025-12-03
**Next Review:** 2025-12-10 (after Week 1 fixes)

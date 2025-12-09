# Testing Quick Reference Card

**Print & Post**

---

## Scout MCP Test Status (2025-12-07)

```
PHASE 2 READINESS: 67% ❌
├── Unit Tests: 85/95 tests ✓
├── Integration Tests: 35/40 tests ⚠
├── Security Tests: 2/6 requirements ✗
├── Performance Tests: 2/4 requirements ✗
└── BLOCKING GAPS: 12 scenarios ❌
```

---

## 4 CRITICAL BLOCKING ISSUES

### 1. SEC-005: No Singleton Thread-Safety Tests
**Status:** UNIMPLEMENTED
**Tests Needed:** 4
**Time:** 1.5h
**Risk:** Memory leaks, crashes under concurrency

```python
# Missing: test_concurrent_get_config_returns_same_instance()
# Missing: test_concurrent_get_pool_returns_same_instance()
```

### 2. SEC-003: No Resource Authorization Tests
**Status:** UNIMPLEMENTED
**Tests Needed:** 3
**Time:** 1h
**Risk:** Future auth bugs, accidental per-user filtering

```python
# Missing: test_scout_resource_has_no_user_parameter()
# Missing: test_config_has_no_user_filtering()
```

### 3. P0-4: Output Size Limit Not Tested
**Status:** CODE EXISTS, NO TESTS
**Tests Needed:** 5
**Time:** 1.5h
**Risk:** OOM attacks, memory exhaustion

```python
# Missing: test_cat_file_truncates_at_max_size()
# Missing: test_max_file_size_configurable()
```

### 4. P1-1: SSH Timeout Not Tested
**Status:** CODE EXISTS, NO TESTS
**Tests Needed:** 4
**Time:** 1.5h
**Risk:** Hanging commands, resource exhaustion

```python
# Missing: test_run_command_passes_timeout()
# Missing: test_timeout_prevents_hanging_commands()
```

---

## Test Files to Create

| File | Lines | Tests | Time |
|------|-------|-------|------|
| `tests/test_singleton_safety.py` | 60 | 4 | 1.5h |
| `tests/test_authorization.py` | 30 | 3 | 1h |
| `tests/test_output_limits.py` | 50 | 5 | 1.5h |
| `tests/test_ssh_timeout.py` | 40 | 4 | 1.5h |
| `tests/test_singleton_implementation.py` | 25 | 3 | 0.5h |
| **TOTAL** | **205** | **19** | **6h** |

---

## Current Test Inventory

```
Total Tests: 148
├── Unit: 85 (57%) ✓ Good
├── Integration: 35 (24%) ✓ Good
├── Performance: 20 (14%) ⚓ Partial
└── Specialized: 8 (5%) ✓ Good

Coverage: 65-75% (estimated) ⚠
Target: 85%+
Gap: 10-20%
```

---

## Module Coverage (Estimated)

| Module | Coverage | Status |
|--------|----------|--------|
| `utils/` | 85-90% | ✓ |
| `models/` | 80-90% | ✓ |
| `middleware/` | 75-85% | ⚠ |
| `services/` | 70-80% | ⚠ |
| `tools/` | 60-70% | ✗ |
| `resources/` | 50-60% | ✗ |

---

## Run Tests

```bash
# All tests
pytest tests/ -v

# By category
pytest tests/ -m security -v
pytest tests/ -m performance -v

# With coverage
pytest tests/ --cov=scout_mcp --cov-report=term-missing

# Phase 1 tests (when created)
pytest tests/test_singleton*.py tests/test_authorization.py \
       tests/test_output_limits.py tests/test_ssh_timeout.py -v
```

---

## Security Requirements Checklist

| Req | Requirement | Tests | Status |
|-----|-------------|-------|--------|
| SEC-001 | Auth disabled by default | ✓ 5 | ✓ PASS |
| SEC-002 | Bind to 0.0.0.0 | ✗ 0 | ✗ FAIL |
| SEC-003 | No resource ACLs | ✗ 0 | ✗ FAIL |
| SEC-004 | No audit logging | ✗ 0 | ✗ FAIL |
| SEC-005 | Singleton thread-safe | ✗ 0 | ✗ FAIL |
| SEC-007 | Health endpoint bypass | ✓ 1 | ✓ PASS |

**Score:** 2/6 (33%)

---

## Performance Requirements Checklist

| Req | Requirement | Tests | Target | Status |
|-----|-------------|-------|--------|--------|
| P0-4 | Output size limit | ✗ 0 | 1MB | ✗ FAIL |
| P1-1 | SSH timeout | ✗ 0 | 30s | ✗ FAIL |
| P2-1 | LRU eviction | ✓ 7 | 100 | ✓ PASS |
| P2-2 | Per-host locking | ✓ 8 | 10-50x | ✓ PASS |

**Score:** 2/4 (50%)

---

## Implementation Priority

### 🔴 CRITICAL (This Week)
1. Singleton safety (4 tests, 1.5h)
2. Auth verification (3 tests, 1h)
3. Output limits (5 tests, 1.5h)
4. SSH timeout (4 tests, 1.5h)
5. Implementation verify (3 tests, 0.5h)

**Total:** 19 tests, 6 hours

### 🟠 HIGH (Next Week)
- Network binding (2 tests, 1h)
- Multi-host broadcast (4 tests, 1.5h)
- Known hosts (3 tests, 1.5h)

**Total:** 9 tests, 4 hours

### 🟡 MEDIUM (Following Sprint)
- Resource tests (20+ tests, 8h)
- Memory benchmarks (2 tests, 1h)
- Middleware overhead (3 tests, 1.5h)

**Total:** 25+ tests, 10.5h

---

## Key Metrics

| Metric | Value | Status |
|--------|-------|--------|
| Total Tests | 148 | ✓ Good |
| Test/Code Ratio | 1.64:1 | ✓ Good |
| Coverage | 65-75% | ⚠ Gap |
| Flaky Tests | 0 | ✓ Good |
| Assertion Density | 1.5-3.0 | ✓ Good |
| Test Isolation | Good | ✓ Good |
| Documentation | Good | ✓ Good |

---

## Most Important Files

1. **docs/testing-evaluation.md** (320 lines)
   - Full analysis, 12 scenarios, roadmap

2. **docs/phase1-testing-implementation.md** (250 lines)
   - Copy-paste ready test code, checklist

3. **docs/testing-summary.md** (200 lines)
   - Executive summary, risks, action plan

4. **docs/testing-quick-reference.md** (THIS FILE)
   - One-page overview

---

## Phase 1 Success Criteria

After implementation, MUST HAVE:

- [x] Create 5 test files (205 lines)
- [ ] Implement 19 tests
- [ ] All 19 tests passing ✓
- [ ] No existing tests broken ✓
- [ ] Coverage to 70%+
- [ ] No new flaky tests

**Current:** 0/6
**Target:** 6/6 by end of week

---

## Estimated Timeline

| Phase | Duration | Tests | Lines | Effort |
|-------|----------|-------|-------|--------|
| **Phase 1** (Blocking) | 1 week | 19 | 205 | 6h |
| **Phase 2** (Quality) | 1 week | 9 | 130 | 4h |
| **Phase 3** (Completeness) | 2 weeks | 25+ | 290 | 10h |
| **TOTAL** | 4 weeks | 53+ | 625 | 20h |

---

## Links & References

| Document | Purpose | Link |
|----------|---------|------|
| **Evaluation** | Full analysis | `docs/testing-evaluation.md` |
| **Implementation** | How-to guide | `docs/phase1-testing-implementation.md` |
| **Summary** | Executive overview | `docs/testing-summary.md` |
| **Architecture** | System design | `scout_mcp/CLAUDE.md` |
| **Services** | Business logic | `scout_mcp/services/CLAUDE.md` |

---

## Quick Commands

```bash
# View test structure
find tests -name "test_*.py" | sort

# Run specific test file
pytest tests/test_pool.py -v

# Run by marker
pytest -m security -v
pytest -m performance -v

# Generate coverage
pytest tests/ --cov=scout_mcp --cov-report=html

# Show uncovered lines
pytest tests/ --cov=scout_mcp --cov-report=term-missing

# Run with parallel execution
pytest tests/ -n auto

# Run slow tests only
pytest -m slow -v

# Collect tests without running
pytest tests/ --collect-only -q
```

---

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| ModuleNotFoundError: fastmcp | Missing deps | `pip install fastmcp asyncssh` |
| Permission denied | File perms | `chmod 644 tests/**/*.py` |
| Fixture not found | Import issue | Check conftest.py |
| Timeout on tests | System slow | Increase timeout tolerance |
| Test flakiness | Timing deps | Mock time.monotonic() |

---

## Success Metrics

**Phase 1 Complete When:**

```
✓ 19 new tests created
✓ All 19 tests PASS
✓ Existing 148 tests still PASS
✓ Coverage improved to 70%+
✓ 0 flaky tests
✓ 0 test isolation issues
✓ Documentation updated
```

**Phase 2 Readiness Achieved When:**

```
✓ Phase 1 DONE
✓ 9 additional tests created
✓ All 28 new tests PASS
✓ Coverage improved to 80%+
✓ Security: 5/6 requirements tested
✓ Performance: 3/4 requirements tested
✓ PHASE 2 READY: YES
```

---

## Print This Card

```
┌─────────────────────────────────────────┐
│   SCOUT MCP TESTING QUICK REFERENCE     │
├─────────────────────────────────────────┤
│                                         │
│  PHASE 2 READINESS: 67% ❌               │
│                                         │
│  4 BLOCKING GAPS:                      │
│  ✗ SEC-005: Singleton threads (4 tests)│
│  ✗ SEC-003: Auth verify (3 tests)      │
│  ✗ P0-4: Output limits (5 tests)       │
│  ✗ P1-1: SSH timeout (4 tests)         │
│                                         │
│  PHASE 1: 19 tests, 6 hours            │
│  PHASE 2: 9 tests, 4 hours             │
│                                         │
│  Files to Read:                        │
│  1. testing-evaluation.md (320 lines)  │
│  2. phase1-testing-implementation.md   │
│  3. testing-summary.md                 │
│                                         │
└─────────────────────────────────────────┘
```

---

**Last Updated:** 2025-12-07
**Status:** Ready for Implementation
**Next Checkpoint:** End of Week 1 (Phase 1 Complete)


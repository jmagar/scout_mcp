# Test Coverage Baseline (2025-12-10)

## Overall Coverage

- **Total:** 74%
- **Target:** 85%+
- **Gap:** 11%

## Test Suite Summary

- **Total Tests:** 422
- **Passing:** 374 (88.6%)
- **Failing:** 48 (11.4%)
- **Warnings:** 23

## Coverage by Module

### High Coverage (≥85%)

| Module | Coverage | Notes |
|--------|----------|-------|
| scout_mcp/config.py | 89% | Config and SSH parsing |
| scout_mcp/services/pool.py | 89% | Connection pool management |
| scout_mcp/services/state.py | 95% | Global state management |
| scout_mcp/services/validation.py | 100% | Input validation |
| scout_mcp/ui/templates.py | 97% | UI template generation |
| scout_mcp/utils/parser.py | 100% | URI parsing |
| scout_mcp/utils/validation.py | 91% | Path validation |
| scout_mcp/utils/ping.py | 94% | Host reachability checks |
| scout_mcp/utils/mime.py | 86% | MIME type detection |

### Medium Coverage (70-84%)

| Module | Coverage | Notes |
|--------|----------|-------|
| scout_mcp/__main__.py | 70% | Entry point |

### Low Coverage (<70%)

| Module | Coverage | Missing Lines | Priority |
|--------|----------|---------------|----------|
| scout_mcp/utils/transfer.py | 0% | 3-79 | High - New module |
| scout_mcp/tools/scout.py | 42% | 41-63, 149-370 | High - Core tool |
| scout_mcp/tools/handlers.py | 56% | 60-360 | High - Request handlers |
| scout_mcp/tools/ui_tests.py | 58% | 136-301 | Medium - UI testing |
| scout_mcp/utils/console.py | 59% | 76-228 | Medium - Console output |
| scout_mcp/utils/hostname.py | 63% | 28-47 | Medium - Hostname detection |

## Known Issues

### Failing Tests (48)

#### Rate Limiting Tests (9 failures)
- Missing `dispatch` method on RateLimitMiddleware
- Tests expect old middleware interface
- **Fix:** Update middleware to new interface or update tests

#### Resource Tests (16 failures)
- UI-enabled tests failing due to HTML output instead of plain text
- Docker, Compose, Syslog, ZFS resources affected
- **Fix:** Mock UI setting or adjust assertions

#### Remote-to-Remote Transfer Tests (5 failures)
- `get_local_hostname` function missing
- SFTP context manager protocol issues
- **Fix:** Implement missing function, fix async context managers

#### Config Security Tests (2 failures)
- Log capture not working in tests
- Warnings logged but not captured by caplog
- **Fix:** Adjust log capture timing or test approach

#### Benchmark Tests (1 failure)
- URI parsing slightly over 0.01ms threshold
- **Fix:** Optimize parser or adjust threshold

#### Integration Tests (5 failures)
- Server lifespan tests failing with MCP protocol errors
- UI generator type errors
- **Fix:** Update to latest FastMCP API

## Next Steps

### Priority 1: Fix Critical Failures
1. **Rate limiting tests** - Update middleware interface
2. **Remote-to-remote transfers** - Implement missing functions
3. **Resource UI tests** - Mock UI setting properly

### Priority 2: Improve Core Coverage
1. **scout_mcp/tools/scout.py** (42% → 85%)
   - Add tests for error paths
   - Test beam transfer logic
   - Test tree display

2. **scout_mcp/tools/handlers.py** (56% → 85%)
   - Test request handlers
   - Test validation flows
   - Test error handling

3. **scout_mcp/utils/transfer.py** (0% → 85%)
   - Add complete test suite for new module
   - Test both upload and download
   - Test error conditions

### Priority 3: End-to-End Testing
1. Add more E2E integration tests
2. Test complete user workflows
3. Test error recovery scenarios

## Coverage Improvements Needed

To reach 85% target coverage, need to add approximately:
- ~260 lines of test coverage in core modules
- Focus on critical paths (scout tool, handlers, transfers)
- Add integration tests for full request flows

## Baseline Metrics

**Before Task 4 (E2E tests):** ~70% coverage
**After Task 4 (E2E tests):** 74% coverage
**Improvement:** +4%

**E2E tests added:**
- 9 new end-to-end workflow tests
- Full request flow testing
- Error recovery testing

## Test Infrastructure Health

### Strengths
- 422 total tests (comprehensive)
- Good benchmark suite (28 tests)
- Strong validation testing (48 tests)
- E2E workflow coverage (9 tests)
- 88.6% test pass rate

### Weaknesses
- 48 failing tests need attention
- Some modules have 0% coverage
- UI tests not properly mocked
- Middleware interface changes needed

## Recommendations

1. **Fix failing tests first** - Get to 100% pass rate
2. **Add missing tests** - Focus on 0% and <50% coverage modules
3. **Improve integration testing** - More E2E scenarios
4. **Update test infrastructure** - Fix mocking and fixtures
5. **Monitor coverage** - Set up CI to track coverage trends

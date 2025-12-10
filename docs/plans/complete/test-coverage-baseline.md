# Test Coverage Baseline

**Date:** 2025-12-10
**Overall Coverage:** 73.8% (1669/2261 statements)
**Test Suite:** 358 passed, 38 failed
**Target:** 85% coverage

## Summary

Current test coverage is 73.8%, below the 85% target. This document establishes the baseline and identifies areas requiring additional testing.

## Coverage by Module

### High Coverage (≥85%)

| Module | Coverage | Lines | Status |
|--------|----------|-------|--------|
| `scout_mcp/__init__.py` | 100% | 5/5 | ✓ |
| `scout_mcp/__main__.py` | 100% | 30/30 | ✓ |
| `scout_mcp/config.py` | 100% | 188/188 | ✓ |
| `scout_mcp/models/broadcast.py` | 100% | 3/3 | ✓ |
| `scout_mcp/models/command.py` | 100% | 3/3 | ✓ |
| `scout_mcp/models/target.py` | 100% | 3/3 | ✓ |
| `scout_mcp/middleware/__init__.py` | 100% | 4/4 | ✓ |
| `scout_mcp/middleware/base.py` | 100% | 4/4 | ✓ |
| `scout_mcp/resources/__init__.py` | 100% | 6/6 | ✓ |
| `scout_mcp/resources/hosts.py` | 100% | 22/22 | ✓ |
| `scout_mcp/services/__init__.py` | 100% | 9/9 | ✓ |
| `scout_mcp/services/validation.py` | 100% | 10/10 | ✓ |
| `scout_mcp/tools/__init__.py` | 100% | 3/3 | ✓ |
| `scout_mcp/ui/__init__.py` | 100% | 2/2 | ✓ |
| `scout_mcp/ui/generators.py` | 100% | 12/12 | ✓ |
| `scout_mcp/utils/__init__.py` | 100% | 8/8 | ✓ |
| `scout_mcp/utils/parser.py` | 100% | 16/16 | ✓ |
| `scout_mcp/utils/shell.py` | 100% | 5/5 | ✓ |
| `scout_mcp/middleware/auth.py` | 96.1% | 98/102 | ✓ |
| `scout_mcp/middleware/errors.py` | 94.7% | 90/95 | ✓ |
| `scout_mcp/services/state.py` | 95.0% | 19/20 | ✓ |
| `scout_mcp/utils/ping.py` | 93.8% | 15/16 | ✓ |
| `scout_mcp/utils/validation.py` | 91.4% | 32/35 | ✓ |
| `scout_mcp/services/pool.py` | 89.4% | 110/123 | ✓ |
| `scout_mcp/utils/mime.py` | 85.7% | 6/7 | ✓ |

### Needs Improvement (<85%)

| Module | Coverage | Lines | Priority | Issue |
|--------|----------|-------|----------|-------|
| `scout_mcp/utils/transfer.py` | 0.0% | 0/28 | **CRITICAL** | No tests |
| `scout_mcp/resources/zfs.py` | 9.4% | 8/85 | **HIGH** | Feature tests missing |
| `scout_mcp/resources/compose.py` | 18.0% | 9/50 | **HIGH** | Feature tests missing |
| `scout_mcp/resources/docker.py` | 20.5% | 8/39 | **HIGH** | Feature tests missing |
| `scout_mcp/resources/syslog.py` | 41.2% | 7/17 | **HIGH** | Feature tests missing |
| `scout_mcp/tools/scout.py` | 41.3% | 59/143 | **HIGH** | Main tool needs coverage |
| `scout_mcp/tools/handlers.py` | 54.2% | 77/142 | **MEDIUM** | Handler logic gaps |
| `scout_mcp/tools/ui_tests.py` | 58.1% | 25/43 | **MEDIUM** | Test file needs tests |
| `scout_mcp/utils/console.py` | 59.3% | 54/91 | **MEDIUM** | Console formatting gaps |
| `scout_mcp/utils/hostname.py` | 63.2% | 12/19 | **MEDIUM** | Hostname validation gaps |
| `scout_mcp/resources/scout.py` | 76.3% | 45/59 | LOW | Near target |
| `scout_mcp/middleware/logging.py` | 78.7% | 107/136 | LOW | Middleware coverage gaps |
| `scout_mcp/services/executors.py` | 78.7% | 310/394 | LOW | Core logic gaps |
| `scout_mcp/server.py` | 84.7% | 138/163 | LOW | Almost at target |

## Critical Issues (0% Coverage)

### scout_mcp/utils/transfer.py - 0% Coverage

**Purpose:** SFTP streaming utilities for remote-to-remote file transfers.

**Missing Coverage:**
- All 28 statements (lines 3-79)
- `stream_file_remote_to_remote()` - Main streaming function
- Error handling, chunk streaming, connection management

**Why Critical:**
- Core functionality for remote-to-remote beam transfers
- Used by `scout()` tool for advanced file operations
- Complex logic with multiple error paths

**Action Required:**
- Write integration tests for remote-to-remote transfers
- Test chunk streaming logic
- Test error conditions (source not found, upload failure, connection issues)

## High Priority Files (<50% Coverage)

### 1. scout_mcp/tools/scout.py - 41.3% Coverage

**Missing Coverage:**
- Remote-to-remote beam transfer logic (lines 149-173)
- Beam parameter validation (lines 41-63)
- Upload/download detection and execution (lines 220-251)
- Error handling paths (lines 255-266, 286-322)

**Action Required:**
- Add tests for beam transfers (upload, download)
- Add tests for remote-to-remote transfers
- Test error conditions and validation

### 2. scout_mcp/resources/zfs.py - 9.4% Coverage

**Missing Coverage:**
- ZFS pool overview (lines 26-37)
- Pool status queries (lines 45-71)
- Snapshot listing (lines 87+)

**Action Required:**
- Mock SSH commands for `zpool list`, `zpool status`, `zfs list -t snapshot`
- Test error cases (no ZFS, pool not found)

### 3. scout_mcp/resources/compose.py - 18.0% Coverage

**Missing Coverage:**
- Docker Compose project listing (lines 23-35)
- Compose file reading (lines 40-55)
- Container logs (lines 69-80)

**Action Required:**
- Mock SSH commands for `docker compose ls`, `cat docker-compose.yaml`, `docker compose logs`
- Test error cases (project not found, file not found)

### 4. scout_mcp/resources/docker.py - 20.5% Coverage

**Missing Coverage:**
- Container listing (lines 27-42)
- Container logs (lines 47-80)

**Action Required:**
- Mock SSH commands for `docker ps`, `docker logs`
- Test error cases (container not found, unknown host)

### 5. scout_mcp/resources/syslog.py - 41.2% Coverage

**Missing Coverage:**
- Syslog file reading (lines 27-47)
- Error handling (no logs available)

**Action Required:**
- Mock SSH commands for `cat /var/log/syslog`
- Test multiple syslog locations

## Medium Priority Files (50-70% Coverage)

### scout_mcp/tools/handlers.py - 54.2% Coverage

**Missing Coverage:**
- UI rendering paths (lines 46-47, 96, 112, 114, 118-119)
- Beam transfer handlers (lines 270-360)
- Error formatting

**Action Required:**
- Test UI generation when `SCOUT_ENABLE_UI=true`
- Test beam transfer handlers (upload/download/remote-to-remote)
- Test error response formatting

### scout_mcp/utils/console.py - 59.3% Coverage

**Missing Coverage:**
- Colored output formatting (lines 76, 139-193)
- Status indicators (lines 211-228)

**Action Required:**
- Test console formatting functions
- Test colored output generation

### scout_mcp/utils/hostname.py - 63.2% Coverage

**Missing Coverage:**
- Localhost detection logic (lines 28, 39-41, 45-47)

**Action Required:**
- Test `is_localhost()` with various hostname formats
- Test edge cases (IPv6, hostnames with dots)

## Test Failures Analysis

**38 tests failed** (out of 396 total):

### Remote-to-Remote Transfer Failures (7 tests)
- `test_beam_remote_to_remote_integration.py` (2 tests)
- `test_executors.py::test_beam_transfer_remote_to_remote_*` (3 tests)

**Root Cause:** Remote-to-remote transfer feature recently added, tests not updated.

### UI Feature Failures (11 tests)
- `test_ui/test_generators.py` (6 tests)
- `test_ui_error_handling.py` (2 tests)
- `test_resources/test_scout_ui.py` (3 tests)

**Root Cause:** MCP-UI integration changes, tests need updating.

### Resource Feature Failures (13 tests)
- `test_resources/test_compose.py` (4 tests)
- `test_resources/test_docker.py` (4 tests)
- `test_resources/test_zfs.py` (5 tests)

**Root Cause:** New resource features without corresponding tests.

### Security/Config Failures (4 tests)
- `test_config_security.py` (2 tests)
- `test_server_lifespan.py` (3 tests)

**Root Cause:** Recent security hardening changes.

## Recommendations

### Immediate Actions (Priority 1)

1. **Fix Critical: scout_mcp/utils/transfer.py (0% coverage)**
   - Write integration tests for `stream_file_remote_to_remote()`
   - Test chunk streaming, error handling, connection management
   - Estimated effort: 4-6 hours

2. **Fix Failed Tests (38 failures)**
   - Update remote-to-remote transfer tests
   - Fix UI generator tests
   - Update resource feature tests
   - Estimated effort: 6-8 hours

3. **Improve Main Tool: scout_mcp/tools/scout.py (41% → 85%)**
   - Add beam transfer tests (upload, download, remote-to-remote)
   - Test validation logic
   - Test error conditions
   - Estimated effort: 4-6 hours

### Short-Term Actions (Priority 2)

4. **Add Resource Tests (zfs.py, compose.py, docker.py, syslog.py)**
   - Mock SSH commands for each resource
   - Test happy paths and error conditions
   - Estimated effort: 8-10 hours

5. **Improve Handler Coverage: scout_mcp/tools/handlers.py (54% → 85%)**
   - Test UI rendering paths
   - Test beam transfer handlers
   - Estimated effort: 4-6 hours

### Long-Term Actions (Priority 3)

6. **Improve Utility Coverage (console.py, hostname.py)**
   - Test formatting functions
   - Test edge cases
   - Estimated effort: 2-4 hours

7. **Improve Middleware Coverage (logging.py, executors.py)**
   - Test logging middleware edge cases
   - Test executor error paths
   - Estimated effort: 4-6 hours

## Success Criteria

- Overall coverage ≥85%
- All tests passing (0 failures)
- Critical files (transfer.py, scout.py) ≥85%
- All resource files ≥85%

## Notes

- Coverage report generated with: `uv run pytest tests/ --cov=scout_mcp --cov-report=html --cov-report=json`
- HTML report: `/mnt/cache/code/scout_mcp/htmlcov/index.html`
- JSON report: `/mnt/cache/code/scout_mcp/coverage.json`
- Test execution time: ~16 seconds for full suite

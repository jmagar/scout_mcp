# Dynamic Host Resources Implementation Session

**Date:** 2025-11-28 to 2025-11-29
**Project:** scout_mcp
**Approach:** Subagent-driven TDD development

## Session Overview

Implemented dynamic host-based resource registration for the Scout MCP server. This enables URI schemes like `tootie://`, `squirts://`, `dookie://` instead of the generic `scout://{host}/{path}` pattern. Each SSH host discovered from `~/.ssh/config` now gets its own resource URI scheme registered at server startup via FastMCP's lifespan context manager.

### Discovered SSH Hosts
All 7 hosts from `~/.ssh/config` have dynamic URI schemes:
- `dookie://`, `shart://`, `squirts://`, `steamy-wsl://`, `tootie://`, `vivobook://`, `vivobook-wsl://`

## Timeline

1. **Task 1** - Added lifespan context manager and `create_server()` factory
2. **Task 2** - Extracted `_read_host_path` helper (completed in Task 1)
3. **Task 3** - Added end-to-end tests for dynamic resources (4 tests)
4. **Task 4** - Updated `hosts://list` to show dynamic URI schemes (2 tests)
5. **Task 5** - Verified full test suite (130 tests passing)
6. **Verification** - Confirmed `squirts://mnt/appdata/swag/nginx/nginx.conf` works via MCP resource

## Key Implementation Details

### Lifespan Context Manager
- Uses `@asynccontextmanager` to register resources at server startup
- Reads SSH hosts from config via `get_config().get_hosts()`
- Creates a resource template for each host using closure pattern
- Delegates to existing `scout_resource()` for file/directory reading

### Factory Function
- `create_server()` creates FastMCP instance with lifespan attached
- Configures middleware, registers tools and resources
- Module-level `mcp = create_server()` for backward compatibility

### Updated hosts://list Output
Shows both URI formats:
```
[✓] tootie (online)
    SSH:      admin@192.168.1.10:22
    Direct:   tootie://path/to/file
    Generic:  scout://tootie/path/to/file
```

## Files Modified

### Created
| File | Purpose |
|------|---------|
| `tests/test_server_lifespan.py` | Lifespan and dynamic resource tests (5 tests) |
| `tests/test_resources/__init__.py` | Test package marker |
| `tests/test_resources/test_hosts.py` | Updated hosts resource tests (2 tests) |

### Modified
| File | Changes |
|------|---------|
| `scout_mcp/server.py` | Added lifespan, `_read_host_path`, `create_server()` |
| `scout_mcp/resources/hosts.py` | Updated output format with dynamic schemes |

## Commits

```
ed33d8e feat: update hosts://list to show dynamic URI schemes
693df2a test: add end-to-end tests for dynamic host resources
6c9775e feat: add lifespan for dynamic host resource registration
```

## Test Coverage

| Module | Tests | Status |
|--------|-------|--------|
| test_server_lifespan.py | 5 | PASS |
| test_resources/test_hosts.py | 2 | PASS |
| **Total Suite** | **130** | **PASS** |

## Verification

```bash
# All tests pass
.venv/bin/python -m pytest tests/ -v
# 130 passed, 2 warnings in 7.76s

# Type checking passes
.venv/bin/python -m mypy scout_mcp/server.py scout_mcp/resources/hosts.py --strict
# Success: no issues found in 2 source files
```

## Usage Examples

```python
# New host-specific URI schemes (via lifespan registration)
tootie://etc/hosts
squirts://var/log/syslog
dookie://home/user/.bashrc

# Generic fallback (still works)
scout://tootie/etc/hosts
scout://squirts/var/log
```

## Architecture

```
Startup Flow:
┌─────────────────┐    ┌──────────────┐    ┌─────────────────────┐
│ app_lifespan()  │───▶│ get_hosts()  │───▶│ server.resource()   │
│ context manager │    │ from config  │    │ for each host       │
└─────────────────┘    └──────────────┘    └─────────────────────┘

Request Flow:
┌──────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ tootie://etc/... │───▶│ _read_host_path  │───▶│ scout_resource  │
│ dynamic resource │    │ (closure)        │    │ (existing impl) │
└──────────────────┘    └──────────────────┘    └─────────────────┘
```

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| Factory function `create_server()` | Allows testing with different configs, cleaner initialization |
| Delegate to `scout_resource()` | Reuse existing file/directory reading logic, single source of truth |
| Closure for host capture | Avoids late-binding issue where all handlers use last host name |
| Keep generic `scout://` | Backward compatibility, works for any host without restart |

## Next Steps

1. Consider caching host list to avoid re-reading SSH config on every request
2. Add resource discovery endpoint to list all dynamic schemes
3. Consider hot-reload capability for SSH config changes
